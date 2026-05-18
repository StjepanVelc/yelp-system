import threading
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from app.api.routes import router, user_router, cache_router
from app.core.logger import get_logger
from app.core.observability import (
    init_tracing,
    metrics_response,
    monotonic_now,
    record_request_metrics,
    reset_correlation_id,
    set_correlation_id,
)
import os

log = get_logger("business-service")
SERVICE_NAME = "business-service"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_tracing(SERVICE_NAME)
    log.info("Business service starting up")
    from app.grpc_server import serve
    grpc_server = serve(port=50051)
    t = threading.Thread(target=grpc_server.wait_for_termination, daemon=True)
    t.start()
    log.info("gRPC server started on port 50051")
    yield
    log.info("Business service shutting down")
    grpc_server.stop(grace=5)
    log.info("gRPC server stopped")


app = FastAPI(title="Business Service", version="1.0.0", lifespan=lifespan)

_origins = os.getenv("CORS_ORIGINS", "http://localhost:8000,http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/businesses")
app.include_router(user_router)
app.include_router(cache_router)


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


@app.get("/")
def root():
    return {"service": "business-service", "status": "running", "version": "1.0.0"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> Response:
    return metrics_response()

