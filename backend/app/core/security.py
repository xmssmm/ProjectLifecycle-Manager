from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import uuid4

from jose import jwt  # type: ignore[import-untyped]
from passlib.context import CryptContext  # type: ignore[import-untyped]

password_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def generate_jti() -> str:
    return str(uuid4())


def hash_password(password: str) -> str:
    return cast(str, password_context.hash(password))


def verify_password(password: str, password_hash: str) -> bool:
    return cast(bool, password_context.verify(password, password_hash))


def create_jwt_token(
    *,
    subject: str,
    key: str,
    algorithm: str,
    token_type: str,
    expires_delta: timedelta,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "jti": generate_jti(),
    }
    if extra_claims:
        payload.update(extra_claims)
    return cast(str, jwt.encode(payload, key, algorithm=algorithm))


def decode_jwt_token(token: str, *, key: str, algorithms: list[str]) -> dict[str, Any]:
    decoded = jwt.decode(token, key, algorithms=algorithms)
    return cast(dict[str, Any], decoded)
