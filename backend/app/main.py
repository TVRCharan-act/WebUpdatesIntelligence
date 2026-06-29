from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.observability import log_health_event
from backend.app.routers import companies, email, health, monitor, runs, sources, storage, tasks


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_health_event(
        event_type="lifecycle",
        service="backend",
        action="startup",
        status="ok",
    )
    try:
        yield
    finally:
        log_health_event(
            event_type="lifecycle",
            service="backend",
            action="shutdown",
            status="ok",
        )


app = FastAPI(
    title="Website Monitor API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_request_timing(request, call_next):
    started_at = perf_counter()
    status_code = 500

    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    except Exception as exc:
        duration_ms = (perf_counter() - started_at) * 1000
        log_health_event(
            event_type="backend_request",
            service="backend",
            action=f"{request.method} {request.url.path}",
            status="error",
            duration_ms=duration_ms,
            metadata={
                "method": request.method,
                "path": request.url.path,
                "query": str(request.url.query),
                "error": str(exc),
            },
        )
        raise
    finally:
        duration_ms = (perf_counter() - started_at) * 1000
        log_health_event(
            event_type="backend_request",
            service="backend",
            action=f"{request.method} {request.url.path}",
            status="ok" if status_code < 500 else "error",
            duration_ms=duration_ms,
            metadata={
                "method": request.method,
                "path": request.url.path,
                "query": str(request.url.query),
                "status_code": status_code,
            },
        )


app.include_router(health.router)
app.include_router(companies.router)
app.include_router(email.router)
app.include_router(sources.router)
app.include_router(storage.router)
app.include_router(runs.router)
app.include_router(monitor.router)
app.include_router(tasks.router)
