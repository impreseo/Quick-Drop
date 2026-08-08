from __future__ import annotations

import hashlib
import hmac
import secrets
import time
import uuid
from pathlib import Path

from quickdrop.core.storage import JsonStore


def _secret_hash(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def clean_device_name(value: str) -> str:
    text = " ".join(str(value).strip().split())
    return text[:64] or "Trusted device"


class DeviceRegistry:
    """Persistent remembered-device credentials.

    The PC persists only a SHA-256 digest of the random device secret. The
    browser stores the actual credential and can be revoked from QuickDrop.
    """

    def __init__(self, data_dir: str | Path | None = None) -> None:
        self._store = JsonStore("trusted_devices.json", [], base_dir=data_dir)

    def _load(self) -> list[dict]:
        rows = self._store.load()
        return rows if isinstance(rows, list) else []

    def _save(self, rows: list[dict]) -> None:
        self._store.save(rows[:100])

    def issue(self, name: str, client_ip: str) -> dict[str, str]:
        now = time.time()
        device_id = uuid.uuid4().hex
        secret = secrets.token_urlsafe(32)
        rows = self._load()
        rows.insert(0, {
            "id": device_id,
            "name": clean_device_name(name),
            "secret_hash": _secret_hash(secret),
            "created_at": now,
            "last_seen": now,
            "last_ip": str(client_ip)[:64],
        })
        self._save(rows)
        return {"id": device_id, "secret": secret}

    def verify(self, device_id: str, secret: str, client_ip: str) -> dict | None:
        if not device_id or not secret:
            return None
        rows = self._load()
        match = None
        changed = False
        for row in rows:
            if str(row.get("id", "")) != str(device_id):
                continue
            expected = str(row.get("secret_hash", ""))
            if expected and hmac.compare_digest(expected, _secret_hash(secret)):
                row["last_seen"] = time.time()
                row["last_ip"] = str(client_ip)[:64]
                match = dict(row)
                changed = True
            break
        if changed:
            self._save(rows)
        return match

    def list_public(self) -> list[dict]:
        result = []
        for row in self._load():
            result.append({
                "id": str(row.get("id", "")),
                "name": clean_device_name(str(row.get("name", ""))),
                "created_at": float(row.get("created_at", 0) or 0),
                "last_seen": float(row.get("last_seen", 0) or 0),
                "last_ip": str(row.get("last_ip", "")),
            })
        return result

    def revoke(self, device_id: str) -> bool:
        rows = self._load()
        kept = [row for row in rows if str(row.get("id", "")) != str(device_id)]
        if len(kept) == len(rows):
            return False
        self._save(kept)
        return True

    def revoke_all(self) -> None:
        self._save([])
