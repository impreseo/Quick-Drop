from __future__ import annotations

import http.client
import json
import tempfile
import unittest
from pathlib import Path

from quickdrop.services.server import ServerController
from quickdrop.services.transfer import TransferManager


class ServerFlowTests(unittest.TestCase):
    def setUp(self):
        self.data = tempfile.TemporaryDirectory(); self.inbox = tempfile.TemporaryDirectory()
        self.manager = TransferManager(data_dir=self.data.name, inbox_dir=self.inbox.name)
        self.controller = ServerController(self.manager); self.controller.start(); self.port = self.controller.port

    def tearDown(self):
        self.controller.stop(); self.manager.close(); self.inbox.cleanup(); self.data.cleanup()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=4)
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse(); payload = response.read(); headers_out = response.getheaders(); status=response.status; conn.close()
        return status, headers_out, payload

    @staticmethod
    def header_values(headers, name):
        return [v for k,v in headers if k.lower()==name.lower()]

    def authenticate(self, *, remember=False, device="Test Phone"):
        body = json.dumps({"pin": self.controller.session.pin, "device_name": device, "remember": remember}).encode()
        status, headers, payload = self.request("POST", "/api/auth", body, {"Content-Type":"application/json","Content-Length":str(len(body))})
        self.assertEqual(status, 200, payload)
        cookie = self.header_values(headers, "Set-Cookie")[0].split(";",1)[0]
        return cookie, json.loads(payload)

    def test_full_upload_download_range_and_download_all(self):
        cookie,_ = self.authenticate()
        source = Path(self.data.name) / "source.txt"; source.write_bytes(b"quickdrop-download")
        shared = self.manager.add_file(source)
        status,_,payload=self.request("GET","/api/state",headers={"Cookie":cookie}); self.assertEqual(status,200); self.assertEqual(json.loads(payload)["files"][0]["name"],"source.txt")
        status,headers,payload=self.request("GET",f"/api/download/{shared.id}",headers={"Cookie":cookie,"Range":"bytes=10-"}); self.assertEqual(status,206); self.assertEqual(payload,b"download"); self.assertIn("bytes 10-17/18", self.header_values(headers,"Content-Range"))
        status,_,payload=self.request("GET","/api/download-all",headers={"Cookie":cookie}); self.assertEqual(status,200); self.assertTrue(payload.startswith(b"PK"))
        upload=b"hello-from-phone"; status,_,payload=self.request("POST","/api/upload",upload,{"Cookie":cookie,"Content-Length":str(len(upload)),"X-QuickDrop-Filename":"phone%20note.txt"}); self.assertEqual(status,200,payload); result=json.loads(payload); self.assertEqual((self.manager.inbox/result["name"]).read_bytes(),upload)
        status,_,payload=self.request("POST","/api/upload",upload,{"Cookie":cookie,"Content-Length":str(len(upload)),"X-QuickDrop-Filename":"phone%20note.txt"}); self.assertEqual(status,200,payload); self.assertEqual(json.loads(payload)["name"],"phone note (2).txt")

    def test_permissions_are_enforced(self):
        cookie,_=self.authenticate(); source=Path(self.data.name)/"x.txt"; source.write_text("x"); item=self.manager.add_file(source)
        self.manager.settings["allow_downloads"]=False; status,_,_=self.request("GET",f"/api/download/{item.id}",headers={"Cookie":cookie}); self.assertEqual(status,403)
        self.manager.settings["allow_uploads"]=False; status,_,_=self.request("POST","/api/upload",b"x",{"Cookie":cookie,"Content-Length":"1","X-QuickDrop-Filename":"x.txt"}); self.assertEqual(status,403)
        self.manager.settings["allow_text"]=False; body=b'{"text":"hello"}'; status,_,_=self.request("POST","/api/text",body,{"Cookie":cookie,"Content-Length":str(len(body)),"Content-Type":"application/json"}); self.assertEqual(status,403)

    def test_trusted_device_can_auth_next_session_and_be_revoked(self):
        _,data=self.authenticate(remember=True,device="Pixel")
        cred=data["trusted_device"]; self.controller.restart_session(); self.port=self.controller.port
        body=json.dumps(cred).encode(); status,headers,payload=self.request("POST","/api/trusted-auth",body,{"Content-Type":"application/json","Content-Length":str(len(body))}); self.assertEqual(status,200,payload); self.assertTrue(self.header_values(headers,"Set-Cookie"))
        self.assertTrue(self.controller.server.devices.revoke(cred["id"])); self.controller.restart_session(); self.port=self.controller.port
        status,_,_=self.request("POST","/api/trusted-auth",body,{"Content-Type":"application/json","Content-Length":str(len(body))}); self.assertEqual(status,403)

    def test_upload_limit(self):
        cookie,_=self.authenticate(); self.manager.settings["max_upload_mb"]=1
        status,_,_=self.request("POST","/api/upload",b"",{"Cookie":cookie,"Content-Length":str(2*1024*1024),"X-QuickDrop-Filename":"big.bin"}); self.assertEqual(status,413)

    def test_phone_page_security_headers_and_auth_required(self):
        status,headers,payload=self.request("GET","/"); self.assertEqual(status,200); self.assertIn(b"Remember this device",payload); self.assertTrue(self.header_values(headers,"Content-Security-Policy"))
        status,_,_=self.request("GET","/api/state"); self.assertEqual(status,401)

    def test_repeated_bad_pins_are_throttled(self):
        bad="999999" if self.controller.session.pin!="999999" else "888888"
        for _ in range(8):
            body=json.dumps({"pin":bad}).encode(); status,_,_=self.request("POST","/api/auth",body,{"Content-Type":"application/json","Content-Length":str(len(body))}); self.assertEqual(status,403)
        body=json.dumps({"pin":self.controller.session.pin}).encode(); status,_,_=self.request("POST","/api/auth",body,{"Content-Type":"application/json","Content-Length":str(len(body))}); self.assertEqual(status,429)


if __name__ == "__main__": unittest.main()
