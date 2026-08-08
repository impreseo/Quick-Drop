from __future__ import annotations

import os
import shutil
import tempfile
import time
import uuid
import zipfile
from pathlib import Path
from threading import RLock
from typing import Callable

from quickdrop.core.models import SharedItem, TransferEvent
from quickdrop.core.security import safe_filename, unique_path
from quickdrop.core.storage import JsonStore, app_data_dir


def default_inbox_dir(data_dir: str | Path | None = None) -> Path:
    if data_dir is not None or os.environ.get("QUICKDROP_DATA_DIR"):
        return app_data_dir(data_dir) / "Received"
    if os.name == "nt":
        return Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Downloads" / "QuickDrop"
    return app_data_dir() / "Received"


DEFAULT_SETTINGS = {
    # Keep this blank in defaults so the location is evaluated at runtime rather
    # than at module import. That is important for portable tests and profiles.
    "inbox": "",
    "session_minutes": 30,
    "start_server": True,
    "allow_downloads": True,
    "allow_uploads": True,
    "allow_text": True,
    "max_upload_mb": 2048,
    "computer_name": "",
    "allow_trusted_devices": True,
}


class TransferManager:
    def __init__(self, *, data_dir: str | Path | None = None, inbox_dir: str | Path | None = None) -> None:
        self.data_dir = app_data_dir(data_dir)
        self._shared: dict[str, SharedItem] = {}
        self._lock = RLock()
        self._history_store = JsonStore("history.json", [], base_dir=self.data_dir)
        self._settings_store = JsonStore("settings.json", DEFAULT_SETTINGS, base_dir=self.data_dir)
        loaded = self._settings_store.load()
        self.settings = DEFAULT_SETTINGS.copy()
        if isinstance(loaded, dict):
            self.settings.update(loaded)
        configured = inbox_dir or self.settings.get("inbox") or default_inbox_dir(self.data_dir if data_dir is not None else None)
        self.inbox = Path(configured).expanduser()
        self.inbox.mkdir(parents=True, exist_ok=True)
        self.temp_dir = Path(tempfile.mkdtemp(prefix="QuickDrop-"))
        self.quick_text = ""
        self.on_change: Callable[[], None] | None = None

    def _notify(self) -> None:
        callback = self.on_change
        if callback:
            callback()

    def save_settings(self) -> None:
        self.settings["inbox"] = str(self.inbox)
        self._settings_store.save(self.settings)

    def list_shared(self) -> list[SharedItem]:
        with self._lock:
            return list(self._shared.values())

    def get_shared(self, item_id: str) -> SharedItem | None:
        with self._lock:
            return self._shared.get(item_id)

    def add_file(self, path: Path) -> SharedItem:
        path = path.expanduser().resolve()
        if not path.is_file():
            raise ValueError(f"Not a file: {path}")
        item = SharedItem(id=uuid.uuid4().hex, path=str(path), name=path.name, size=path.stat().st_size)
        with self._lock:
            self._shared[item.id] = item
        self._notify()
        return item

    def add_folder(self, folder: Path) -> SharedItem:
        folder = folder.expanduser().resolve()
        if not folder.is_dir():
            raise ValueError(f"Not a folder: {folder}")
        archive_base = self.temp_dir / f"{safe_filename(folder.name, 'Folder')}-{uuid.uuid4().hex[:8]}"
        archive = Path(shutil.make_archive(str(archive_base), "zip", root_dir=folder))
        item = SharedItem(
            id=uuid.uuid4().hex,
            path=str(archive),
            name=f"{safe_filename(folder.name, 'Folder')}.zip",
            size=archive.stat().st_size,
            kind="folder-zip",
            temporary=True,
        )
        with self._lock:
            self._shared[item.id] = item
        self._notify()
        return item

    def build_share_bundle(self) -> Path | None:
        items = [item for item in self.list_shared() if item.file_path.is_file()]
        if not items:
            return None
        bundle = self.temp_dir / f"QuickDrop-Shared-{uuid.uuid4().hex[:8]}.zip"
        with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
            used: set[str] = set()
            for item in items:
                name = safe_filename(item.name, "file")
                candidate = name
                index = 2
                stem, suffix = Path(name).stem, Path(name).suffix
                while candidate.casefold() in used:
                    candidate = f"{stem} ({index}){suffix}"
                    index += 1
                used.add(candidate.casefold())
                archive.write(item.file_path, arcname=candidate)
        return bundle

    def remove_shared(self, item_id: str) -> None:
        with self._lock:
            item = self._shared.pop(item_id, None)
        if item and item.temporary:
            try:
                item.file_path.unlink(missing_ok=True)
            except OSError:
                pass
        self._notify()

    def clear_shared(self) -> None:
        for item in self.list_shared():
            self.remove_shared(item.id)

    def history(self) -> list[dict]:
        value = self._history_store.load()
        return value if isinstance(value, list) else []

    def clear_history(self) -> None:
        self._history_store.save([])
        self._notify()

    def record(self, event: TransferEvent) -> None:
        rows = self.history()
        rows.insert(0, event.to_dict())
        self._history_store.save(rows[:500])
        self._notify()

    def record_download(self, item: SharedItem, client: str, device: str = "") -> None:
        self.record(TransferEvent("sent", item.name, item.size, "Completed", time.time(), client, device))

    def record_bundle_download(self, path: Path, client: str, device: str = "") -> None:
        self.record(TransferEvent("sent", path.name, path.stat().st_size, "Completed", time.time(), client, device))

    def receive_path(self, filename: str) -> Path:
        return unique_path(self.inbox, safe_filename(filename, "received-file"))

    def record_upload(self, path: Path, client: str, device: str = "") -> None:
        self.record(TransferEvent("received", path.name, path.stat().st_size, "Completed", time.time(), client, device))

    def set_quick_text(self, value: str) -> None:
        self.quick_text = value[:100_000]
        self._notify()

    def stats(self) -> dict[str, int]:
        rows = self.history()
        return {
            "shared": len(self.list_shared()),
            "sent": sum(1 for row in rows if row.get("direction") == "sent"),
            "received": sum(1 for row in rows if row.get("direction") == "received"),
            "sent_bytes": sum(int(row.get("size", 0) or 0) for row in rows if row.get("direction") == "sent"),
            "received_bytes": sum(int(row.get("size", 0) or 0) for row in rows if row.get("direction") == "received"),
        }

    def close(self) -> None:
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        finally:
            self.save_settings()
