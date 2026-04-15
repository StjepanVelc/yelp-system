from sqlalchemy import text
from tqdm import tqdm
from app.db.session import SessionLocal
from app.loaders.json_loader import (
    load_businesses,
    load_reviews,
    load_users,
    load_tips,
    load_checkins,
)
from app.core.config import settings
from app.core.logger import get_logger

log = get_logger("ingestion-service")

BATCH_SIZE = 1000


# ─── Business ────────────────────────────────────────────────────────────────

def ingest_businesses(session) -> int:
    return _ingest_stream(
        session,
        load_businesses(settings.data_path),
        "businesses",
        desc="Ingesting businesses",
        insert_sql="""
            INSERT INTO businesses
                (id, name, address, city, state, postal_code, latitude, longitude,
                 stars, review_count, is_open, categories)
            VALUES
                (:id, :name, :address, :city, :state, :postal_code, :latitude, :longitude,
                 :stars, :review_count, :is_open, :categories)
            ON CONFLICT (id) DO NOTHING
        """,
    )


# ─── Review ──────────────────────────────────────────────────────────────────

def ingest_reviews(session) -> int:
    return _ingest_stream(
        session,
        load_reviews(settings.data_path),
        "reviews",
        desc="Ingesting reviews",
        insert_sql="""
            INSERT INTO reviews (review_id, user_id, business_id, stars, useful, funny, cool, text, date)
            VALUES (:review_id, :user_id, :business_id, :stars, :useful, :funny, :cool, :text, :date)
            ON CONFLICT (review_id) DO NOTHING
        """,
    )


# ─── User ────────────────────────────────────────────────────────────────────

def ingest_users(session) -> int:
    return _ingest_stream(
        session,
        load_users(settings.data_path),
        "users",
        desc="Ingesting users",
        insert_sql="""
            INSERT INTO users
                (user_id, name, review_count, yelping_since, useful, funny, cool, fans, average_stars, elite)
            VALUES
                (:user_id, :name, :review_count, :yelping_since, :useful, :funny, :cool, :fans, :average_stars, :elite)
            ON CONFLICT (user_id) DO NOTHING
        """,
    )


# ─── Tip ─────────────────────────────────────────────────────────────────────

def ingest_tips(session) -> int:
    return _ingest_stream(
        session,
        load_tips(settings.data_path),
        "tips",
        desc="Ingesting tips",
        insert_sql="""
            INSERT INTO tips (user_id, business_id, text, date, compliment_count)
            VALUES (:user_id, :business_id, :text, :date, :compliment_count)
        """,
    )


# ─── Checkin ─────────────────────────────────────────────────────────────────

def ingest_checkins(session) -> int:
    return _ingest_stream(
        session,
        load_checkins(settings.data_path),
        "checkins",
        desc="Ingesting checkins",
        insert_sql="""
            INSERT INTO checkins (business_id, date)
            VALUES (:business_id, :date)
        """,
    )


# ─── Full ingest ─────────────────────────────────────────────────────────────

def ingest_all() -> dict:
    log.info("Starting full ingestion of all datasets")
    session = SessionLocal()
    results = {}
    try:
        results["businesses"] = ingest_businesses(session)
        results["users"] = ingest_users(session)
        results["reviews"] = ingest_reviews(session)
        results["tips"] = ingest_tips(session)
        results["checkins"] = ingest_checkins(session)
    finally:
        session.close()
    log.info("Full ingestion complete: %s", results)
    return results


# ─── Helper ──────────────────────────────────────────────────────────────────

def _ingest_stream(session, stream, name: str, desc: str, insert_sql: str) -> int:
    log.info("Starting ingestion: %s", name)
    batch = []
    total = 0
    try:
        for record in tqdm(stream, desc=desc):
            batch.append(record)
            if len(batch) >= BATCH_SIZE:
                _execute_batch(session, insert_sql, batch)
                total += len(batch)
                batch.clear()
        if batch:
            _execute_batch(session, insert_sql, batch)
            total += len(batch)
    except Exception as e:
        session.rollback()
        log.error("Error during %s ingestion at record ~%d: %s", name, total, e)
        raise RuntimeError(f"Failed during {name} ingestion: {e}") from e
    log.info("Finished %s — total records: %d", name, total)
    return total


def _execute_batch(session, sql: str, batch: list):
    session.execute(text(sql), batch)
    session.commit()


if __name__ == "__main__":
    ingest_all()