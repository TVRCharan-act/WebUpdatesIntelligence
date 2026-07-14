from fastapi import APIRouter

from backend.app import schemas
from backend.app.auth import CurrentUser, Repository


router = APIRouter(prefix="/storage", tags=["storage"])


def _owner_filter(user: CurrentUser) -> str | None:
    return None if user.role == "admin" else user.name


@router.get("/urls", response_model=schemas.StoredUrlsResponse)
def list_stored_urls(repository: Repository, user: CurrentUser) -> dict:
    companies = []
    for company in repository.list_companies(_owner_filter(user)):
        owner = str(company["owner_name"])
        sources = []
        for source in repository.list_sources(owner, company_id=int(company["id"])):
            discovered = repository.list_discovered_urls(owner, int(source["id"]), limit=500)
            stored = [
                {
                    "url": item["url"],
                    "source": "s3",
                    "first_seen_at": (repository.seen_record(owner, int(source["id"]), str(item["url"])) or {}).get("first_seen_at"),
                    "discovered_at": item.get("discovered_at"),
                    "monitor_run_id": item.get("monitor_run_id"),
                    "payload": item.get("payload"),
                }
                for item in discovered
            ]
            sources.append({
                "id": source["id"],
                "company_id": source["company_id"],
                "url": source["url"],
                "strategy": source["strategy"],
                "stored_urls": stored,
                "json_url_count": 0,
                "database_url_count": len(stored),
                "message": None,
            })
        companies.append({"id": company["id"], "name": company["name"], "sources": sources})
    return {"status": "ok", "message": "S3-backed authoritative URL state.", "companies": companies}
