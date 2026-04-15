from fastapi import FastAPI
from app.api.routes import router
from app.core.logger import get_logger

log = get_logger("recommendation-service")
app = FastAPI(title="Recommendation Service", version="1.0.0")

app.include_router(router, prefix="/recommendations")


@app.on_event("startup")
def startup():
    log.info("Recommendation service starting up")


@app.get("/health")
def health():
    return {"status": "ok"}
