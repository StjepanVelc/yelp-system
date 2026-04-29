from typing import Iterable

import jwt
from fastapi import HTTPException, Request

from app.clients import user_status_client
from app.config import settings


def _auth_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def parse_bearer_token(authorization_header: str | None) -> str:
    if not authorization_header:
        raise _auth_error(401, "no_token", "Missing Authorization header")

    parts = authorization_header.strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
        raise _auth_error(401, "malformed_authorization_header", "Malformed Authorization header")

    return parts[1]


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            leeway=settings.jwt_leeway_seconds,
        )
    except jwt.ExpiredSignatureError as exc:
        raise _auth_error(401, "expired_token", "Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise _auth_error(401, "invalid_token", "Invalid token") from exc

    return payload


def _extract_roles(payload: dict) -> set[str]:
    raw_roles = payload.get(settings.jwt_roles_claim)
    if raw_roles is None:
        return set()
    if isinstance(raw_roles, str):
        return {raw_roles}
    if isinstance(raw_roles, list):
        return {str(role) for role in raw_roles if role}
    return set()


def ensure_roles(payload: dict, required_roles: Iterable[str]) -> None:
    required = {role for role in required_roles if role}
    if not required:
        return

    roles = _extract_roles(payload)
    if not roles:
        raise _auth_error(403, "missing_role", "Token has no roles claim")

    if roles.isdisjoint(required):
        raise _auth_error(403, "insufficient_role", "Token role is not allowed for this resource")


async def ensure_user_is_active(payload: dict) -> None:
    user_id = payload.get("sub")
    if not user_id:
        raise _auth_error(401, "invalid_token", "Token is missing subject claim")

    try:
        status = await user_status_client.get_user_status(str(user_id))
    except Exception as exc:
        raise _auth_error(403, "user_status_unavailable", "Could not verify user status") from exc

    is_deleted = bool(status.get("deleted")) or bool(status.get("deleted_at"))
    is_active = bool(status.get("active", True))
    if not is_active or is_deleted:
        raise _auth_error(403, "inactive_or_deleted_user", "User is inactive or deleted")


def require_roles(required_roles: Iterable[str]):
    async def _dependency(request: Request) -> dict:
        token = parse_bearer_token(request.headers.get("Authorization"))
        payload = decode_token(token)
        ensure_roles(payload, required_roles)
        await ensure_user_is_active(payload)
        request.state.auth = payload
        return payload

    return _dependency
