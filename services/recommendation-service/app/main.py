from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.core.logger import get_logger
import os

log = get_logger("recommendation-service")
app = FastAPI(title="Recommendation Service", version="1.0.0")

_origins = os.getenv("CORS_ORIGINS", "http://localhost:8000,http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/recommendations")


@app.on_event("startup")
def startup():
    log.info("Recommendation service starting up")


@app.get("/")
def root():
    return {"service": "recommendation-service", "status": "running", "version": "1.0.0"}


@app.get("/health")
def health():
    return {"status": "ok"}
