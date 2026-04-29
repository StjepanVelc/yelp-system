import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router, user_router
from app.core.logger import get_logger
import os

log = get_logger("business-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
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


@app.get("/")
def root():
    return {"service": "business-service", "status": "running", "version": "1.0.0"}


@app.get("/health")
def health():
    return {"status": "ok"}

