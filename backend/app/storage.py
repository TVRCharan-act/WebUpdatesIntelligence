"""Version-aware JSON storage backed by S3.

S3 is deliberately hidden behind this small interface.  Records are individual
objects, never one mutable application JSON blob, and callers use compare and
swap updates when a concurrent writer could otherwise lose an update.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import copy
import json
import threading
from typing import Any, Protocol, TypeVar

from backend.app.config import ConfigurationError, Settings, get_settings


JsonValue = dict[str, Any]
T = TypeVar("T")


class StorageError(RuntimeError):
    pass


class ObjectNotFound(StorageError):
    pass


class ObjectConflict(StorageError):
    pass


@dataclass(frozen=True)
class StoredJson:
    key: str
    value: JsonValue
    etag: str


@dataclass(frozen=True)
class ObjectPage:
    keys: list[str]
    next_cursor: str | None = None


class JsonStorage(Protocol):
    def get_json(self, key: str) -> StoredJson: ...

    def put_json(
        self,
        key: str,
        value: JsonValue,
        *,
        if_match: str | None = None,
        if_none_match: bool = False,
    ) -> StoredJson: ...

    def delete(self, key: str) -> None: ...

    def list_objects(
        self, prefix: str, *, cursor: str | None = None, limit: int = 1000
    ) -> ObjectPage: ...

    def update_json(
        self,
        key: str,
        update: Callable[[JsonValue | None], JsonValue],
        *,
        retries: int = 4,
    ) -> StoredJson: ...


def _encode(value: JsonValue) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )


class InMemoryJsonStorage:
    """Thread-safe storage substitute used by the normal test suite."""

    def __init__(self) -> None:
        self._objects: dict[str, tuple[JsonValue, int]] = {}
        self._lock = threading.RLock()

    def get_json(self, key: str) -> StoredJson:
        with self._lock:
            try:
                value, version = self._objects[key]
            except KeyError as exc:
                raise ObjectNotFound(key) from exc
            return StoredJson(key, copy.deepcopy(value), str(version))

    def put_json(
        self,
        key: str,
        value: JsonValue,
        *,
        if_match: str | None = None,
        if_none_match: bool = False,
    ) -> StoredJson:
        with self._lock:
            existing = self._objects.get(key)
            if if_none_match and existing is not None:
                raise ObjectConflict(f"Object already exists: {key}")
            if if_match is not None and (existing is None or str(existing[1]) != if_match):
                raise ObjectConflict(f"Object changed before update: {key}")
            version = (existing[1] if existing else 0) + 1
            safe_value = copy.deepcopy(value)
            self._objects[key] = (safe_value, version)
            return StoredJson(key, copy.deepcopy(safe_value), str(version))

    def delete(self, key: str) -> None:
        with self._lock:
            self._objects.pop(key, None)

    def list_objects(
        self, prefix: str, *, cursor: str | None = None, limit: int = 1000
    ) -> ObjectPage:
        with self._lock:
            keys = sorted(key for key in self._objects if key.startswith(prefix))
        if cursor:
            keys = [key for key in keys if key > cursor]
        page = keys[:limit]
        return ObjectPage(page, page[-1] if len(keys) > len(page) and page else None)

    def update_json(
        self,
        key: str,
        update: Callable[[JsonValue | None], JsonValue],
        *,
        retries: int = 4,
    ) -> StoredJson:
        # The lock makes a read/modify/write atomic for the local implementation.
        with self._lock:
            existing = self._objects.get(key)
            value = copy.deepcopy(existing[0]) if existing else None
            next_value = update(value)
            return self.put_json(
                key,
                next_value,
                if_match=str(existing[1]) if existing else None,
                if_none_match=existing is None,
            )

    def seed(self, values: Iterable[tuple[str, JsonValue]]) -> None:
        for key, value in values:
            self.put_json(key, value)


class S3JsonStorage:
    def __init__(self, *, bucket: str, region: str, client: Any | None = None) -> None:
        self.bucket = bucket
        if client is None:
            try:
                import boto3
            except ImportError as exc:  # pragma: no cover - dependency guard
                raise ConfigurationError("boto3 is required for S3-backed storage.") from exc
            # Deliberately rely on the standard AWS credential provider chain.
            client = boto3.client("s3", region_name=region)
        self.client = client

    @staticmethod
    def _is_missing(exc: Exception) -> bool:
        response = getattr(exc, "response", {}) or {}
        code = str((response.get("Error") or {}).get("Code", ""))
        return code in {"NoSuchKey", "404", "NotFound"}

    @staticmethod
    def _is_conflict(exc: Exception) -> bool:
        response = getattr(exc, "response", {}) or {}
        code = str((response.get("Error") or {}).get("Code", ""))
        return code in {"PreconditionFailed", "412", "ConditionalRequestConflict"}

    def get_json(self, key: str) -> StoredJson:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            raw = response["Body"].read()
            value = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            if self._is_missing(exc):
                raise ObjectNotFound(key) from exc
            if isinstance(exc, (UnicodeDecodeError, json.JSONDecodeError)):
                raise StorageError(f"Invalid JSON in s3://{self.bucket}/{key}") from exc
            raise StorageError(f"Could not read s3://{self.bucket}/{key}: {exc}") from exc
        if not isinstance(value, dict):
            raise StorageError(f"Expected an object at s3://{self.bucket}/{key}")
        return StoredJson(key, value, str(response.get("ETag", "")).strip('"'))

    def put_json(
        self,
        key: str,
        value: JsonValue,
        *,
        if_match: str | None = None,
        if_none_match: bool = False,
    ) -> StoredJson:
        params: dict[str, Any] = {
            "Bucket": self.bucket,
            "Key": key,
            "Body": _encode(value),
            "ContentType": "application/json",
        }
        if if_match is not None:
            params["IfMatch"] = if_match
        if if_none_match:
            params["IfNoneMatch"] = "*"
        try:
            response = self.client.put_object(**params)
        except Exception as exc:
            if self._is_conflict(exc):
                raise ObjectConflict(f"Object changed before update: {key}") from exc
            raise StorageError(f"Could not write s3://{self.bucket}/{key}: {exc}") from exc
        return StoredJson(key, copy.deepcopy(value), str(response.get("ETag", "")).strip('"'))

    def delete(self, key: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
        except Exception as exc:
            raise StorageError(f"Could not delete s3://{self.bucket}/{key}: {exc}") from exc

    def list_objects(
        self, prefix: str, *, cursor: str | None = None, limit: int = 1000
    ) -> ObjectPage:
        params: dict[str, Any] = {
            "Bucket": self.bucket,
            "Prefix": prefix,
            "MaxKeys": min(max(limit, 1), 1000),
        }
        if cursor:
            params["ContinuationToken"] = cursor
        try:
            response = self.client.list_objects_v2(**params)
        except Exception as exc:
            raise StorageError(f"Could not list s3://{self.bucket}/{prefix}: {exc}") from exc
        return ObjectPage(
            [item["Key"] for item in response.get("Contents", [])],
            response.get("NextContinuationToken"),
        )

    def update_json(
        self,
        key: str,
        update: Callable[[JsonValue | None], JsonValue],
        *,
        retries: int = 4,
    ) -> StoredJson:
        for attempt in range(retries + 1):
            try:
                current = self.get_json(key)
            except ObjectNotFound:
                try:
                    return self.put_json(key, update(None), if_none_match=True)
                except ObjectConflict:
                    if attempt == retries:
                        raise
                    continue
            try:
                return self.put_json(key, update(current.value), if_match=current.etag)
            except ObjectConflict:
                if attempt == retries:
                    raise
        raise ObjectConflict(f"Could not safely update {key}")


_storage_override: JsonStorage | None = None
_cached_storage: JsonStorage | None = None


def get_storage(settings: Settings | None = None) -> JsonStorage:
    global _cached_storage
    if _storage_override is not None:
        return _storage_override
    if _cached_storage is not None:
        return _cached_storage
    config = settings or get_settings()
    config.require_storage()
    if config.storage_backend == "memory":
        _cached_storage = InMemoryJsonStorage()
    elif config.storage_backend == "s3":
        _cached_storage = S3JsonStorage(bucket=config.s3_bucket or "", region=config.aws_region)
    else:
        raise ConfigurationError("STORAGE_BACKEND must be 's3' or 'memory'.")
    return _cached_storage


def set_storage_for_testing(storage: JsonStorage | None) -> None:
    """Install a storage double.  Never use this from runtime code."""
    global _storage_override, _cached_storage
    _storage_override = storage
    _cached_storage = None
