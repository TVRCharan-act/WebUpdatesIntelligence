from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app import crud, schemas
from backend.app.auth import CurrentUser
from backend.app.database import get_db
from backend.app.workers.monitor_worker import baseline_source_task, monitor_source_task
from mysignal.discovery.api_discovery import (
    discover_js_bundle_sources,
    normalize_api_url,
)
from mysignal.discovery.page_links import extract_page_links, normalize_page_url
from mysignal.filters.content_filter import is_content_candidate
from mysignal.monitoring.inventory_store import load_seen_url_records
from mysignal.workflows.api_monitor import api_endpoint_content_urls
from mysignal.workflows.feed_monitor import feed_entry_urls, normalize_feed_url
from mysignal.workflows.parent_monitor import (
    api_content_links_for_parent,
    parent_js_bundle_sources,
    parent_trace_js,
)


router = APIRouter(
    prefix="/sources",
    tags=["sources"],
)

DbSession = Annotated[Session, Depends(get_db)]


def _owner_filter(user: CurrentUser) -> str | None:
    return None if user.role == "admin" else user.name


@router.get(
    "",
    response_model=list[schemas.SourceRead],
)
def list_sources(db: DbSession, user: CurrentUser) -> list[schemas.SourceRead]:
    return crud.list_sources(db, owner_name=_owner_filter(user))


@router.get(
    "/{source_id}",
    response_model=schemas.SourceRead,
)
def get_source(source_id: int, db: DbSession, user: CurrentUser) -> schemas.SourceRead:
    source = crud.get_source(db, source_id, owner_name=_owner_filter(user))
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found.",
        )
    return source


@router.get(
    "/{source_id}/runs",
    response_model=list[schemas.MonitorRunRead],
)
def list_source_monitor_runs(
    source_id: int,
    db: DbSession,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=500)] = 20,
) -> list[schemas.MonitorRunRead]:
    if crud.get_source(db, source_id, owner_name=_owner_filter(user)) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found.",
        )
    return crud.list_source_monitor_runs(db, source_id, limit)


@router.get(
    "/{source_id}/discovered-urls",
    response_model=list[schemas.DiscoveredUrlRead],
)
def list_source_discovered_urls(
    source_id: int,
    db: DbSession,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> list[schemas.DiscoveredUrlRead]:
    if crud.get_source(db, source_id, owner_name=_owner_filter(user)) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found.",
        )
    return crud.list_source_discovered_urls(db, source_id, limit)


@router.get(
    "/{source_id}/summaries",
    response_model=list[schemas.SummaryRead],
)
def list_source_summaries(
    source_id: int,
    db: DbSession,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=500)] = 20,
) -> list[schemas.SummaryRead]:
    if crud.get_source(db, source_id, owner_name=_owner_filter(user)) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found.",
        )
    return crud.list_source_summaries(db, source_id, limit)


@router.get(
    "/{source_id}/discovery-preview",
    response_model=schemas.SourceDiscoveryPreviewRead,
)
def preview_source_discovery(
    source_id: int,
    db: DbSession,
    user: CurrentUser,
) -> schemas.SourceDiscoveryPreviewRead:
    source = crud.get_source(db, source_id, owner_name=_owner_filter(user))
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found.",
        )

    try:
        seen_records = load_seen_url_records()

        if source.strategy == "feed":
            source_url = normalize_feed_url(source.url)
            raw_urls = feed_entry_urls(source_url)
            preview_urls = [
                schemas.DiscoveryPreviewUrl(
                    url=normalize_page_url(url),
                    already_seen=normalize_page_url(url) in seen_records,
                    source="feed",
                )
                for url in raw_urls
            ]
        elif source.strategy == "api":
            source_url = normalize_api_url(source.url)
            raw_urls = api_endpoint_content_urls(source_url)
            preview_urls = [
                schemas.DiscoveryPreviewUrl(
                    url=normalize_page_url(url),
                    already_seen=normalize_page_url(url) in seen_records,
                    source="api",
                )
                for url in raw_urls
            ]
        else:
            source_url = normalize_page_url(source.url)
            js_bundle_sources = parent_js_bundle_sources(source)

            if parent_trace_js(source):
                detected_js_bundle_sources = discover_js_bundle_sources(
                    source_url,
                    script_sources=js_bundle_sources,
                )

                if detected_js_bundle_sources != js_bundle_sources:
                    source = crud.update_source_js_bundle_sources(
                        db,
                        source,
                        detected_js_bundle_sources,
                    )
                    js_bundle_sources = detected_js_bundle_sources

            page_links = extract_page_links(source_url)
            preview_urls = [
                schemas.DiscoveryPreviewUrl(
                    url=normalize_page_url(link.url),
                    already_seen=normalize_page_url(link.url) in seen_records,
                    source=link.source,
                    region=link.region,
                    label=link.label,
                )
                for link in page_links.links
                if is_content_candidate(link.url)
            ]

            if parent_trace_js(source):
                for url in api_content_links_for_parent(
                    source_url,
                    js_bundle_sources=js_bundle_sources,
                ):
                    normalized_url = normalize_page_url(url)
                    preview_urls.append(
                        schemas.DiscoveryPreviewUrl(
                            url=normalized_url,
                            already_seen=normalized_url in seen_records,
                            source="js-trace",
                        )
                    )

            raw_urls = [link.url for link in page_links.links]

        deduped_urls = {}
        for item in preview_urls:
            deduped_urls.setdefault(item.url, item)

        urls = sorted(deduped_urls.values(), key=lambda item: item.url)
        already_seen_count = sum(1 for item in urls if item.already_seen)

        return schemas.SourceDiscoveryPreviewRead(
            source_id=source.id,
            source_url=source.url,
            strategy=source.strategy,
            status="ok",
            raw_url_count=len(set(raw_urls)),
            content_url_count=len(urls),
            already_seen_count=already_seen_count,
            new_candidate_count=len(urls) - already_seen_count,
            urls=urls[:200],
            message=(
                "No content URL candidates were found."
                if not urls
                else None
            ),
        )
    except Exception as exc:
        return schemas.SourceDiscoveryPreviewRead(
            source_id=source.id,
            source_url=source.url,
            strategy=source.strategy,
            status="error",
            message=str(exc),
        )


@router.post(
    "",
    response_model=schemas.SourceRead,
    status_code=status.HTTP_201_CREATED,
)
def create_source(
    source: schemas.SourceCreate,
    db: DbSession,
    user: CurrentUser,
) -> schemas.SourceRead:
    if crud.get_company(db, source.company_id, owner_name=_owner_filter(user)) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found.",
        )

    try:
        return crud.create_source(db, source)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source could not be created.",
        ) from exc


@router.patch(
    "/{source_id}",
    response_model=schemas.SourceRead,
)
def update_source(
    source_id: int,
    source: schemas.SourceUpdate,
    db: DbSession,
    user: CurrentUser,
) -> schemas.SourceRead:
    db_source = crud.get_source(db, source_id, owner_name=_owner_filter(user))
    if db_source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found.",
        )

    try:
        return crud.update_source(db, db_source, source)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source could not be updated.",
        ) from exc


@router.delete(
    "/{source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_source(source_id: int, db: DbSession, user: CurrentUser) -> None:
    db_source = crud.get_source(db, source_id, owner_name=_owner_filter(user))
    if db_source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found.",
        )

    crud.delete_source(db, db_source)


@router.post(
    "/{source_id}/baseline",
    response_model=schemas.QueuedTaskResponse,
)
def run_source_baseline(
    source_id: int,
    db: DbSession,
    user: CurrentUser,
) -> schemas.QueuedTaskResponse:
    if crud.get_source(db, source_id, owner_name=_owner_filter(user)) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found.",
        )

    task = baseline_source_task.delay(source_id)
    return schemas.QueuedTaskResponse(
        task_id=task.id,
        status="queued",
    )


@router.post(
    "/{source_id}/run",
    response_model=schemas.QueuedTaskResponse,
)
def run_source_monitor(
    source_id: int,
    db: DbSession,
    user: CurrentUser,
) -> schemas.QueuedTaskResponse:
    if crud.get_source(db, source_id, owner_name=_owner_filter(user)) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found.",
        )

    task = monitor_source_task.delay(source_id)
    return schemas.QueuedTaskResponse(
        task_id=task.id,
        status="queued",
    )
