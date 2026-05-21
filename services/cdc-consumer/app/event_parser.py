from dataclasses import dataclass
from typing import Any


@dataclass
class NormalizedCdcEvent:
    table: str
    op: str
    entity_id: str | None
    business_id: str | None
    changed_fields: list[str]
    before: dict[str, Any] | None
    after: dict[str, Any] | None


def _as_payload(raw: dict[str, Any]) -> dict[str, Any]:
    payload = raw.get("payload")
    if isinstance(payload, dict):
        return payload
    return raw


def _extract_table(payload: dict[str, Any], topic: str) -> str | None:
    source = payload.get("source")
    if isinstance(source, dict):
        table = source.get("table")
        if isinstance(table, str) and table:
            return table

    parts = topic.split(".")
    if len(parts) >= 1:
        return parts[-1]
    return None


def _changed_fields(before: dict[str, Any] | None, after: dict[str, Any] | None) -> list[str]:
    if not isinstance(before, dict) or not isinstance(after, dict):
        return []

    changed: list[str] = []
    for key in set(before.keys()) | set(after.keys()):
        if before.get(key) != after.get(key):
            changed.append(str(key))
    return sorted(changed)


def normalize_debezium_event(raw: dict[str, Any], topic: str) -> NormalizedCdcEvent | None:
    payload = _as_payload(raw)
    op = payload.get("op")
    if not isinstance(op, str) or op not in {"c", "u", "d", "r"}:
        return None

    table = _extract_table(payload, topic)
    if table not in {"businesses", "reviews"}:
        return None

    before = payload.get("before") if isinstance(payload.get("before"), dict) else None
    after = payload.get("after") if isinstance(payload.get("after"), dict) else None

    entity_id: str | None = None
    business_id: str | None = None

    if table == "businesses":
        entity_id = (after or {}).get("id") or (before or {}).get("id")
    elif table == "reviews":
        entity_id = (after or {}).get("review_id") or (before or {}).get("review_id")
        business_id = (after or {}).get("business_id") or (before or {}).get("business_id")

    return NormalizedCdcEvent(
        table=table,
        op=op,
        entity_id=str(entity_id) if entity_id else None,
        business_id=str(business_id) if business_id else None,
        changed_fields=_changed_fields(before, after),
        before=before,
        after=after,
    )
