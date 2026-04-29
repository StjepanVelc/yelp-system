from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import business, recommendation
from app.logger import get_logger
import os

log = get_logger("api-gateway")
app = FastAPI(title="API Gateway", version="1.0.0")

_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(business.router, prefix="/businesses", tags=["businesses"])
app.include_router(recommendation.router, prefix="/recommendations", tags=["recommendations"])
app.include_router(business.router, prefix="/api/businesses", tags=["businesses"])
app.include_router(recommendation.router, prefix="/api/recommendations", tags=["recommendations"])


@app.on_event("startup")
def startup():
    log.info("API Gateway starting up")


@app.get("/")
def root():
    return {"service": "api-gateway", "status": "running", "version": "1.0.0"}


@app.get("/health")
def health():
    return {"status": "ok"}
