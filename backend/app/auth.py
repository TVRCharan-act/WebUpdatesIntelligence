"""S3-backed accounts and signed HTTP-only sessions."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime
import hashlib
import hmac
import json
import secrets
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from backend.app.config import ConfigurationError, get_settings
from backend.app.repository import DuplicateRecord, S3Repository, get_repository


AUTH_COOKIE_NAME = "pulseactalyst_session"
AUTH_COOKIE_MAX_AGE = 60 * 60 * 24 * 7
PASSWORD_ITERATIONS = 600_000


class LoginRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=500)


class AuthUser(BaseModel):
    name: str
    role: str


class AuthSessionRead(AuthUser):
    pass


@dataclass(frozen=True)
class ConfigAccount:
    name: str
    role: str
    last_login_at: datetime | None = None


def _normalize_name(value: str) -> str:
    return value.strip().lower()


def hash_password(password: str) -> str:
    """Use a salted PBKDF2 hash; plaintext credentials never enter S3."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return "$".join(
        (
            "pbkdf2_sha256",
            str(PASSWORD_ITERATIONS),
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(digest).decode("ascii"),
        )
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, iterations, encoded_salt, expected = encoded.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(encoded_salt.encode("ascii"))
        expected_digest = base64.urlsafe_b64decode(expected.encode("ascii"))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected_digest)


def bootstrap_accounts(repository: S3Repository | None = None) -> None:
    """Seed environment-provisioned accounts once, without overwriting S3 state."""
    settings = get_settings()
    repo = repository or get_repository()
    if settings.admin_name and settings.admin_password:
        repo.ensure_account(settings.admin_name, hash_password(settings.admin_password), "admin")
    repo.bootstrap_customer_accounts_once(
        (name, hash_password(password)) for name, password in settings.bootstrap_customer_accounts
    )


def configured_accounts(repository: S3Repository) -> list[ConfigAccount]:
    rows: list[ConfigAccount] = []
    for account in repository.list_accounts():
        raw_last_login = account.get("last_login_at")
        last_login = None
        if isinstance(raw_last_login, str):
            try:
                last_login = datetime.fromisoformat(raw_last_login.replace("Z", "+00:00"))
            except ValueError:
                pass
        rows.append(
            ConfigAccount(
                name=str(account["name"]),
                role=str(account["role"]),
                last_login_at=last_login,
            )
        )
    return rows


def register_account(repository: S3Repository, name: str, password: str, role: str = "customer") -> ConfigAccount:
    name = name.strip()
    if not name or not password:
        raise ValueError("Name and password are required.")
    if role != "customer":
        raise ValueError("Only customer accounts may be created through this endpoint.")
    try:
        account = repository.create_account(name, hash_password(password), role)
    except DuplicateRecord as exc:
        raise ValueError("An account with that name already exists.") from exc
    return ConfigAccount(name=str(account["name"]), role="customer")


def verify_login(repository: S3Repository, name: str, password: str) -> AuthUser | None:
    account = repository.get_account(name)
    if not account or not verify_password(password, str(account.get("password_hash", ""))):
        return None
    repository.touch_account_login(str(account["name"]))
    return AuthUser(name=str(account["name"]), role=str(account["role"]))


def _secret_key() -> bytes:
    settings = get_settings()
    settings.require_auth()
    # A local-only fallback keeps the in-memory development/test adapter easy to
    # use. Production always fails startup without a dedicated AUTH_SECRET.
    return (settings.auth_secret or "sentinel-actalyst-local-development-only").encode("utf-8")


def _sign(payload: bytes) -> str:
    return hmac.new(_secret_key(), payload, hashlib.sha256).hexdigest()


def _encode_session(user: AuthUser) -> str:
    payload = json.dumps({"name": user.name, "role": user.role}, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return f"{base64.urlsafe_b64encode(payload).decode('ascii')}.{_sign(payload)}"


def _decode_session(token: str) -> AuthUser | None:
    try:
        encoded_payload, signature = token.split(".", 1)
        payload = base64.urlsafe_b64decode(encoded_payload.encode("ascii"))
        if not hmac.compare_digest(_sign(payload), signature):
            return None
        value = json.loads(payload.decode("utf-8"))
        name = str(value["name"])
        role = str(value["role"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, ConfigurationError):
        return None
    if role not in {"admin", "customer"}:
        return None
    return AuthUser(name=name, role=role)


def set_auth_cookie(response: Response, user: AuthUser) -> None:
    response.set_cookie(
        AUTH_COOKIE_NAME,
        _encode_session(user),
        max_age=AUTH_COOKIE_MAX_AGE,
        httponly=True,
        secure=get_settings().auth_cookie_secure,
        samesite="lax",
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(AUTH_COOKIE_NAME)


Repository = Annotated[S3Repository, Depends(get_repository)]


def get_current_user(
    repository: Repository,
    session: Annotated[str | None, Cookie(alias=AUTH_COOKIE_NAME)] = None,
) -> AuthUser:
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    user = _decode_session(session)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session.")
    account = repository.get_account(user.name)
    if account is None or str(account.get("role")) != user.role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session.")
    return AuthUser(name=str(account["name"]), role=str(account["role"]))


CurrentUser = Annotated[AuthUser, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> AuthUser:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")
    return user


AdminUser = Annotated[AuthUser, Depends(require_admin)]
