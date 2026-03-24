"""In-memory hold for compress/convert outputs (tokens under /r/{token})."""

from __future__ import annotations

import re
import threading
import time
import uuid
from typing import Any

from app.config import get_settings

_TOKEN_RE = re.compile(r"^[0-9a-f]{32}$")
_lock = threading.Lock()
_store: dict[str, tuple[bytes, dict[str, Any]]] = {}


def is_valid_token(token: str) -> bool:
    return bool(token and _TOKEN_RE.match(token))


def _ttl_seconds() -> float:
    return float(get_settings().result_ttl_hours) * 3600.0


def _cleanup_expired() -> None:
    cutoff = time.time() - _ttl_seconds()
    with _lock:
        expired = [
            t
            for t, (_data, meta) in _store.items()
            if float(meta.get("created", 0)) < cutoff
        ]
        for t in expired:
            _store.pop(t, None)


def save_result(
    data: bytes,
    *,
    media_type: str,
    filename: str,
    kind: str,
    original_size: int,
    compressed_size: int,
    pdf_mode: str | None = None,
    kept_original: bool | None = None,
    page_count: int | None = None,
) -> str:
    _cleanup_expired()
    token = uuid.uuid4().hex
    meta: dict[str, Any] = {
        "media_type": media_type,
        "filename": filename,
        "created": time.time(),
        "kind": kind,
        "original_size": original_size,
        "compressed_size": compressed_size,
    }
    if pdf_mode is not None:
        meta["pdf_mode"] = pdf_mode
    if kept_original is not None:
        meta["kept_original"] = kept_original
    if page_count is not None:
        meta["page_count"] = int(page_count)

    with _lock:
        _store[token] = (data, meta)
    return token


def _read_meta(token: str) -> dict[str, Any] | None:
    if not is_valid_token(token):
        return None
    with _lock:
        entry = _store.get(token)
    if not entry:
        return None
    _data, meta = entry
    created = float(meta.get("created", 0))
    if time.time() - created > _ttl_seconds():
        with _lock:
            _store.pop(token, None)
        return None
    return meta


def get_result_meta(token: str) -> dict[str, Any] | None:
    _cleanup_expired()
    return _read_meta(token)


def get_result_bytes(token: str) -> tuple[bytes, dict[str, Any]] | None:
    _cleanup_expired()
    if not is_valid_token(token):
        return None
    with _lock:
        entry = _store.get(token)
    if not entry:
        return None
    data, meta = entry
    created = float(meta.get("created", 0))
    if time.time() - created > _ttl_seconds():
        with _lock:
            _store.pop(token, None)
        return None
    return data, meta
