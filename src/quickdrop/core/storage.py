from __future__ import annotations

import json
import os
from pathlib import Path
from threading import RLock
from typing import Any

APP_DIR_NAME = "QuickDrop"


def app_data_dir(override: str | Path | None = None) -> Path:
    """Return QuickDrop's writable per-user data directory.

    ``override`` is used by tests and controlled integrations so they never touch
    a real user's settings/history. Normal application code leaves it unset.
    """
    if override is not None:
        path = Path(override).expanduser()
    elif os.environ.get("QUICKDROP_DATA_DIR"):
        path = Path(os.environ["QUICKDROP_DATA_DIR"]).expanduser()
    elif os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        path = base / APP_DIR_NAME
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        path = base / APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


class JsonStore:
    def __init__(self, filename: str, default: Any, base_dir: str | Path | None = None) -> None:
        self.path = app_data_dir(base_dir) / filename
        self.default = default
        self._lock = RLock()

    def _default_value(self) -> Any:
        return self.default.copy() if isinstance(self.default, (dict, list)) else self.default

    def load(self) -> Any:
        with self._lock:
            if not self.path.exists():
                return self._default_value()
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return self._default_value()

    def save(self, value: Any) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)
