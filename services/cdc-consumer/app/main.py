import json
import logging

from kafka import KafkaConsumer

from app.cache import RedisInvalidator
from app.config import settings
from app.event_parser import normalize_debezium_event


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("cdc-consumer")


def _handle_business_event(invalidator: RedisInvalidator, op: str, business_id: str, changed_fields: list[str]) -> None:
    details_key = f"yelp:{settings.app_env}:business:details:{business_id}:v1"
    recommendation_pattern = f"yelp:{settings.app_env}:recommendation:by_business:{business_id}:*:v1"
    cities_key = f"yelp:{settings.app_env}:business:cities:all:v1"

    invalidator.delete_exact(details_key)
    invalidator.delete_pattern(recommendation_pattern)

    # Some pgoutput update events may not provide full before/after diff context.
    # If changed_fields is empty on update, treat it as unknown and invalidate cities conservatively.
    city_affecting_update = "city" in changed_fields or "is_open" in changed_fields or not changed_fields
    if op in {"c", "d"} or city_affecting_update:
        invalidator.delete_exact(cities_key)


def _handle_review_event(invalidator: RedisInvalidator, business_id: str) -> None:
    recommendation_pattern = f"yelp:{settings.app_env}:recommendation:by_business:{business_id}:*:v1"
    invalidator.delete_pattern(recommendation_pattern)


def run() -> None:
    invalidator = RedisInvalidator(settings.redis_url, settings.redis_timeout_seconds)
    invalidator.ping()

    topics = [
        f"{settings.cdc_topic_prefix}.public.businesses",
        f"{settings.cdc_topic_prefix}.public.reviews",
    ]

    consumer = KafkaConsumer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.cdc_consumer_group,
        auto_offset_reset=settings.cdc_auto_offset_reset,
        enable_auto_commit=True,
        value_deserializer=lambda b: json.loads(b.decode("utf-8")) if b else None,
    )
    consumer.subscribe(topics)

    log.info(
        "cdc_consumer_started bootstrap=%s topic_prefix=%s group=%s",
        settings.kafka_bootstrap_servers,
        settings.cdc_topic_prefix,
        settings.cdc_consumer_group,
    )

    while True:
        records = consumer.poll(timeout_ms=settings.cdc_poll_timeout_ms)
        for _partition, messages in records.items():
            for message in messages:
                value = message.value
                if not isinstance(value, dict):
                    continue

                event = normalize_debezium_event(value, message.topic)
                if event is None:
                    continue

                if event.op == "r":
                    # Snapshot/read events are ignored in MVP to avoid backfill noise invalidations.
                    continue

                if event.table == "businesses" and event.entity_id:
                    _handle_business_event(
                        invalidator=invalidator,
                        op=event.op,
                        business_id=event.entity_id,
                        changed_fields=event.changed_fields,
                    )
                    continue

                if event.table == "reviews" and event.business_id:
                    _handle_review_event(invalidator=invalidator, business_id=event.business_id)


if __name__ == "__main__":
    run()
