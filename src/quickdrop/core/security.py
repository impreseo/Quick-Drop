from __future__ import annotations

import ipaddress
import re
import secrets
from pathlib import Path
from urllib.parse import quote

_FILENAME_CLEAN = re.compile(r"[<>:\\|?*\x00-\x1f]")


def new_token() -> str:
    return secrets.token_urlsafe(32)


def new_pin() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def is_private_client(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except ValueError:
        return False


def safe_filename(name: str, fallback: str = "file") -> str:
    name = str(name).replace("\\", "/").rsplit("/", 1)[-1].strip().strip(".")
    name = _FILENAME_CLEAN.sub("_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:180] or fallback


def unique_path(directory: Path, filename: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    filename = safe_filename(filename)
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem, suffix = candidate.stem, candidate.suffix
    index = 2
    while True:
        candidate = directory / f"{stem} ({index}){suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def content_disposition(filename: str) -> str:
    clean = safe_filename(filename)
    ascii_name = clean.encode("ascii", "ignore").decode("ascii") or "download"
    ascii_name = ascii_name.replace('"', "'")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(clean)}"
