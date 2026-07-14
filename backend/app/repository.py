"""S3 record repository for Sentinel Actalyst.

The object layout is intentionally customer-first:

    {prefix}/accounts/{owner}/profile.json
    {prefix}/accounts/{owner}/companies/{company_id}/company.json
    {prefix}/accounts/{owner}/sources/{source_id}.json
    {prefix}/accounts/{owner}/runs/{run_id}.json
    {prefix}/accounts/{owner}/seen/{source_id}/{url_sha256}.json
    {prefix}/accounts/{owner}/insights/{insight_id}.json
    {prefix}/accounts/{owner}/jobs/{job_id}.json

Small ``operations/*-index`` objects are derived indexes for an admin lookup by
numeric ID. Customer requests never need to scan another customer's prefix.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from typing import Any, Callable, Iterable
from urllib.parse import quote
from uuid import uuid4

from backend.app.storage import JsonStorage, ObjectConflict, ObjectNotFound
from backend.app.storage import get_storage
from backend.app.config import get_settings


SCHEMA_VERSION = 1
TERMINAL_JOB_STATES = {"succeeded", "partially_succeeded", "failed", "cancelled"}
ACTIVE_JOB_STATES = {"queued", "starting", "running"}


class RepositoryError(RuntimeError):
    pass


class RecordNotFound(RepositoryError):
    pass


class DuplicateRecord(RepositoryError):
    pass


class SourceDisabled(RepositoryError):
    pass


class InvalidJobTransition(RepositoryError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat()


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def public_id() -> int:
    """A JavaScript-safe random ID, stable once persisted in S3."""
    return secrets.randbelow(2**52 - 1) + 1


def stable_id(*parts: object) -> int:
    raw = "\x1f".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:7], "big")


def url_fingerprint(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def owner_key(owner: str) -> str:
    return quote(owner.strip().lower(), safe="")


class S3Repository:
    def __init__(self, storage: JsonStorage, *, prefix: str) -> None:
        self.storage = storage
        self.prefix = prefix.strip("/")

    def _key(self, *parts: object) -> str:
        return "/".join((self.prefix, *(str(part).strip("/") for part in parts)))

    def _account_prefix(self, owner: str) -> str:
        return self._key("accounts", owner_key(owner))

    def _account_key(self, owner: str) -> str:
        return f"{self._account_prefix(owner)}/profile.json"

    def _company_key(self, owner: str, company_id: int) -> str:
        return f"{self._account_prefix(owner)}/companies/{company_id}/company.json"

    def _source_key(self, owner: str, source_id: int) -> str:
        return f"{self._account_prefix(owner)}/sources/{source_id}.json"

    def _run_key(self, owner: str, run_id: int) -> str:
        return f"{self._account_prefix(owner)}/runs/{run_id}.json"

    def _discovered_key(self, owner: str, source_id: int, url: str) -> str:
        return f"{self._account_prefix(owner)}/discovered/{source_id}/{url_fingerprint(url)}.json"

    def _seen_key(self, owner: str, source_id: int, url: str) -> str:
        return f"{self._account_prefix(owner)}/seen/{source_id}/{url_fingerprint(url)}.json"

    def _insight_key(self, owner: str, insight_id: int) -> str:
        return f"{self._account_prefix(owner)}/insights/{insight_id}.json"

    def _recipient_key(self, owner: str, recipient_id: int) -> str:
        return f"{self._account_prefix(owner)}/recipients/{recipient_id}.json"

    def _notification_key(self, owner: str) -> str:
        return f"{self._account_prefix(owner)}/settings/notifications.json"

    def _job_key(self, owner: str, job_id: str) -> str:
        return f"{self._account_prefix(owner)}/jobs/{job_id}.json"

    def _index_key(self, kind: str, record_id: int | str) -> str:
        return self._key("operations", f"{kind}-index", f"{record_id}.json")

    def _get(self, key: str) -> dict[str, Any]:
        try:
            return self.storage.get_json(key).value
        except ObjectNotFound as exc:
            raise RecordNotFound(key) from exc

    def _create(self, key: str, value: dict[str, Any]) -> dict[str, Any]:
        try:
            self.storage.put_json(key, value, if_none_match=True)
        except ObjectConflict as exc:
            raise DuplicateRecord(key) from exc
        return value

    def _update(self, key: str, change: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
        def updater(current: dict[str, Any] | None) -> dict[str, Any]:
            if current is None:
                raise RecordNotFound(key)
            next_value = change(current)
            next_value["updated_at"] = iso_now()
            return next_value

        try:
            return self.storage.update_json(key, updater).value
        except ObjectNotFound as exc:
            raise RecordNotFound(key) from exc

    def _put_index(self, kind: str, record_id: int | str, owner: str) -> None:
        key = self._index_key(kind, record_id)
        value = {
            "schema_version": SCHEMA_VERSION,
            "record_type": f"{kind}_index",
            "id": record_id,
            "owner_name": owner,
            "created_at": iso_now(),
        }
        try:
            self.storage.put_json(key, value, if_none_match=True)
        except ObjectConflict:
            # Repeated/idempotent writes are safe only when the index belongs to
            # the same owner. A different owner indicates a vanishingly unlikely
            # random-ID collision and must not be silently accepted.
            if self._get(key).get("owner_name") != owner:
                raise DuplicateRecord(f"Index collision for {kind}/{record_id}")

    def _owner_for(self, kind: str, record_id: int | str) -> str:
        value = self._get(self._index_key(kind, record_id))
        owner = value.get("owner_name")
        if not isinstance(owner, str):
            raise RecordNotFound(str(record_id))
        return owner

    def _require_owner(self, record: dict[str, Any], owner: str | None) -> dict[str, Any]:
        if owner is not None and record.get("owner_name") != owner:
            # Return 404 at the HTTP layer rather than reveal cross-account IDs.
            raise RecordNotFound(str(record.get("id", "record")))
        return record

    _LIST_RECORDS_MAX_WORKERS = 16

    def _get_or_none(self, key: str) -> dict[str, Any] | None:
        try:
            return self._get(key)
        except RecordNotFound:
            return None

    def _list_records(
        self,
        prefix: str,
        *,
        limit: int = 500,
        predicate: Callable[[dict[str, Any]], bool] | None = None,
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        cursor: str | None = None
        # Continue in pages so S3 pagination remains correct as a tenant grows.
        while len(records) < limit:
            page = self.storage.list_objects(prefix, cursor=cursor, limit=min(1000, limit))
            if page.keys:
                # Each key is an independent GetObject call; fetching them
                # concurrently turns O(n) sequential network round-trips into
                # O(n / workers), which is what made large feeds slow to load.
                workers = min(self._LIST_RECORDS_MAX_WORKERS, len(page.keys))
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    for record in pool.map(self._get_or_none, page.keys):
                        if record is None:
                            continue
                        if predicate is None or predicate(record):
                            records.append(record)
                            if len(records) >= limit:
                                break
            if not page.next_cursor or len(records) >= limit:
                break
            cursor = page.next_cursor
        return records

    # Accounts -----------------------------------------------------------------
    def get_account(self, name: str) -> dict[str, Any] | None:
        try:
            return self._get(self._account_key(name))
        except RecordNotFound:
            return None

    def create_account(self, name: str, password_hash: str, role: str = "customer") -> dict[str, Any]:
        normalized = name.strip()
        if role not in {"admin", "customer"}:
            raise ValueError("Invalid account role.")
        record = {
            "schema_version": SCHEMA_VERSION,
            "record_type": "account",
            "id": owner_key(normalized),
            "name": normalized,
            "normalized_name": normalized.lower(),
            "role": role,
            "password_hash": password_hash,
            "last_login_at": None,
            "created_at": iso_now(),
            "updated_at": iso_now(),
        }
        return self._create(self._account_key(normalized), record)

    def ensure_account(self, name: str, password_hash: str, role: str) -> dict[str, Any]:
        existing = self.get_account(name)
        if existing:
            return existing
        try:
            return self.create_account(name, password_hash, role)
        except DuplicateRecord:
            return self.get_account(name) or (_ for _ in ()).throw(RecordNotFound(name))

    def bootstrap_customer_accounts_once(self, accounts: Iterable[tuple[str, str]]) -> None:
        """Seed configured customers only during the initial S3 bootstrap.

        Customer accounts are managed through the admin UI after bootstrap, so
        deleting one must not recreate it merely because the backend restarts.
        """
        marker_key = self._key("operations", "bootstrap", "customer-accounts.json")
        try:
            self.storage.get_json(marker_key)
            return
        except ObjectNotFound:
            pass

        for name, password_hash in accounts:
            self.ensure_account(name, password_hash, "customer")
        try:
            self.storage.put_json(
                marker_key,
                {
                    "schema_version": SCHEMA_VERSION,
                    "record_type": "bootstrap_marker",
                    "created_at": iso_now(),
                },
                if_none_match=True,
            )
        except ObjectConflict:
            # Concurrent startup completed the same idempotent bootstrap.
            pass

    def list_accounts(self, *, limit: int = 1000) -> list[dict[str, Any]]:
        return sorted(
            self._list_records(
                f"{self._key('accounts')}/",
                limit=limit,
                predicate=lambda item: item.get("record_type") == "account",
            ),
            key=lambda item: str(item.get("name", "")).lower(),
        )

    def touch_account_login(self, name: str) -> None:
        self._update(
            self._account_key(name),
            lambda current: {**current, "last_login_at": iso_now()},
        )

    def delete_account(self, name: str) -> None:
        account = self.get_account(name)
        if account is None:
            raise RecordNotFound(name)
        if account.get("role") != "customer":
            raise ValueError("Only customer accounts may be deleted.")

        owner = str(account["name"])
        for source in self.list_sources(owner, limit=10000):
            self.delete_source(int(source["id"]), owner)
        for company in self.list_companies(owner, limit=10000):
            self.delete_company(int(company["id"]), owner)
        # Remove any orphaned records if an earlier partial delete left data
        # without its company or source.
        for recipient in self.list_recipients(owner, limit=10000):
            self.delete_recipient(int(recipient["id"]), owner)
        for job in self.list_jobs(owner, limit=10000):
            self.storage.delete(self._job_key(owner, str(job["job_id"])))
            self.storage.delete(self._index_key("job", str(job["job_id"])))
        self.storage.delete(self._notification_key(owner))
        self.storage.delete(self._account_key(owner))

    # Companies ----------------------------------------------------------------
    def _company_name_key(self, owner: str, name: str) -> str:
        digest = hashlib.sha256(name.strip().casefold().encode("utf-8")).hexdigest()
        return f"{self._account_prefix(owner)}/indexes/company-names/{digest}.json"

    def create_company(self, owner: str, name: str, priority: str = "medium") -> dict[str, Any]:
        company_id = public_id()
        now = iso_now()
        name_key = self._company_name_key(owner, name)
        name_record = {"schema_version": SCHEMA_VERSION, "company_id": company_id, "owner_name": owner}
        try:
            self.storage.put_json(name_key, name_record, if_none_match=True)
        except ObjectConflict as exc:
            raise DuplicateRecord("Company name already exists.") from exc
        record = {
            "schema_version": SCHEMA_VERSION,
            "record_type": "company",
            "id": company_id,
            "name": name,
            "owner_name": owner,
            "priority": priority,
            "created_at": now,
            "updated_at": now,
        }
        try:
            self._create(self._company_key(owner, company_id), record)
            self._put_index("company", company_id, owner)
        except Exception:
            self.storage.delete(name_key)
            raise
        return record

    def get_company(self, company_id: int, owner: str | None = None) -> dict[str, Any]:
        actual_owner = owner or self._owner_for("company", company_id)
        return self._require_owner(self._get(self._company_key(actual_owner, company_id)), owner)

    def list_companies(self, owner: str | None, *, limit: int = 500) -> list[dict[str, Any]]:
        if owner is None:
            return sorted(
                [
                    self.get_company(int(index["id"]))
                    for index in self._list_records(
                        f"{self._key('operations', 'company-index')}/", limit=limit
                    )
                ],
                key=lambda item: str(item["name"]).lower(),
            )
        return sorted(
            self._list_records(
                f"{self._account_prefix(owner)}/companies/",
                limit=limit,
                predicate=lambda item: item.get("record_type") == "company",
            ),
            key=lambda item: str(item["name"]).lower(),
        )

    def update_company(self, company_id: int, owner: str | None, **changes: Any) -> dict[str, Any]:
        current = self.get_company(company_id, owner)
        actual_owner = str(current["owner_name"])
        if "name" in changes and changes["name"] != current["name"]:
            new_name_key = self._company_name_key(actual_owner, str(changes["name"]))
            try:
                self.storage.put_json(
                    new_name_key,
                    {"schema_version": SCHEMA_VERSION, "company_id": company_id, "owner_name": actual_owner},
                    if_none_match=True,
                )
            except ObjectConflict as exc:
                raise DuplicateRecord("Company name already exists.") from exc
            self.storage.delete(self._company_name_key(actual_owner, str(current["name"])))
        allowed = {"name", "priority"}
        return self._update(
            self._company_key(actual_owner, company_id),
            lambda value: {**value, **{key: item for key, item in changes.items() if key in allowed}},
        )

    def delete_company(self, company_id: int, owner: str | None) -> None:
        company = self.get_company(company_id, owner)
        actual_owner = str(company["owner_name"])
        for source in self.list_sources(actual_owner, company_id=company_id):
            self.delete_source(int(source["id"]), actual_owner)
        for recipient in self.list_recipients(actual_owner, company_id=company_id):
            self.delete_recipient(int(recipient["id"]), actual_owner)
        self.storage.delete(self._company_key(actual_owner, company_id))
        self.storage.delete(self._company_name_key(actual_owner, str(company["name"])))
        self.storage.delete(self._index_key("company", company_id))

    # Sources / monitors --------------------------------------------------------
    def create_source(self, owner: str, payload: dict[str, Any]) -> dict[str, Any]:
        company_id = int(payload["company_id"])
        self.get_company(company_id, owner)
        source_id = public_id()
        now = iso_now()
        strategy = str(payload.get("strategy", "parent"))
        record = {
            "schema_version": SCHEMA_VERSION,
            "record_type": "source",
            "id": source_id,
            "owner_name": owner,
            "company_id": company_id,
            "url": str(payload["url"]),
            "strategy": strategy,
            "acquisition_provider": str(payload.get("acquisition_provider") or "auto"),
            "processing_pipeline": str(payload.get("processing_pipeline") or "auto"),
            "trace_js": bool(payload.get("trace_js", False)) if strategy == "parent" else False,
            "js_bundle_sources": list(payload.get("js_bundle_sources") or []),
            "enabled": bool(payload.get("enabled", True)),
            "schedule_minutes": int(payload.get("schedule_minutes", 60)),
            "last_checked_at": None,
            "baseline_completed_at": None,
            "created_at": now,
            "updated_at": now,
        }
        self._create(self._source_key(owner, source_id), record)
        self._put_index("source", source_id, owner)
        return record

    def get_source(self, source_id: int, owner: str | None = None) -> dict[str, Any]:
        actual_owner = owner or self._owner_for("source", source_id)
        return self._require_owner(self._get(self._source_key(actual_owner, source_id)), owner)

    def list_sources(
        self, owner: str | None, *, company_id: int | None = None, limit: int = 500
    ) -> list[dict[str, Any]]:
        if owner is None:
            records = [
                self.get_source(int(index["id"]))
                for index in self._list_records(f"{self._key('operations', 'source-index')}/", limit=limit)
            ]
        else:
            records = self._list_records(
                f"{self._account_prefix(owner)}/sources/",
                limit=limit,
                predicate=lambda item: item.get("record_type") == "source",
            )
        if company_id is not None:
            records = [item for item in records if int(item["company_id"]) == company_id]
        return sorted(records, key=lambda item: (str(item["url"]), int(item["id"])))

    def update_source(self, source_id: int, owner: str | None, **changes: Any) -> dict[str, Any]:
        source = self.get_source(source_id, owner)
        allowed = {
            "url", "strategy", "acquisition_provider", "processing_pipeline", "trace_js",
            "js_bundle_sources", "enabled", "schedule_minutes", "last_checked_at", "baseline_completed_at",
        }

        def apply(current: dict[str, Any]) -> dict[str, Any]:
            next_value = {**current, **{key: value for key, value in changes.items() if key in allowed}}
            if next_value["strategy"] != "parent":
                next_value["trace_js"] = False
            return next_value

        return self._update(self._source_key(str(source["owner_name"]), source_id), apply)

    def delete_source(self, source_id: int, owner: str | None) -> None:
        source = self.get_source(source_id, owner)
        actual_owner = str(source["owner_name"])
        for job in self.list_jobs(actual_owner, limit=10000):
            if job.get("source_id") == source_id:
                self.storage.delete(self._job_key(actual_owner, str(job["job_id"])))
                self.storage.delete(self._index_key("job", str(job["job_id"])))
        for prefix in (
            f"{self._account_prefix(actual_owner)}/seen/{source_id}/",
            f"{self._account_prefix(actual_owner)}/discovered/{source_id}/",
        ):
            for record in self._list_records(prefix, limit=10000):
                url = record.get("url")
                if isinstance(url, str):
                    self.storage.delete(
                        self._seen_key(actual_owner, source_id, url)
                        if "/seen/" in prefix
                        else self._discovered_key(actual_owner, source_id, url)
                    )
        for run in self.list_runs(actual_owner, source_id=source_id, limit=10000):
            self.storage.delete(self._run_key(actual_owner, int(run["id"])))
            self.storage.delete(self._index_key("run", int(run["id"])))
        for insight in self.list_insights(actual_owner, source_id=source_id, limit=10000):
            self.storage.delete(self._insight_key(actual_owner, int(insight["id"])))
            self.storage.delete(self._index_key("insight", int(insight["id"])))
        self.storage.delete(self._source_key(actual_owner, source_id))
        self.storage.delete(self._index_key("source", source_id))

    # Runs, discovery and authoritative seen state -----------------------------
    def create_run(self, owner: str, source: dict[str, Any], operation: str, job_id: str) -> dict[str, Any]:
        run_id = public_id()
        now = iso_now()
        record = {
            "schema_version": SCHEMA_VERSION,
            "record_type": "monitor_run",
            "id": run_id,
            "owner_name": owner,
            "source_id": int(source["id"]),
            "company_id": int(source["company_id"]),
            "job_id": job_id,
            "operation": operation,
            "status": "queued",
            "started_at": now,
            "finished_at": None,
            "error": None,
            "result_summary": {},
            "created_at": now,
            "updated_at": now,
        }
        self._create(self._run_key(owner, run_id), record)
        self._put_index("run", run_id, owner)
        return record

    def get_run(self, run_id: int, owner: str | None = None) -> dict[str, Any]:
        actual_owner = owner or self._owner_for("run", run_id)
        return self._require_owner(self._get(self._run_key(actual_owner, run_id)), owner)

    def list_runs(
        self, owner: str | None, *, source_id: int | None = None, limit: int = 500
    ) -> list[dict[str, Any]]:
        if owner is None:
            records = [
                self.get_run(int(index["id"]))
                for index in self._list_records(f"{self._key('operations', 'run-index')}/", limit=limit)
            ]
        else:
            records = self._list_records(f"{self._account_prefix(owner)}/runs/", limit=limit)
        if source_id is not None:
            records = [record for record in records if int(record["source_id"]) == source_id]
        return sorted(records, key=lambda record: str(record["started_at"]), reverse=True)

    def update_run(self, run_id: int, owner: str, **changes: Any) -> dict[str, Any]:
        allowed = {"status", "finished_at", "error", "result_summary"}
        return self._update(
            self._run_key(owner, run_id),
            lambda record: {**record, **{key: value for key, value in changes.items() if key in allowed}},
        )

    def record_discovered_url(
        self, owner: str, source: dict[str, Any], run_id: int, url: str, payload: dict[str, Any] | None
    ) -> dict[str, Any]:
        key = self._discovered_key(owner, int(source["id"]), url)
        existing = None
        try:
            existing = self._get(key)
        except RecordNotFound:
            pass
        if existing:
            return existing
        now = iso_now()
        record = {
            "schema_version": SCHEMA_VERSION,
            "record_type": "discovered_url",
            "id": stable_id("discovered", owner, source["id"], url),
            "owner_name": owner,
            "source_id": int(source["id"]),
            "company_id": int(source["company_id"]),
            "monitor_run_id": run_id,
            "url": url,
            "payload": payload,
            "discovered_at": now,
            "created_at": now,
            "updated_at": now,
        }
        try:
            return self._create(key, record)
        except DuplicateRecord:
            return self._get(key)

    def list_discovered_urls(self, owner: str, source_id: int, *, limit: int = 500) -> list[dict[str, Any]]:
        return sorted(
            self._list_records(f"{self._account_prefix(owner)}/discovered/{source_id}/", limit=limit),
            key=lambda item: str(item["discovered_at"]),
            reverse=True,
        )

    def seen_record(self, owner: str, source_id: int, url: str) -> dict[str, Any] | None:
        try:
            return self._get(self._seen_key(owner, source_id, url))
        except RecordNotFound:
            return None

    def mark_seen(
        self, owner: str, source_id: int, url: str, *, insight_id: int | None = None, baseline: bool = False
    ) -> bool:
        now = iso_now()
        value = {
            "schema_version": SCHEMA_VERSION,
            "record_type": "seen_url",
            "owner_name": owner,
            "source_id": source_id,
            "url": url,
            "insight_id": insight_id,
            "baseline": baseline,
            "first_seen_at": now,
            "processed_at": now,
            "created_at": now,
            "updated_at": now,
        }
        try:
            self.storage.put_json(self._seen_key(owner, source_id, url), value, if_none_match=True)
            return True
        except ObjectConflict:
            return False

    # Insights -----------------------------------------------------------------
    def persist_insight(
        self,
        owner: str,
        source: dict[str, Any],
        discovered: dict[str, Any],
        analysis: dict[str, Any],
    ) -> dict[str, Any]:
        insight_id = stable_id("insight", owner, source["id"], discovered["url"])
        key = self._insight_key(owner, insight_id)
        try:
            return self._get(key)
        except RecordNotFound:
            pass
        now = iso_now()
        record = {
            "schema_version": SCHEMA_VERSION,
            "record_type": "insight",
            "id": insight_id,
            "owner_name": owner,
            "company_id": int(source["company_id"]),
            "source_id": int(source["id"]),
            "discovered_url_id": int(discovered["id"]),
            "discovered_url": str(discovered["url"]),
            "title": analysis.get("headline") or analysis.get("title"),
            "summary": str(analysis.get("summary") or ""),
            "model": analysis.get("model"),
            "severity": analysis.get("severity", "medium"),
            "confidence": analysis.get("confidence", "medium"),
            "raw_analysis": analysis.get("raw"),
            "reviewed_at": None,
            "email_status": "pending",
            "email_sent_at": None,
            "email_error": None,
            "created_at": now,
            "updated_at": now,
        }
        try:
            self._create(key, record)
            self._put_index("insight", insight_id, owner)
            return record
        except DuplicateRecord:
            return self._get(key)

    def get_insight(self, insight_id: int | str, owner: str | None = None) -> dict[str, Any]:
        actual_owner = owner or self._owner_for("insight", insight_id)
        return self._require_owner(self._get(self._insight_key(actual_owner, insight_id)), owner)

    def list_insights(
        self, owner: str | None, *, source_id: int | None = None, limit: int = 500
    ) -> list[dict[str, Any]]:
        if owner is None:
            records = [
                self.get_insight(int(index["id"]))
                for index in self._list_records(f"{self._key('operations', 'insight-index')}/", limit=limit)
            ]
        else:
            records = self._list_records(f"{self._account_prefix(owner)}/insights/", limit=limit)
        if source_id is not None:
            records = [record for record in records if int(record["source_id"]) == source_id]
        return sorted(records, key=lambda record: str(record["created_at"]), reverse=True)

    def update_insight_review(self, insight_id: int | str, owner: str | None, reviewed: bool) -> dict[str, Any]:
        insight = self.get_insight(insight_id, owner)
        return self._update(
            self._insight_key(str(insight["owner_name"]), insight_id),
            lambda record: {**record, "reviewed_at": iso_now() if reviewed else None},
        )

    def claim_email_delivery(self, insight_id: int | str, owner: str) -> dict[str, Any] | None:
        key = self._insight_key(owner, insight_id)
        claimed = False

        def apply(record: dict[str, Any]) -> dict[str, Any]:
            nonlocal claimed
            if record.get("email_status") in {"sent", "sending"}:
                return record
            claimed = True
            return {**record, "email_status": "sending", "email_error": None}

        record = self._update(key, apply)
        return record if claimed else None

    def complete_email_delivery(
        self, insight_id: int | str, owner: str, *, sent: bool, error: str | None = None, status: str | None = None
    ) -> dict[str, Any]:
        return self._update(
            self._insight_key(owner, insight_id),
            lambda record: {
                **record,
                "email_status": status or ("sent" if sent else "failed"),
                "email_sent_at": iso_now() if sent or status == "sent" else None,
                "email_error": error,
            },
        )

    # Notification settings / recipients --------------------------------------
    def get_notification_mode(self, owner: str) -> str:
        try:
            return str(self._get(self._notification_key(owner)).get("mode", "manual"))
        except RecordNotFound:
            return "manual"

    def set_notification_mode(self, owner: str, mode: str) -> dict[str, Any]:
        if mode not in {"manual", "automatic"}:
            raise ValueError("Notification mode must be manual or automatic.")
        key = self._notification_key(owner)
        now = iso_now()
        return self.storage.update_json(
            key,
            lambda current: {
                **(current or {"schema_version": SCHEMA_VERSION, "record_type": "notification_settings", "owner_name": owner, "created_at": now}),
                "mode": mode,
                "updated_at": now,
            },
        ).value

    def create_recipient(self, owner: str, company_id: int, email: str, enabled: bool = True) -> dict[str, Any]:
        self.get_company(company_id, owner)
        existing = [
            item for item in self.list_recipients(owner, company_id=company_id)
            if str(item["email"]).casefold() == email.casefold()
        ]
        if existing:
            raise DuplicateRecord("Recipient already exists for this company.")
        recipient_id = public_id()
        now = iso_now()
        record = {
            "schema_version": SCHEMA_VERSION,
            "record_type": "notification_recipient",
            "id": recipient_id,
            "owner_name": owner,
            "company_id": company_id,
            "email": email.strip().lower(),
            "enabled": bool(enabled),
            "created_at": now,
            "updated_at": now,
        }
        self._create(self._recipient_key(owner, recipient_id), record)
        self._put_index("recipient", recipient_id, owner)
        return record

    def get_recipient(self, recipient_id: int, owner: str | None = None) -> dict[str, Any]:
        actual_owner = owner or self._owner_for("recipient", recipient_id)
        return self._require_owner(self._get(self._recipient_key(actual_owner, recipient_id)), owner)

    def list_recipients(
        self, owner: str, *, company_id: int | None = None, limit: int = 500
    ) -> list[dict[str, Any]]:
        records = self._list_records(f"{self._account_prefix(owner)}/recipients/", limit=limit)
        if company_id is not None:
            records = [record for record in records if int(record["company_id"]) == company_id]
        return sorted(records, key=lambda record: str(record["email"]))

    def update_recipient(self, recipient_id: int, owner: str | None, **changes: Any) -> dict[str, Any]:
        recipient = self.get_recipient(recipient_id, owner)
        if "email" in changes:
            duplicate = [
                item for item in self.list_recipients(str(recipient["owner_name"]), company_id=int(recipient["company_id"]))
                if int(item["id"]) != recipient_id and str(item["email"]).casefold() == str(changes["email"]).casefold()
            ]
            if duplicate:
                raise DuplicateRecord("Recipient already exists for this company.")
        return self._update(
            self._recipient_key(str(recipient["owner_name"]), recipient_id),
            lambda record: {**record, **{key: value for key, value in changes.items() if key in {"email", "enabled"}}},
        )

    def delete_recipient(self, recipient_id: int, owner: str | None) -> None:
        recipient = self.get_recipient(recipient_id, owner)
        self.storage.delete(self._recipient_key(str(recipient["owner_name"]), recipient_id))
        self.storage.delete(self._index_key("recipient", recipient_id))

    # ECS application jobs -----------------------------------------------------
    def create_job(
        self,
        owner: str,
        *,
        operation: str,
        company_id: int | None = None,
        source_id: int | None = None,
        run_id: int | None = None,
        options: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        job_id = str(uuid4())
        now = iso_now()
        record = {
            "schema_version": SCHEMA_VERSION,
            "record_type": "job",
            "job_id": job_id,
            "id": job_id,
            "owner_name": owner,
            "operation": operation,
            "company_id": company_id,
            "source_id": source_id,
            "run_id": run_id,
            "options": options or {},
            "status": "queued",
            "ecs_task_arn": None,
            "correlation_id": correlation_id or str(uuid4()),
            "created_at": now,
            "started_at": None,
            "updated_at": now,
            "completed_at": None,
            "progress": {"completed": 0, "total": 0},
            "result_summary": None,
            "error": None,
            "retry": {"attempt": 0, "max_attempts": 3},
        }
        self._create(self._job_key(owner, job_id), record)
        self._put_index("job", job_id, owner)
        return record

    def get_job(self, job_id: str, owner: str | None = None) -> dict[str, Any]:
        actual_owner = owner or self._owner_for("job", job_id)
        return self._require_owner(self._get(self._job_key(actual_owner, job_id)), owner)

    def list_jobs(self, owner: str | None, *, limit: int = 500) -> list[dict[str, Any]]:
        if owner is None:
            records = [
                self.get_job(str(index["id"]))
                for index in self._list_records(f"{self._key('operations', 'job-index')}/", limit=limit)
            ]
        else:
            records = self._list_records(f"{self._account_prefix(owner)}/jobs/", limit=limit)
        return sorted(records, key=lambda record: str(record["created_at"]), reverse=True)

    def update_job(self, job_id: str, owner: str, **changes: Any) -> dict[str, Any]:
        allowed = {"run_id", "status", "ecs_task_arn", "started_at", "completed_at", "progress", "result_summary", "error", "retry"}
        requested_status = changes.get("status")

        def apply(record: dict[str, Any]) -> dict[str, Any]:
            current_status = str(record["status"])
            if requested_status and current_status in TERMINAL_JOB_STATES and requested_status != current_status:
                raise InvalidJobTransition(f"Cannot transition terminal job from {current_status}.")
            if requested_status and requested_status not in ACTIVE_JOB_STATES | TERMINAL_JOB_STATES:
                raise InvalidJobTransition(f"Unknown job state: {requested_status}")
            return {**record, **{key: value for key, value in changes.items() if key in allowed}}

        return self._update(self._job_key(owner, job_id), apply)

    def claim_job(self, job_id: str, owner: str, runner_id: str) -> dict[str, Any] | None:
        claimed = False

        def apply(record: dict[str, Any]) -> dict[str, Any]:
            nonlocal claimed
            if record.get("status") not in {"queued", "starting"}:
                return record
            if record.get("runner_id") and record.get("runner_id") != runner_id:
                return record
            claimed = True
            return {
                **record,
                "status": "running",
                "runner_id": runner_id,
                "started_at": record.get("started_at") or iso_now(),
                "retry": {**dict(record.get("retry") or {}), "attempt": int((record.get("retry") or {}).get("attempt", 0)) + 1},
            }

        record = self._update(self._job_key(owner, job_id), apply)
        return record if claimed else None

    # Operational reports ------------------------------------------------------
    def insight_stats(self, owner: str | None, *, days: int = 30) -> dict[str, Any]:
        start = (utc_now() - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
        insights = [
            insight for insight in self.list_insights(owner, limit=10000)
            if (parse_time(str(insight.get("created_at"))) or start) >= start
        ]
        companies: dict[int, dict[str, Any]] = {}
        sources: dict[int, dict[str, Any]] = {}
        for source in self.list_sources(owner, limit=10000):
            sources[int(source["id"])] = source
            try:
                companies[int(source["company_id"])] = self.get_company(int(source["company_id"]), owner)
            except RecordNotFound:
                continue
        dates = [(start.date() + timedelta(days=index)).isoformat() for index in range(days)]
        daily: Counter[str] = Counter()
        company_counts: Counter[int] = Counter()
        source_counts: Counter[int] = Counter()
        by_source_daily: dict[int, Counter[str]] = defaultdict(Counter)
        latency_total = 0.0
        latency_samples = 0
        for insight in insights:
            created = parse_time(str(insight["created_at"]))
            if not created:
                continue
            day = created.date().isoformat()
            source_id = int(insight["source_id"])
            company_id = int(insight["company_id"])
            daily[day] += 1
            company_counts[company_id] += 1
            source_counts[source_id] += 1
            by_source_daily[source_id][day] += 1
            discovered = self._get_discovered_by_id(str(insight["owner_name"]), source_id, int(insight["discovered_url_id"]))
            discovered_at = parse_time(discovered.get("discovered_at")) if discovered else None
            if discovered_at:
                latency = (created - discovered_at).total_seconds()
                if latency >= 0:
                    latency_total += latency
                    latency_samples += 1
        return {
            "days": days,
            "daily": [{"date": date, "count": daily[date]} for date in dates],
            "by_company": sorted(
                [
                    {"company_id": company_id, "company_name": companies.get(company_id, {}).get("name", "Unknown"), "count": count}
                    for company_id, count in company_counts.items()
                ], key=lambda item: item["count"], reverse=True,
            ),
            "busiest_sources": sorted(
                [
                    {"source_id": source_id, "url": sources.get(source_id, {}).get("url", ""), "count": count}
                    for source_id, count in source_counts.items()
                ], key=lambda item: item["count"], reverse=True,
            )[:5],
            "by_source_daily": {source_id: [counts[date] for date in dates] for source_id, counts in by_source_daily.items()},
            "avg_seconds_to_insight": latency_total / latency_samples if latency_samples else None,
        }

    def _get_discovered_by_id(self, owner: str, source_id: int, discovered_id: int) -> dict[str, Any] | None:
        for record in self._list_records(f"{self._account_prefix(owner)}/discovered/{source_id}/", limit=10000):
            if int(record.get("id", 0)) == discovered_id:
                return record
        return None

    def due_sources(self, now: datetime | None = None) -> list[dict[str, Any]]:
        now = now or utc_now()
        due: list[dict[str, Any]] = []
        for source in self.list_sources(None, limit=10000):
            if not source.get("enabled", True):
                continue
            last_checked = parse_time(source.get("last_checked_at"))
            cadence = timedelta(minutes=max(0, int(source.get("schedule_minutes", 60))))
            if last_checked is None or last_checked + cadence <= now:
                active = [
                    job for job in self.list_jobs(str(source["owner_name"]), limit=1000)
                    if int(job.get("source_id") or 0) == int(source["id"]) and job.get("status") in ACTIVE_JOB_STATES
                ]
                if not active:
                    due.append(source)
        return due

    def monitor_status(self, owner: str | None) -> dict[str, int]:
        sources = self.list_sources(owner, limit=10000)
        jobs = self.list_jobs(owner, limit=10000)
        today = utc_now().date().isoformat()
        return {
            "enabled_sources": sum(1 for source in sources if source.get("enabled")),
            "queued": sum(1 for job in jobs if job.get("status") in {"queued", "starting"}),
            "running": sum(1 for job in jobs if job.get("status") == "running"),
            "completed_today": sum(1 for job in jobs if job.get("status") in {"succeeded", "partially_succeeded"} and str(job.get("completed_at") or "").startswith(today)),
            "failed_today": sum(1 for job in jobs if job.get("status") == "failed" and str(job.get("completed_at") or "").startswith(today)),
        }


_repository_override: S3Repository | None = None
_cached_repository: S3Repository | None = None


def get_repository() -> S3Repository:
    global _cached_repository
    if _repository_override is not None:
        return _repository_override
    if _cached_repository is None:
        settings = get_settings()
        _cached_repository = S3Repository(get_storage(settings), prefix=settings.storage_prefix)
    return _cached_repository


def set_repository_for_testing(repository: S3Repository | None) -> None:
    global _repository_override, _cached_repository
    _repository_override = repository
    _cached_repository = None
