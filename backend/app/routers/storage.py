from typing import Any, Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app import models, schemas
from backend.app.database import get_db
from mysignal.discovery.api_discovery import normalize_api_url
from mysignal.discovery.page_links import normalize_page_url
from mysignal.monitoring.inventory_store import load_seen_url_records
from mysignal.workflows.feed_monitor import normalize_feed_url


router = APIRouter(
    prefix="/storage",
    tags=["storage"],
)

DbSession = Annotated[Session, Depends(get_db)]


def _source_storage_key(source: models.Source) -> tuple[str, str]:
    if source.strategy == "feed":
        return "feed_url", normalize_feed_url(source.url)

    if source.strategy == "api":
        return "api_url", normalize_api_url(source.url)

    return "parent_url", normalize_page_url(source.url)


def _json_records_for_source(
    records: dict[str, Any],
    source: models.Source,
) -> list[schemas.StoredUrlRead]:
    record_key, source_url = _source_storage_key(source)
    stored_urls = []

    for url, payload in records.items():
        if not isinstance(payload, dict):
            continue

        record_source_url = payload.get(record_key)
        if not isinstance(record_source_url, str):
            continue

        if record_key == "feed_url":
            normalized_record_source = normalize_feed_url(record_source_url)
        elif record_key == "api_url":
            normalized_record_source = normalize_api_url(record_source_url)
        else:
            normalized_record_source = normalize_page_url(record_source_url)

        if normalized_record_source != source_url:
            continue

        stored_urls.append(
            schemas.StoredUrlRead(
                url=str(payload.get("url") or url),
                source="json",
                first_seen_at=(
                    str(payload["first_seen_at"])
                    if payload.get("first_seen_at")
                    else None
                ),
                payload=payload,
            )
        )

    return sorted(stored_urls, key=lambda item: item.url)


def _database_records_for_source(source: models.Source) -> list[schemas.StoredUrlRead]:
    return [
        schemas.StoredUrlRead(
            url=discovered_url.url,
            source="database",
            discovered_at=discovered_url.discovered_at,
            monitor_run_id=discovered_url.monitor_run_id,
            payload=discovered_url.payload,
        )
        for discovered_url in sorted(
            source.discovered_urls,
            key=lambda item: (item.discovered_at, item.id),
            reverse=True,
        )
    ]


def _merge_records(
    json_records: list[schemas.StoredUrlRead],
    database_records: list[schemas.StoredUrlRead],
) -> list[schemas.StoredUrlRead]:
    merged: dict[str, schemas.StoredUrlRead] = {}

    for record in database_records:
        merged[record.url] = record

    for record in json_records:
        merged.setdefault(record.url, record)

    return sorted(merged.values(), key=lambda item: item.url)


@router.get(
    "/urls",
    response_model=schemas.StoredUrlsResponse,
)
def list_stored_urls(db: DbSession) -> schemas.StoredUrlsResponse:
    try:
        seen_records = load_seen_url_records()
        status = "ok"
        message = None
    except Exception as exc:
        seen_records = {}
        status = "warning"
        message = f"Could not read JSON stored URLs: {exc}"

    companies = list(
        db.scalars(
            select(models.Company)
            .options(
                selectinload(models.Company.sources).selectinload(
                    models.Source.discovered_urls
                )
            )
            .order_by(models.Company.name)
        )
    )

    response_companies = []
    for company in companies:
        response_sources = []

        for source in sorted(company.sources, key=lambda item: item.id):
            json_records = _json_records_for_source(seen_records, source)
            database_records = _database_records_for_source(source)
            stored_urls = _merge_records(json_records, database_records)
            source_message = None

            if not stored_urls:
                source_message = (
                    "No stored URLs found for this source. Run a baseline or monitor, "
                    "or check whether extraction/filtering found any content URLs."
                )

            response_sources.append(
                schemas.SourceStoredUrlsRead(
                    id=source.id,
                    company_id=source.company_id,
                    url=source.url,
                    strategy=source.strategy,
                    stored_urls=stored_urls,
                    json_url_count=len(json_records),
                    database_url_count=len(database_records),
                    message=source_message,
                )
            )

        response_companies.append(
            schemas.CompanyStoredUrlsRead(
                id=company.id,
                name=company.name,
                sources=response_sources,
            )
        )

    return schemas.StoredUrlsResponse(
        status=status,
        message=message,
        companies=response_companies,
    )
