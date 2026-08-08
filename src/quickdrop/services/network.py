from __future__ import annotations

import os
import socket
from pathlib import Path


def best_lan_ip() -> str:
    """Return the preferred LAN IPv4 without sending application data."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        if ip and not ip.startswith("127."):
            return ip
    except OSError:
        pass
    finally:
        sock.close()

    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127."):
                return ip
    except OSError:
        pass
    return "127.0.0.1"


def network_summary() -> dict[str, str]:
    hostname = socket.gethostname() or "Unknown"
    addresses: list[str] = []
    try:
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            value = info[4][0]
            if value not in addresses:
                addresses.append(value)
    except OSError:
        pass
    return {
        "Computer": os.environ.get("COMPUTERNAME") or hostname,
        "Host name": hostname,
        "Preferred LAN IPv4": best_lan_ip(),
        "IPv4 addresses": ", ".join(addresses) or "Unavailable",
    }


def folder_health(path: Path) -> dict[str, str]:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".quickdrop-write-test"
        probe.write_bytes(b"ok")
        probe.unlink(missing_ok=True)
        writable = "Yes"
    except OSError:
        writable = "No"
    try:
        import shutil
        usage = shutil.disk_usage(path)
        free = usage.free
        free_gb = f"{free / (1024**3):.1f} GB"
    except OSError:
        free_gb = "Unavailable"
    return {"Inbox writable": writable, "Inbox free space": free_gb}
