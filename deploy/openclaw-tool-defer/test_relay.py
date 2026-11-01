"""中継の試験。偽の上流 (MCP サーバーの代わり) を立て、中継越しに tools/list と tools/call を送る。

python3 -m unittest deploy/openclaw-tool-defer/test_relay.py
"""
import http.client
import http.server
import json
import os
import socketserver
import tempfile
import threading
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


class FakeUpstream(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    seen_headers = []

    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeUpstream.seen_headers.append(dict(self.headers))
        if body["method"] == "tools/list":
            result = {"tools": [{"name": "exec", "inputSchema": {}}, {"name": "workboard_create", "inputSchema": {}, "_meta": {"x": 1}}]}
        else:
            result = {"content": [{"type": "text", "text": "ok"}]}
        msg = {"jsonrpc": "2.0", "id": body["id"], "result": result}
        if self.headers.get("X-Want-Sse"):
            payload = ("event: message\ndata: " + json.dumps(msg) + "\n\n").encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Transfer-Encoding", "chunked")
            self.send_header("Mcp-Session-Id", "abc")
            self.end_headers()
            self.wfile.write(b"%x\r\n%s\r\n0\r\n\r\n" % (len(payload), payload))
        else:
            payload = json.dumps(msg).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Mcp-Session-Id", "abc")
            self.end_headers()
            self.wfile.write(payload)


class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class S(socketserver.ThreadingMixIn, http.server.HTTPServer):
            daemon_threads = True
        cls.up = S(("127.0.0.1", 0), FakeUpstream)
        threading.Thread(target=cls.up.serve_forever, daemon=True).start()
        cls.tmp = tempfile.mkdtemp()
        keep = os.path.join(cls.tmp, "keep.txt")
        with open(keep, "w") as fh:
            fh.write("# comment\nexec\n")
        os.environ["TOOL_DEFER_KEEP"] = keep
        os.environ["TOOL_DEFER_LOG"] = os.path.join(cls.tmp, "relay.log")
        import importlib.util
        spec = importlib.util.spec_from_file_location("relay", os.path.join(HERE, "relay.py"))
        cls.relay = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.relay)
        cls.srv = cls.relay.Server(("127.0.0.1", 0), cls.relay.Handler)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        time.sleep(0.1)

    def post(self, method, sse=False):
        c = http.client.HTTPConnection("127.0.0.1", self.srv.server_address[1])
        h = {"Content-Type": "application/json", "Authorization": "Bearer t", "Mcp-Session-Id": "abc"}
        if sse:
            h["X-Want-Sse"] = "1"
        c.request("POST", f"/p/{self.up.server_address[1]}/mcp", body=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method}), headers=h)
        r = c.getresponse()
        return r, r.read()

    def check_marks(self, msg):
        tools = {t["name"]: t for t in msg["result"]["tools"]}
        self.assertNotIn("_meta", tools["exec"])
        self.assertEqual(tools["workboard_create"]["_meta"], {"x": 1, "anthropic/alwaysLoad": False})

    def test_tools_list_json(self):
        r, body = self.post("tools/list")
        self.assertEqual(r.status, 200)
        self.check_marks(json.loads(body))
        self.assertEqual(r.getheader("Mcp-Session-Id"), "abc")

    def test_tools_list_sse(self):
        r, body = self.post("tools/list", sse=True)
        data = [l for l in body.decode().split("\n") if l.startswith("data:")][0]
        self.check_marks(json.loads(data[5:]))

    def test_other_calls_pass_through(self):
        r, body = self.post("tools/call")
        self.assertEqual(json.loads(body)["result"]["content"][0]["text"], "ok")
        r, body = self.post("tools/call", sse=True)
        self.assertIn(b'"text": "ok"', body)
        self.assertEqual(FakeUpstream.seen_headers[-1]["Authorization"], "Bearer t")

    def test_only_loopback_ports_paths(self):
        c = http.client.HTTPConnection("127.0.0.1", self.srv.server_address[1])
        c.request("POST", "/elsewhere/mcp", body="{}")
        self.assertEqual(c.getresponse().status, 404)

    def test_wrapper_rewrite(self):
        import importlib.machinery, importlib.util
        loader = importlib.machinery.SourceFileLoader("wrapper", os.path.join(HERE, "bin", "claude"))
        spec = importlib.util.spec_from_loader("wrapper", loader)
        w = importlib.util.module_from_spec(spec)
        loader.exec_module(w)
        cfg = {"mcpServers": {"openclaw": {"type": "http", "url": "http://127.0.0.1:41234/mcp", "alwaysLoad": True}}}
        self.assertTrue(w.rewrite(cfg))
        self.assertEqual(cfg["mcpServers"]["openclaw"]["url"], f"http://127.0.0.1:{w.RELAY_PORT}/p/41234/mcp")
        self.assertTrue(cfg["mcpServers"]["openclaw"]["alwaysLoad"])
        self.assertFalse(w.rewrite({"mcpServers": {"other": {}}}))


if __name__ == "__main__":
    unittest.main()
