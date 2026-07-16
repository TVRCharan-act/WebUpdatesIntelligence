"""Deleting a company/source must leave nothing behind in the bucket.

These guard the key-based deletion in ``S3Repository._delete_prefix``: cleanup
must not depend on reconstructing a key from a record field, so even a record
missing that field is removed rather than orphaned.
"""

from __future__ import annotations

from backend.app.repository import S3Repository
from backend.app.storage import InMemoryJsonStorage

from .conftest import make_source


def _account_only(storage: InMemoryJsonStorage, baseline: set[str]) -> list[str]:
    """Keys created since ``baseline`` (i.e. everything but the account profile)."""
    return sorted(key for key in storage._objects if key not in baseline)


def test_delete_company_removes_every_stored_object(
    repo: S3Repository, storage: InMemoryJsonStorage, owner: str
) -> None:
    baseline = set(storage._objects)  # just the account profile

    source = make_source(repo, owner, baseline=False)
    sid = int(source["id"])
    cid = int(source["company_id"])

    repo.create_recipient(owner, cid, "alerts@acme.example")
    job = repo.create_job(owner, operation="check", company_id=cid, source_id=sid)
    run = repo.create_run(owner, source, "check", job["job_id"])
    for url in ("https://a.example", "https://b.example?q=1", "https://c.example#frag"):
        repo.mark_seen(owner, sid, url)
        repo.record_discovered_url(owner, source, int(run["id"]), url, {"title": "x"})

    assert _account_only(storage, baseline), "expected objects to have been created"

    repo.delete_company(cid, owner)

    assert _account_only(storage, baseline) == [], "orphaned objects remain after delete"
    assert repo._account_key(owner) in storage._objects, "account profile must survive"


def test_delete_source_removes_seen_record_missing_its_url_field(
    repo: S3Repository, storage: InMemoryJsonStorage, owner: str
) -> None:
    """A seen record without a ``url`` field must still be deleted.

    The previous implementation re-hashed ``record['url']`` to rebuild the key,
    so such a record was silently skipped and orphaned. Key-based deletion fixes
    it. This is the specific regression the delete rework addressed.
    """
    source = make_source(repo, owner, baseline=False)
    sid = int(source["id"])

    repo.mark_seen(owner, sid, "https://a.example")
    # A corrupted / partially written seen record with no 'url' key.
    orphan = f"{repo._account_prefix(owner)}/seen/{sid}/deadbeef.json"
    storage.put_json(orphan, {"record_type": "seen_url", "source_id": sid})

    repo.delete_source(sid, owner)

    assert orphan not in storage._objects
    seen_prefix = f"{repo._account_prefix(owner)}/seen/{sid}/"
    assert not any(key.startswith(seen_prefix) for key in storage._objects)
    assert repo._source_key(owner, sid) not in storage._objects
    assert repo._index_key("source", sid) not in storage._objects


def test_delete_company_scopes_to_owner(repo: S3Repository, owner: str) -> None:
    """Another account's company with the same id is never touched."""
    other = "beta"
    repo.create_account(other, "hash", "customer")
    mine = make_source(repo, owner, baseline=False)
    theirs = make_source(repo, other, baseline=False)

    repo.delete_company(int(mine["company_id"]), owner)

    # The other account's company and source are still intact.
    assert repo.get_company(int(theirs["company_id"]), other)["id"] == theirs["company_id"]
    assert repo.get_source(int(theirs["id"]), other)["id"] == theirs["id"]
