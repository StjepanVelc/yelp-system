from fastapi import FastAPI
from app.routes import business, recommendation
from app.logger import get_logger

log = get_logger("api-gateway")
app = FastAPI(title="API Gateway", version="1.0.0")

app.include_router(business.router, prefix="/businesses", tags=["businesses"])
app.include_router(recommendation.router, prefix="/recommendations", tags=["recommendations"])


@app.on_event("startup")
def startup():
    log.info("API Gateway starting up")


@app.get("/health")
def health():
    return {"status": "ok"}
