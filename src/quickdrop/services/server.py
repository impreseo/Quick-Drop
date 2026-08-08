from __future__ import annotations

import json
import logging
import mimetypes
import os
import re
import secrets
import shutil
import threading
import time
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from urllib.parse import unquote, urlparse

from quickdrop.core.devices import DeviceRegistry, clean_device_name
from quickdrop.core.security import content_disposition, is_private_client, new_pin, safe_filename
from quickdrop.services.network import best_lan_ip
from quickdrop.services.transfer import TransferManager

ABSOLUTE_MAX_UPLOAD_BYTES = 10 * 1024 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024
_RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)$")


class ShareSession:
    def __init__(self, minutes: int = 30) -> None:
        self.pin = new_pin()
        self.created_at = time.time()
        self.expires_at = self.created_at + max(5, min(minutes, 240)) * 60

    @property
    def remaining_seconds(self) -> int:
        return max(0, int(self.expires_at - time.time()))

    @property
    def active(self) -> bool:
        return self.remaining_seconds > 0


class QuickDropHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address) -> None:
        logging.exception("HTTP handler error from %s", client_address)

    def __init__(self, address, manager: TransferManager, session: ShareSession):
        self.manager = manager
        self.session = session
        self.devices = DeviceRegistry(manager.data_dir)
        self.auth_failures: dict[str, tuple[int, float]] = {}
        self.auth_clients: dict[str, dict] = {}
        super().__init__(address, QuickDropHandler)

    def create_auth(self, *, name: str, client_ip: str, trusted_device_id: str = "") -> str:
        auth_id = secrets.token_urlsafe(32)
        self.auth_clients[auth_id] = {
            "name": clean_device_name(name),
            "ip": client_ip,
            "trusted_device_id": trusted_device_id,
            "created_at": time.time(),
        }
        return auth_id

    def auth_client(self, auth_id: str | None) -> dict | None:
        if not auth_id or not self.session.active:
            return None
        return self.auth_clients.get(auth_id)


class QuickDropHandler(BaseHTTPRequestHandler):
    server_version = "QuickDrop/2.0"

    def log_message(self, fmt: str, *args) -> None:
        return

    @property
    def qd_server(self) -> QuickDropHTTPServer:
        return self.server  # type: ignore[return-value]

    def _private_only(self) -> bool:
        if is_private_client(self.client_address[0]):
            return True
        self.send_error(HTTPStatus.FORBIDDEN, "QuickDrop only accepts local-network clients")
        return False

    def _security_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")

    def _json(self, payload: dict | list, status: int = 200, headers: list[tuple[str, str]] | None = None) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self._security_headers()
        for key, value in headers or []:
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def _cookie(self, key: str) -> str | None:
        raw = self.headers.get("Cookie", "")
        cookie = SimpleCookie()
        try:
            cookie.load(raw)
        except Exception:
            return None
        morsel = cookie.get(key)
        return morsel.value if morsel else None

    def _client(self) -> dict | None:
        return self.qd_server.auth_client(self._cookie("qd_auth"))

    def _authenticated(self) -> bool:
        return self._client() is not None

    def _require_auth(self) -> bool:
        if self._authenticated():
            return True
        self._json({"error": "Authentication required"}, 401)
        return False

    def _require_permission(self, key: str) -> bool:
        if not self._require_auth():
            return False
        if bool(self.qd_server.manager.settings.get(key, True)):
            return True
        self._json({"error": "This transfer action is disabled on the PC"}, 403)
        return False

    def _read_json(self, max_bytes: int = 128_000) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("Invalid request length")
        if length <= 0 or length > max_bytes:
            raise ValueError("Invalid request length")
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid JSON") from exc

    def _serve_asset(self, name: str, content_type: str) -> None:
        try:
            asset = resources.files("quickdrop.web").joinpath(name).read_bytes()
        except Exception:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(asset)))
        self._security_headers()
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(asset)

    def _auth_headers(self, auth_id: str) -> list[tuple[str, str]]:
        age = self.qd_server.session.remaining_seconds
        return [("Set-Cookie", f"qd_auth={auth_id}; Path=/; HttpOnly; SameSite=Strict; Max-Age={age}")]

    def _permissions(self) -> dict[str, object]:
        settings = self.qd_server.manager.settings
        return {
            "downloads": bool(settings.get("allow_downloads", True)),
            "uploads": bool(settings.get("allow_uploads", True)),
            "text": bool(settings.get("allow_text", True)),
            "trusted_devices": bool(settings.get("allow_trusted_devices", True)),
            "max_upload_mb": int(settings.get("max_upload_mb", 2048) or 2048),
        }

    def _parse_range(self, size: int) -> tuple[int, int] | None:
        raw = self.headers.get("Range")
        if not raw:
            return None
        match = _RANGE_RE.fullmatch(raw.strip())
        if not match:
            raise ValueError("Invalid Range")
        first, last = match.groups()
        if not first and not last:
            raise ValueError("Invalid Range")
        if first:
            start = int(first)
            end = int(last) if last else size - 1
        else:
            suffix = int(last)
            if suffix <= 0:
                raise ValueError("Invalid Range")
            start = max(0, size - suffix)
            end = size - 1
        if start >= size or start < 0 or end < start:
            raise ValueError("Range outside file")
        return start, min(end, size - 1)

    def _stream_file(self, path: Path, download_name: str, *, record=None) -> None:
        size = path.stat().st_size
        try:
            byte_range = self._parse_range(size)
        except ValueError:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return
        start, end = byte_range if byte_range else (0, max(0, size - 1))
        length = 0 if size == 0 else end - start + 1
        content_type = mimetypes.guess_type(download_name)[0] or "application/octet-stream"
        self.send_response(206 if byte_range else 200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Content-Disposition", content_disposition(download_name))
        self.send_header("Accept-Ranges", "bytes")
        if byte_range:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self._security_headers()
        self.end_headers()
        completed = False
        try:
            with path.open("rb") as handle:
                handle.seek(start)
                remaining = length
                while remaining:
                    chunk = handle.read(min(CHUNK_SIZE, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
                completed = remaining == 0
        except (BrokenPipeError, ConnectionResetError):
            pass
        if completed and record:
            record()

    def do_GET(self) -> None:
        if not self._private_only():
            return
        path = urlparse(self.path).path
        if path in ("/", "/connect"):
            self._serve_asset("index.html", "text/html; charset=utf-8")
            return
        if path == "/app.css":
            self._serve_asset("app.css", "text/css; charset=utf-8")
            return
        if path == "/app.js":
            self._serve_asset("app.js", "application/javascript; charset=utf-8")
            return
        if path == "/api/session":
            session = self.qd_server.session
            self._json({
                "authenticated": self._authenticated(),
                "expires_in": session.remaining_seconds,
                "computer": str(self.qd_server.manager.settings.get("computer_name") or os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or "QuickDrop PC"),
                "permissions": self._permissions(),
            })
            return
        if path == "/api/state":
            if not self._require_auth():
                return
            manager = self.qd_server.manager
            client = self._client() or {}
            self._json({
                "files": [item.public_dict() for item in manager.list_shared()],
                "quick_text": manager.quick_text,
                "expires_in": self.qd_server.session.remaining_seconds,
                "permissions": self._permissions(),
                "client": {"name": client.get("name", "Phone")},
            })
            return
        if path == "/api/download-all":
            if not self._require_permission("allow_downloads"):
                return
            bundle = self.qd_server.manager.build_share_bundle()
            if not bundle:
                self._json({"error": "No files are shared"}, 404)
                return
            client = self._client() or {}
            try:
                self._stream_file(bundle, "QuickDrop-Shared.zip", record=lambda: self.qd_server.manager.record_bundle_download(bundle, self.client_address[0], str(client.get("name", ""))))
            finally:
                bundle.unlink(missing_ok=True)
            return
        if path.startswith("/api/download/"):
            if not self._require_permission("allow_downloads"):
                return
            item_id = path.rsplit("/", 1)[-1]
            item = self.qd_server.manager.get_shared(item_id)
            if not item or not item.file_path.is_file():
                self.send_error(404, "File is no longer available")
                return
            client = self._client() or {}
            self._stream_file(item.file_path, item.name, record=lambda: self.qd_server.manager.record_download(item, self.client_address[0], str(client.get("name", ""))))
            return
        self.send_error(404)

    def do_POST(self) -> None:
        if not self._private_only():
            return
        path = urlparse(self.path).path
        if path == "/api/auth":
            try:
                payload = self._read_json(8192)
            except ValueError as exc:
                self._json({"error": str(exc)}, 400)
                return
            client_ip = self.client_address[0]
            attempts, locked_until = self.qd_server.auth_failures.get(client_ip, (0, 0.0))
            if locked_until > time.time():
                self._json({"error": "Too many attempts. Try again in a minute."}, 429)
                return
            pin = str(payload.get("pin", "")).strip()
            if not secrets.compare_digest(pin, self.qd_server.session.pin):
                attempts += 1
                self.qd_server.auth_failures[client_ip] = (0, time.time() + 60) if attempts >= 8 else (attempts, 0.0)
                self._json({"error": "Incorrect PIN"}, 403)
                return
            self.qd_server.auth_failures.pop(client_ip, None)
            name = clean_device_name(str(payload.get("device_name", "My phone")))
            remember = bool(payload.get("remember")) and bool(self.qd_server.manager.settings.get("allow_trusted_devices", True))
            trusted = self.qd_server.devices.issue(name, client_ip) if remember else None
            auth_id = self.qd_server.create_auth(name=name, client_ip=client_ip, trusted_device_id=(trusted or {}).get("id", ""))
            result: dict[str, object] = {"ok": True, "device_name": name}
            if trusted:
                result["trusted_device"] = trusted
            self._json(result, headers=self._auth_headers(auth_id))
            return
        if path == "/api/trusted-auth":
            if not bool(self.qd_server.manager.settings.get("allow_trusted_devices", True)):
                self._json({"error": "Trusted devices are disabled on this PC"}, 403)
                return
            try:
                payload = self._read_json(8192)
            except ValueError as exc:
                self._json({"error": str(exc)}, 400)
                return
            match = self.qd_server.devices.verify(str(payload.get("id", "")), str(payload.get("secret", "")), self.client_address[0])
            if not match:
                self._json({"error": "Remembered device is no longer trusted"}, 403)
                return
            name = clean_device_name(str(match.get("name", "Trusted device")))
            auth_id = self.qd_server.create_auth(name=name, client_ip=self.client_address[0], trusted_device_id=str(match.get("id", "")))
            self._json({"ok": True, "device_name": name}, headers=self._auth_headers(auth_id))
            return
        if path == "/api/text":
            if not self._require_permission("allow_text"):
                return
            try:
                payload = self._read_json(120_000)
            except ValueError as exc:
                self._json({"error": str(exc)}, 400)
                return
            self.qd_server.manager.set_quick_text(str(payload.get("text", "")))
            self._json({"ok": True})
            return
        if path == "/api/upload":
            if not self._require_permission("allow_uploads"):
                return
            raw_name = unquote(self.headers.get("X-QuickDrop-Filename", "received-file"))
            filename = safe_filename(raw_name, "received-file")
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._json({"error": "Invalid file size"}, 400)
                return
            configured_mb = max(1, min(int(self.qd_server.manager.settings.get("max_upload_mb", 2048) or 2048), 10_240))
            max_bytes = min(configured_mb * 1024 * 1024, ABSOLUTE_MAX_UPLOAD_BYTES)
            if length < 0 or length > max_bytes:
                self._json({"error": f"File exceeds the PC upload limit of {configured_mb} MB"}, 413)
                return
            try:
                free = shutil.disk_usage(self.qd_server.manager.inbox).free
                if length > max(0, free - 64 * 1024 * 1024):
                    self._json({"error": "Not enough free space in the receive folder"}, 507)
                    return
            except OSError:
                pass
            destination = self.qd_server.manager.receive_path(filename)
            remaining = length
            client = self._client() or {}
            try:
                with destination.open("wb") as out:
                    while remaining:
                        chunk = self.rfile.read(min(CHUNK_SIZE, remaining))
                        if not chunk:
                            raise ConnectionError("Upload ended early")
                        out.write(chunk)
                        remaining -= len(chunk)
                self.qd_server.manager.record_upload(destination, self.client_address[0], str(client.get("name", "")))
                self._json({"ok": True, "name": destination.name, "size": destination.stat().st_size})
            except Exception as exc:
                destination.unlink(missing_ok=True)
                self._json({"error": f"Upload failed: {exc}"}, 500)
            return
        self.send_error(404)


class ServerController:
    def __init__(self, manager: TransferManager) -> None:
        self.manager = manager
        self.server: QuickDropHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.session: ShareSession | None = None
        self.lan_ip = best_lan_ip()
        self.port = 0

    @property
    def running(self) -> bool:
        return self.server is not None

    @property
    def url(self) -> str:
        return f"http://{self.lan_ip}:{self.port}" if self.port else ""

    def start(self) -> None:
        if self.running:
            return
        minutes = int(self.manager.settings.get("session_minutes", 30))
        self.lan_ip = best_lan_ip()
        self.session = ShareSession(minutes)
        server = QuickDropHTTPServer(("0.0.0.0", 0), self.manager, self.session)
        self.port = int(server.server_address[1])
        self.server = server
        self.thread = threading.Thread(target=server.serve_forever, name="QuickDropServer", daemon=True)
        self.thread.start()

    def restart_session(self) -> None:
        self.stop()
        self.start()

    def stop(self) -> None:
        server = self.server
        self.server = None
        if server is not None:
            server.shutdown()
            server.server_close()
        thread = self.thread
        self.thread = None
        if thread and thread.is_alive():
            thread.join(timeout=2)
        self.port = 0
        self.session = None
