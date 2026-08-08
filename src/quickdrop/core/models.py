from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import time


@dataclass(slots=True)
class SharedItem:
    id: str
    path: str
    name: str
    size: int
    kind: str = "file"
    temporary: bool = False
    created_at: float = 0.0

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = time.time()

    @property
    def file_path(self) -> Path:
        return Path(self.path)

    def public_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "size": self.size,
            "kind": self.kind,
            "created_at": self.created_at,
        }


@dataclass(slots=True)
class TransferEvent:
    direction: str
    name: str
    size: int
    status: str
    timestamp: float
    detail: str = ""
    device: str = ""

    def to_dict(self) -> dict:
        return asdict(self)
