from uuid import uuid4

from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.responses import Response
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from app.db.session import engine
from app.core.logger import get_logger
from app.core.observability import (
    init_tracing,
    metrics_response,
    monotonic_now,
    record_request_metrics,
    reset_correlation_id,
    set_correlation_id,
)

log = get_logger("ingestion-service")
SERVICE_NAME = "ingestion-service"
app = FastAPI(title="Ingestion Service", version="1.0.0")


@app.middleware("http")
async def correlation_and_metrics_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid4())
    token = set_correlation_id(correlation_id)
    started = monotonic_now()
    response: Response | None = None
    tracer = trace.get_tracer(SERVICE_NAME)

    try:
        with tracer.start_as_current_span(f"{request.method} {request.url.path}") as span:
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.route", request.url.path)
            span.set_attribute("correlation_id", correlation_id)

            try:
                response = await call_next(request)
                if response is None:
                    raise RuntimeError("call_next returned no response")

                span.set_attribute("http.status_code", response.status_code)
                response.headers["X-Correlation-ID"] = correlation_id
                return response
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR))
                raise
    finally:
        elapsed_seconds = monotonic_now() - started
        status_code = response.status_code if response is not None else 500
        record_request_metrics(
            SERVICE_NAME,
            request.method,
            request.url.path,
            status_code,
            elapsed_seconds,
        )
        log.info(
            "http_request",
            extra={
                "service": SERVICE_NAME,
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "latency_ms": round(elapsed_seconds * 1000, 2),
            },
        )
        reset_correlation_id(token)


@app.on_event("startup")
def create_tables():
    init_tracing(SERVICE_NAME)
    from app.models import Base
    Base.metadata.create_all(bind=engine)
    log.info("Ingestion service started — tables verified/created")


@app.post("/ingest/all")
def trigger_ingest_all(background_tasks: BackgroundTasks):
    log.info("Triggered: ingest all datasets")
    from app.service.ingestion_service import ingest_all
    background_tasks.add_task(ingest_all)
    return {"status": "ingestion started", "datasets": ["businesses", "users", "reviews", "tips", "checkins"]}


@app.post("/ingest/businesses")
def trigger_ingest_businesses(background_tasks: BackgroundTasks):
    log.info("Triggered: ingest businesses")
    from app.service.ingestion_service import ingest_businesses
    from app.db.session import SessionLocal
    def run():
        s = SessionLocal()
        try: ingest_businesses(s)
        finally: s.close()
    background_tasks.add_task(run)
    return {"status": "started", "dataset": "businesses"}


@app.post("/ingest/reviews")
def trigger_ingest_reviews(background_tasks: BackgroundTasks):
    log.info("Triggered: ingest reviews")
    from app.service.ingestion_service import ingest_reviews
    from app.db.session import SessionLocal
    def run():
        s = SessionLocal()
        try: ingest_reviews(s)
        finally: s.close()
    background_tasks.add_task(run)
    return {"status": "started", "dataset": "reviews"}


@app.post("/ingest/users")
def trigger_ingest_users(background_tasks: BackgroundTasks):
    log.info("Triggered: ingest users")
    from app.service.ingestion_service import ingest_users
    from app.db.session import SessionLocal
    def run():
        s = SessionLocal()
        try: ingest_users(s)
        finally: s.close()
    background_tasks.add_task(run)
    return {"status": "started", "dataset": "users"}


@app.post("/ingest/tips")
def trigger_ingest_tips(background_tasks: BackgroundTasks):
    log.info("Triggered: ingest tips")
    from app.service.ingestion_service import ingest_tips
    from app.db.session import SessionLocal
    def run():
        s = SessionLocal()
        try: ingest_tips(s)
        finally: s.close()
    background_tasks.add_task(run)
    return {"status": "started", "dataset": "tips"}


@app.post("/ingest/checkins")
def trigger_ingest_checkins(background_tasks: BackgroundTasks):
    log.info("Triggered: ingest checkins")
    from app.service.ingestion_service import ingest_checkins
    from app.db.session import SessionLocal
    def run():
        s = SessionLocal()
        try: ingest_checkins(s)
        finally: s.close()
    background_tasks.add_task(run)
    return {"status": "started", "dataset": "checkins"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/cache/stats")
def cache_stats():
    from app.core.cache import cache_invalidator
    return cache_invalidator.stats.snapshot()


@app.get("/metrics")
def metrics() -> Response:
    return metrics_response()


