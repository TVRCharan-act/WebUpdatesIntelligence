from fastapi import APIRouter

from backend.app import schemas
from backend.app.auth import AdminUser
from backend.app.services import crawler_lab

router = APIRouter(prefix="/admin/crawler-lab", tags=["admin"])


@router.post("/compare", response_model=schemas.CrawlerLabCompareResult)
def compare_crawlers(payload: schemas.CrawlerLabCompareRequest, user: AdminUser) -> schemas.CrawlerLabCompareResult:
    url = str(payload.url)
    results = crawler_lab.compare_providers(url)
    judge = crawler_lab.judge_crawlers(url, results)
    return schemas.CrawlerLabCompareResult(
        url=url,
        results=[
            schemas.CrawlerLabProviderResult(
                provider=result["provider"],
                success=result["success"],
                error=result["error"],
                total_latency_seconds=result["total_latency_seconds"],
                discovery_success=result["discovery"]["success"],
                discovery_latency_seconds=result["discovery"]["latency_seconds"],
                discovery_link_count=result["discovery"]["link_count"],
                discovery_error=result["discovery"]["error"],
                discovery_sample_links=result["discovery"]["sample_links"],
                content_success=result["content"]["success"],
                content_latency_seconds=result["content"]["latency_seconds"],
                content_title=result["content"]["title"],
                content_length=result["content"]["length"],
                content_snippet=result["content"]["snippet"],
                content_error=result["content"]["error"],
            )
            for result in results
        ],
        judge=schemas.CrawlerLabJudgeVerdict(**judge),
    )
