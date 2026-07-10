from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
import re
from pathlib import Path
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field


AUTH_COOKIE_NAME = "pulseactalyst_session"
AUTH_COOKIE_MAX_AGE = 60 * 60 * 24 * 7

# Accounts registered at runtime (admin-provisioned) are persisted here, in the
# mounted mysignal/data volume, since the container can't write the host .env.
# They are merged with the env-configured accounts at startup (§auth).
ACCOUNTS_FILE = Path("mysignal/data/accounts.json")


class LoginRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=500)


class AuthUser(BaseModel):
    name: str
    role: str


class AuthSessionRead(AuthUser):
    pass


@dataclass
class ConfigAccount:
    name: str
    password: str
    role: str
    last_login_at: datetime | None = None


def _normalize_name(value: str) -> str:
    return value.strip().lower()


def _secret_key() -> bytes:
    secret = os.getenv("AUTH_SECRET") or os.getenv("SECRET_KEY")
    if not secret:
        database_url = os.getenv("DATABASE_URL", "pulseactalyst-local-dev")
        secret = f"pulseactalyst:{database_url}"
    return secret.encode("utf-8")


def _load_accounts() -> dict[str, ConfigAccount]:
    accounts: dict[str, ConfigAccount] = {}

    admin_name = os.getenv("ADMIN_NAME")
    admin_password = os.getenv("ADMIN_PASSWORD")
    if admin_name and admin_password:
        accounts[_normalize_name(admin_name)] = ConfigAccount(
            name=admin_name.strip(),
            password=admin_password,
            role="admin",
        )

    user_indexes = sorted(
        {
            match.group(1)
            for key in os.environ
            if (match := re.fullmatch(r"USER_(\d+)_NAME", key))
        },
        key=int,
    )
    for index in user_indexes:
        name = os.getenv(f"USER_{index}_NAME")
        password = os.getenv(f"USER_{index}_PASSWORD")
        if not name or not password:
            continue
        accounts[_normalize_name(name)] = ConfigAccount(
            name=name.strip(),
            password=password,
            role="customer",
        )

    # File-backed accounts (registered via the admin UI). Env accounts win on a
    # name clash, so a registered account can never shadow the configured admin.
    for key, account in _load_file_accounts().items():
        accounts.setdefault(key, account)

    return accounts


def _load_file_accounts() -> dict[str, ConfigAccount]:
    accounts: dict[str, ConfigAccount] = {}
    try:
        if not ACCOUNTS_FILE.exists():
            return accounts
        data = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return accounts

    if not isinstance(data, list):
        return accounts

    for entry in data:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", "")).strip()
        password = str(entry.get("password", ""))
        role = str(entry.get("role", "customer")).strip().lower()
        if not name or not password:
            continue
        if role not in {"admin", "customer"}:
            role = "customer"
        accounts[_normalize_name(name)] = ConfigAccount(name=name, password=password, role=role)

    return accounts


def _append_file_account(account: ConfigAccount) -> None:
    ACCOUNTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data: list = []
    if ACCOUNTS_FILE.exists():
        try:
            loaded = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                data = loaded
        except Exception:
            data = []
    data.append({"name": account.name, "password": account.password, "role": account.role})
    ACCOUNTS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def register_account(name: str, password: str, role: str = "customer") -> ConfigAccount:
    """Provision a new account: persist to the accounts file and make it usable
    immediately (no restart). Raises ValueError on invalid input or a name clash."""
    name = (name or "").strip()
    password = password or ""
    if not name or not password:
        raise ValueError("Name and password are required.")
    # Registration only ever creates customer accounts.
    role = "customer"

    key = _normalize_name(name)
    if key in CONFIG_ACCOUNTS:
        raise ValueError("An account with that name already exists.")

    account = ConfigAccount(name=name, password=password, role=role)
    _append_file_account(account)
    CONFIG_ACCOUNTS[key] = account
    return account


CONFIG_ACCOUNTS = _load_accounts()


def configured_accounts() -> list[ConfigAccount]:
    return sorted(CONFIG_ACCOUNTS.values(), key=lambda account: (account.role, account.name.lower()))


def verify_login(name: str, password: str) -> AuthUser | None:
    account = CONFIG_ACCOUNTS.get(_normalize_name(name))
    if account is None:
        return None

    if not hmac.compare_digest(account.password, password):
        return None

    account.last_login_at = datetime.now(timezone.utc)
    return AuthUser(name=account.name, role=account.role)


def _sign(payload: bytes) -> str:
    return hmac.new(_secret_key(), payload, hashlib.sha256).hexdigest()


def _encode_session(user: AuthUser) -> str:
    payload = json.dumps(
        {"name": user.name, "role": user.role},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    token = base64.urlsafe_b64encode(payload).decode("ascii")
    return f"{token}.{_sign(payload)}"


def _decode_session(token: str) -> AuthUser | None:
    try:
        encoded_payload, signature = token.split(".", 1)
        payload = base64.urlsafe_b64decode(encoded_payload.encode("ascii"))
    except Exception:
        return None

    if not hmac.compare_digest(_sign(payload), signature):
        return None

    try:
        raw = json.loads(payload.decode("utf-8"))
        name = str(raw["name"])
        role = str(raw["role"])
    except Exception:
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
        secure=os.getenv("AUTH_COOKIE_SECURE", "").strip().lower() in {"1", "true", "yes", "on"},
        samesite="lax",
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(AUTH_COOKIE_NAME)


def get_current_user(
    session: Annotated[str | None, Cookie(alias=AUTH_COOKIE_NAME)] = None,
) -> AuthUser:
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    user = _decode_session(session)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session.",
        )

    return user


CurrentUser = Annotated[AuthUser, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> AuthUser:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return user


AdminUser = Annotated[AuthUser, Depends(require_admin)]
