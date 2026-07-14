"""Idempotently migrate legacy PostgreSQL/JSON state into the S3 repository.

This is deliberately an offline administrative tool, not an application
runtime dependency. PostgreSQL support is loaded only when --postgres-dsn is
used, so the service image never needs psycopg.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

from backend.app.auth import hash_password
from backend.app.repository import DuplicateRecord, RecordNotFound, S3Repository
from backend.app.storage import get_storage
from backend.app.config import get_settings


class Migration:
    def __init__(self, repository: S3Repository) -> None:
        self.repository = repository
        self.counts: Counter[str] = Counter()
        self.errors: list[str] = []
        self.company_ids: dict[int, dict[str, Any]] = {}
        self.source_ids: dict[int, dict[str, Any]] = {}
        self.run_ids: dict[int, dict[str, Any]] = {}
        self.discovered_ids: dict[int, dict[str, Any]] = {}

    def _record(self, category: str, action: str) -> None:
        self.counts[f"{category}_{action}"] += 1

    def _safe(self, category: str, callback) -> Any | None:
        try:
            value = callback()
        except Exception as exc:
            self._record(category, "failed")
            self.errors.append(f"{category}: {exc}")
            return None
        self._record(category, "migrated")
        return value

    def ensure_account(self, name: str, password: str = "migration-reset-required") -> None:
        if not name:
            name = "legacy-unassigned"
        if self.repository.get_account(name):
            self._record("accounts", "skipped")
            return
        try:
            self.repository.create_account(name, hash_password(password), "customer")
        except DuplicateRecord:
            self._record("accounts", "duplicate")
        else:
            self._record("accounts", "migrated")

    def import_accounts_json(self, directory: Path) -> None:
        path = directory / "accounts.json"
        if not path.exists():
            self._record("accounts", "skipped")
            return
        try:
            records = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            self.errors.append(f"accounts JSON: {exc}")
            self._record("accounts", "failed")
            return
        for row in records if isinstance(records, list) else []:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or "").strip()
            if not name:
                self._record("accounts", "skipped")
                continue
            # Existing legacy plaintext values are hashed during import and are
            # never copied into S3 as plaintext.
            self.ensure_account(name, str(row.get("password") or "migration-reset-required"))

    def import_company(self, row: dict[str, Any]) -> None:
        owner = str(row.get("owner_name") or "legacy-unassigned")
        self.ensure_account(owner)
        old_id = int(row.get("id") or 0)
        name = str(row.get("name") or "").strip()
        if not name:
            self._record("companies", "skipped")
            return
        existing = next((item for item in self.repository.list_companies(owner, limit=10000) if item["name"].casefold() == name.casefold()), None)
        if existing:
            self.company_ids[old_id] = existing
            self._record("companies", "duplicate")
            return
        value = self._safe("companies", lambda: self.repository.create_company(owner, name, str(row.get("priority") or "medium")))
        if value:
            self.company_ids[old_id] = value

    def import_source(self, row: dict[str, Any]) -> None:
        old_company_id = int(row.get("company_id") or 0)
        company = self.company_ids.get(old_company_id)
        if not company:
            self._record("sources", "skipped")
            return
        owner = str(company["owner_name"])
        old_id = int(row.get("id") or 0)
        url = str(row.get("url") or "").strip()
        if not url:
            self._record("sources", "skipped")
            return
        existing = next((item for item in self.repository.list_sources(owner, company_id=int(company["id"]), limit=10000) if item["url"] == url), None)
        if existing:
            self.source_ids[old_id] = existing
            self._record("sources", "duplicate")
            return
        value = self._safe("sources", lambda: self.repository.create_source(owner, {
            "company_id": company["id"], "url": url, "strategy": row.get("strategy") or "parent",
            "trace_js": bool(row.get("trace_js")), "js_bundle_sources": row.get("js_bundle_sources") or [],
            "enabled": bool(row.get("enabled", True)), "schedule_minutes": int(row.get("schedule_minutes") or 60),
        }))
        if value:
            self.source_ids[old_id] = value

    def import_recipient(self, row: dict[str, Any]) -> None:
        company = self.company_ids.get(int(row.get("company_id") or 0))
        email = str(row.get("email") or "").strip()
        if not company or not email:
            self._record("recipients", "skipped")
            return
        owner = str(company["owner_name"])
        if any(item["email"] == email.lower() for item in self.repository.list_recipients(owner, company_id=int(company["id"]), limit=10000)):
            self._record("recipients", "duplicate")
            return
        self._safe("recipients", lambda: self.repository.create_recipient(owner, int(company["id"]), email, bool(row.get("enabled", True))))

    def import_run(self, row: dict[str, Any]) -> None:
        source = self.source_ids.get(int(row.get("source_id") or 0))
        if not source:
            self._record("runs", "skipped")
            return
        owner = str(source["owner_name"])
        old_id = int(row.get("id") or 0)
        created = self.repository.create_run(owner, source, "migration", f"legacy-run-{old_id}")
        value = self.repository.update_run(
            int(created["id"]), owner,
            status=str(row.get("status") or "completed"),
            finished_at=(str(row["finished_at"]) if row.get("finished_at") else None),
            error=(str(row["error"]) if row.get("error") else None),
        )
        self.run_ids[old_id] = value
        self._record("runs", "migrated")

    def import_discovered(self, row: dict[str, Any]) -> None:
        source = self.source_ids.get(int(row.get("source_id") or 0))
        url = str(row.get("url") or "").strip()
        if not source or not url:
            self._record("discovered_urls", "skipped")
            return
        owner = str(source["owner_name"])
        old_id = int(row.get("id") or 0)
        legacy_run = self.run_ids.get(int(row.get("monitor_run_id") or 0))
        if not legacy_run:
            legacy_run = self.repository.create_run(owner, source, "migration", f"legacy-discovered-{old_id}")
        value = self.repository.record_discovered_url(owner, source, int(legacy_run["id"]), url, row.get("payload") if isinstance(row.get("payload"), dict) else None)
        if row.get("discovered_at"):
            value = self.repository._update(
                self.repository._discovered_key(owner, int(source["id"]), url),
                lambda current: {**current, "discovered_at": str(row["discovered_at"])},
            )
        self.discovered_ids[old_id] = value
        self._record("discovered_urls", "migrated")

    def import_summary(self, row: dict[str, Any]) -> None:
        discovered = self.discovered_ids.get(int(row.get("discovered_url_id") or 0))
        if not discovered:
            self._record("insights", "skipped")
            return
        source = next((item for item in self.source_ids.values() if int(item["id"]) == int(discovered["source_id"])), None)
        if not source:
            self._record("insights", "skipped")
            return
        owner = str(source["owner_name"])
        insight = self.repository.persist_insight(owner, source, discovered, {
            "headline": row.get("title") or discovered["url"], "summary": row.get("summary") or "Legacy insight",
            "model": row.get("model"), "severity": row.get("severity") or "medium",
            "confidence": row.get("confidence") or "medium", "raw": None, "relevant": True,
        })
        migrated = self.repository._update(
            self.repository._insight_key(owner, int(insight["id"])),
            lambda current: {
                **current,
                "created_at": str(row.get("created_at") or current["created_at"]),
                "reviewed_at": str(row["reviewed_at"]) if row.get("reviewed_at") else None,
                "email_status": str(row.get("email_status") or "pending"),
                "email_sent_at": str(row["email_sent_at"]) if row.get("email_sent_at") else None,
                "email_error": str(row["email_error"]) if row.get("email_error") else None,
            },
        )
        self.repository.mark_seen(owner, int(source["id"]), str(discovered["url"]), insight_id=int(migrated["id"]))
        self._record("insights", "migrated")

    def import_seen_db(self, row: dict[str, Any]) -> None:
        source = self.source_ids.get(int(row.get("source_id") or 0))
        url = str(row.get("url") or "").strip()
        if not source or not url:
            self._record("seen_urls", "skipped")
            return
        added = self.repository.mark_seen(str(source["owner_name"]), int(source["id"]), url)
        self._record("seen_urls", "migrated" if added else "duplicate")

    def import_notification_mode(self, rows: list[dict[str, Any]]) -> None:
        mode = next((str(row.get("value")) for row in rows if row.get("key") == "email_notification_mode"), None)
        if mode not in {"automatic", "manual"}:
            self._record("notification_settings", "skipped")
            return
        for account in self.repository.list_accounts(limit=10000):
            self.repository.set_notification_mode(str(account["name"]), mode)
        self._record("notification_settings", "migrated")

    def import_seen_json(self, directory: Path) -> None:
        path = directory / "seen_url_records.json"
        if not path.exists():
            self._record("seen_urls", "skipped")
            return
        try:
            entries = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            self.errors.append(f"seen URL JSON: {exc}")
            self._record("seen_urls", "failed")
            return
        source_by_url = {item["url"]: item for item in self.source_ids.values()}
        for url, payload in (entries.items() if isinstance(entries, dict) else []):
            if not isinstance(payload, dict):
                self._record("seen_urls", "skipped")
                continue
            source_url = payload.get("parent_url") or payload.get("feed_url") or payload.get("api_url")
            source = source_by_url.get(str(source_url))
            if not source:
                self._record("seen_urls", "skipped")
                continue
            added = self.repository.mark_seen(str(source["owner_name"]), int(source["id"]), str(url), baseline=bool(payload.get("baseline")))
            self._record("seen_urls", "migrated" if added else "duplicate")

    def import_postgres(self, dsn: str) -> None:
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError("Install psycopg temporarily to use --postgres-dsn; it is not a service dependency.") from exc
        with psycopg.connect(dsn, row_factory=dict_row) as connection:
            for table, handler in (
                ("companies", self.import_company), ("sources", self.import_source),
                ("notification_recipients", self.import_recipient), ("monitor_runs", self.import_run),
                ("discovered_urls", self.import_discovered), ("summaries", self.import_summary),
                ("seen_urls", self.import_seen_db),
            ):
                try:
                    rows = connection.execute(f"SELECT * FROM {table}").fetchall()
                except Exception as exc:
                    self.errors.append(f"{table}: {exc}")
                    self._record(table, "failed")
                    continue
                for row in rows:
                    handler(dict(row))
            try:
                self.import_notification_mode([dict(row) for row in connection.execute("SELECT * FROM app_settings").fetchall()])
            except Exception as exc:
                self.errors.append(f"app_settings: {exc}")
                self._record("notification_settings", "failed")

    def report(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "migrated": {key: value for key, value in self.counts.items() if key.endswith("_migrated")},
            "skipped": {key: value for key, value in self.counts.items() if key.endswith("_skipped")},
            "duplicates": {key: value for key, value in self.counts.items() if key.endswith("_duplicate")},
            "failed": {key: value for key, value in self.counts.items() if key.endswith("_failed")},
            "errors": self.errors,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate legacy Sentinel Actalyst data to S3.")
    parser.add_argument("--legacy-json-dir", type=Path, default=Path("mysignal/data"))
    parser.add_argument("--postgres-dsn", help="Optional legacy PostgreSQL DSN; requires temporary psycopg installation.")
    parser.add_argument("--report", type=Path, default=Path("migration-report.json"))
    args = parser.parse_args()
    settings = get_settings()
    settings.require_storage()
    migration = Migration(S3Repository(get_storage(settings), prefix=settings.storage_prefix))
    migration.import_accounts_json(args.legacy_json_dir)
    if args.postgres_dsn:
        migration.import_postgres(args.postgres_dsn)
    migration.import_seen_json(args.legacy_json_dir)
    args.report.write_text(json.dumps(migration.report(), indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
