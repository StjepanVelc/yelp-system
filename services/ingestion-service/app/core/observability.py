import time
import os
from contextvars import ContextVar

from fastapi import Response
from opentelemetry import trace
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest


correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="-")

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["service", "method", "path", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["service", "method", "path"],
)

_TRACING_INITIALIZED = False


def get_correlation_id() -> str:
    return correlation_id_var.get()


def set_correlation_id(value: str):
    return correlation_id_var.set(value)


def reset_correlation_id(token) -> None:
    correlation_id_var.reset(token)


def record_request_metrics(service: str, method: str, path: str, status_code: int, elapsed_seconds: float) -> None:
    REQUEST_COUNT.labels(
        service=service,
        method=method,
        path=path,
        status_code=str(status_code),
    ).inc()
    REQUEST_LATENCY.labels(service=service, method=method, path=path).observe(elapsed_seconds)


def metrics_response() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


def monotonic_now() -> float:
    return time.perf_counter()


def init_tracing(service_name: str) -> None:
    global _TRACING_INITIALIZED
    if _TRACING_INITIALIZED:
        return

    if os.getenv("OTEL_TRACES_ENABLED", "false").strip().lower() not in {"1", "true", "yes", "on"}:
        return

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4317")
    insecure = os.getenv("OTEL_EXPORTER_OTLP_INSECURE", "true").strip().lower() in {"1", "true", "yes", "on"}

    os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except Exception:
        return

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    exporter = OTLPSpanExporter(endpoint=endpoint, insecure=insecure)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _TRACING_INITIALIZED = True
