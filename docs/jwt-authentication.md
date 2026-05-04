# JWT Authentication (API Gateway)

This document contains the detailed JWT authentication and authorization behavior implemented in the API Gateway.

## What is validated

All protected routes validate:

- Authorization header format (`Bearer <token>`)
- JWT signature + claims (`iss`, `aud`, `exp`, `sub`)
- Route-level required role
- Runtime user status (`active/deleted`) through the user-status service

## Response model

- `401`
  - no token
  - malformed authorization header
  - invalid token
  - expired token
- `403`
  - missing role
  - insufficient role
  - inactive/deleted user

## Expected JWT claims

```json
{
  "sub": "user-123",
  "iss": "yelp-auth",
  "aud": "yelp-api",
  "roles": ["business:read", "recommendation:read"],
  "iat": 1714370000,
  "exp": 1714373600
}
```

## Authorization header example

```bash
curl -H "Authorization: Bearer <JWT_TOKEN>" \
  "http://localhost:8000/businesses?city=Phoenix"
```

## Gateway JWT config (env)

Core JWT settings:

- `JWT_SECRET`
- `JWT_ALGORITHM`
- `JWT_ISSUER`
- `JWT_AUDIENCE`
- `JWT_LEEWAY_SECONDS`
- `JWT_ROLES_CLAIM`

Role mapping:

- `BUSINESS_REQUIRED_ROLES`
- `RECOMMENDATION_REQUIRED_ROLES`

User status runtime check:

- `USER_SERVICE_URL`
- `USER_STATUS_PATH_TEMPLATE`
- `USER_STATUS_TIMEOUT_SECONDS`

## Frontend token propagation

Frontend sends `Authorization` automatically if a token is available in:

- `NEXT_PUBLIC_API_AUTH_TOKEN` / `API_AUTH_TOKEN` environment variables
- `localStorage["api_auth_token"]`