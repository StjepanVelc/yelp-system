from fastapi import FastAPI, BackgroundTasks
from app.db.session import engine
from app.core.logger import get_logger

log = get_logger("ingestion-service")
app = FastAPI(title="Ingestion Service", version="1.0.0")


@app.on_event("startup")
def create_tables():
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


