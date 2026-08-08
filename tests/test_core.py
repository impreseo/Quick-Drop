from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from quickdrop.core.devices import DeviceRegistry
from quickdrop.core.security import is_private_client, safe_filename, unique_path
from quickdrop.services.server import ShareSession
from quickdrop.services.transfer import TransferManager


class CoreTests(unittest.TestCase):
    def test_safe_filename_removes_path_and_windows_chars(self):
        self.assertEqual(safe_filename(r"..\\bad<name>?.txt"), "bad_name__.txt")
        self.assertEqual(safe_filename("../../hello.txt"), "hello.txt")

    def test_private_client(self):
        self.assertTrue(is_private_client("127.0.0.1"))
        self.assertTrue(is_private_client("192.168.1.4"))
        self.assertFalse(is_private_client("8.8.8.8"))

    def test_unique_path(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); (root / "photo.jpg").write_bytes(b"a")
            self.assertEqual(unique_path(root, "photo.jpg").name, "photo (2).jpg")

    def test_session_pin_and_expiry(self):
        session = ShareSession(5)
        self.assertTrue(session.active)
        self.assertEqual(len(session.pin), 6)
        self.assertTrue(session.pin.isdigit())

    def test_transfer_file_folder_bundle_and_isolated_storage(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as data, tempfile.TemporaryDirectory() as inbox:
            root = Path(td); file = root / "hello.txt"; file.write_text("hello", encoding="utf-8")
            folder = root / "docs"; folder.mkdir(); (folder / "a.txt").write_text("A", encoding="utf-8")
            manager = TransferManager(data_dir=data, inbox_dir=inbox)
            item = manager.add_file(file); zipped = manager.add_folder(folder); bundle = manager.build_share_bundle()
            self.assertEqual(item.size, 5); self.assertTrue(zipped.file_path.exists()); self.assertIsNotNone(bundle); self.assertTrue(bundle.exists())
            manager.remove_shared(zipped.id); self.assertFalse(zipped.file_path.exists()); manager.close()

    def test_trusted_device_issue_verify_revoke(self):
        with tempfile.TemporaryDirectory() as data:
            registry = DeviceRegistry(data)
            credential = registry.issue("Niranjan Phone", "192.168.1.9")
            match = registry.verify(credential["id"], credential["secret"], "192.168.1.10")
            self.assertEqual(match["name"], "Niranjan Phone")
            self.assertIsNone(registry.verify(credential["id"], "wrong", "192.168.1.10"))
            self.assertTrue(registry.revoke(credential["id"]))
            self.assertIsNone(registry.verify(credential["id"], credential["secret"], "192.168.1.10"))


if __name__ == "__main__":
    unittest.main()
