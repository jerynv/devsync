import http.client
import json
import re
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path

from devsync import model, server
from devsync.config import LiveConfig
from devsync.cycle import Runner
from devsync.peers import Peers

LOGIN = "owner@example.invalid"


def write_config(d: Path, peer_url="http://127.0.0.1:9"):
    (d / "config.toml").write_text(f"""
[machines.a]
tailnet_url = "http://a-host"
[machines.b]
tailnet_url = "{peer_url}"
[access]
tailnet_logins = ["{LOGIN}"]
tailnet_hosts = ["a-host", "a-host.example.ts.net"]
tailscale_cli = ["/bin/false"]
[repos]
root = "{d}"
""")
    (d / "repos.toml").write_text('[[repo]]\npath = "GitHub/app"\nurl = ""\nmachines = ["a", "b"]\n')


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = Path(cls.tmp.name)
        # A peer that accepts connections but never answers: fetches must time out, not hang the UI.
        cls.silent = socket.socket()
        cls.silent.bind(("127.0.0.1", 0))
        cls.silent.listen(8)
        write_config(d, f"http://127.0.0.1:{cls.silent.getsockname()[1]}")
        cls.live = LiveConfig(d, "a")
        cls.runner = Runner(cls.live)
        cls.runner.enabled = False
        cls.runner.snap = {"machine": "a", "version": "t", "generated": time.time(),
                           "repos": {"GitHub/app": {"path": "GitHub/app", "present": True, "is_repo": True,
                                                    "branch": "<script>alert(1)</script>",
                                                    "notes": ["GitHub/app: 2 uncommitted change(s)"]}},
                           "syncthing": {"reachable": False, "error": "x", "notes": []}, "skills": {}}
        cls.peers = Peers(cls.live)
        app = server.App(cls.live, cls.runner, cls.peers)
        cls.local = server.bind(app, "local", "127.0.0.1", 0)
        cls.tailnet = server.bind(app, "tailnet", "127.0.0.1", 0)
        for s in (cls.local, cls.tailnet):
            threading.Thread(target=s.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        for s in (cls.local, cls.tailnet):
            s.shutdown()
            s.server_close()
        cls.silent.close()
        cls.tmp.cleanup()

    def req(self, srv, method="GET", path="/", headers=None, host="devsync.localhost"):
        c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=5)
        h = {"Host": host}
        h.update(headers or {})
        c.request(method, path, headers=h)
        r = c.getresponse()
        body = r.read()
        c.close()
        return r.status, dict(r.getheaders()), body

    # --- local listener ------------------------------------------------------------------
    def test_local_page_and_security_headers(self):
        status, headers, body = self.req(self.local)
        self.assertEqual(status, 200)
        self.assertIn("default-src 'self'", headers["Content-Security-Policy"])
        self.assertIn("script-src 'self';", headers["Content-Security-Policy"])
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertIn(b'<div id="root">', body)
        self.assertNotIn(b"<script>", body)  # no inline script: the CSP would block it

    def test_dashboard_is_json_built_from_the_live_snapshot(self):
        status, headers, body = self.req(self.local, path="/api/dashboard")
        self.assertEqual(status, 200)
        self.assertTrue(headers["Content-Type"].startswith("application/json"))
        d = json.loads(body)
        self.assertEqual(d["me"], "a")
        self.assertEqual([m["name"] for m in d["machines"]], ["a", "b"])
        cell = d["repos"][0]["machines"]["a"]
        self.assertEqual(cell["branch"], "<script>alert(1)</script>")  # data, rendered as text by the page
        self.assertEqual(d["attention"][0]["messages"], ["2 uncommitted change(s)"])

    def test_built_assets(self):
        _, _, page = self.req(self.local)
        assets = re.findall(rb'(?:src|href)="(/assets/[^"]+)"', page)
        self.assertTrue(assets, "index.html references no built assets; run the ui build")
        for a in assets:
            status, headers, _ = self.req(self.local, path=a.decode())
            self.assertEqual(status, 200)
            self.assertIn("immutable", headers["Cache-Control"])
        status, headers, _ = self.req(self.local, path="/theme.js")
        self.assertEqual((status, headers["Cache-Control"]), (200, "no-store"))
        css = next(a for a in assets if a.endswith(b".css"))
        fonts = re.findall(rb"url\((/assets/[^)]+\.woff2)\)", self.req(self.local, path=css.decode())[2])
        self.assertEqual(len(fonts), 2)
        status, headers, body = self.req(self.local, path=fonts[0].decode())
        self.assertEqual((status, headers["Content-Type"]), (200, "font/woff2"))
        self.assertTrue(body.startswith(b"wOF2"))

    def test_attention_groups_notes_by_repo(self):
        st = {"repos": {"GitHub/app": {"notes": ["GitHub/app: 1 behind", "GitHub/app: 2 dirty"]}},
              "banner": "Documents is unreadable"}
        groups = model.attention(["a"], {"a": st})
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0], {"machine": "a", "subject": "Documents is unreadable", "messages": []})
        self.assertEqual(groups[1]["messages"], ["1 behind", "2 dirty"])

    def test_local_rejects_foreign_host(self):
        for host in ["evil.example", "devsync.localhost.evil.example", "a-host"]:
            with self.subTest(host=host):
                self.assertEqual(self.req(self.local, host=host)[0], 421)

    def test_local_accepts_loopback_names(self):
        for host in ["devsync.localhost:8765", "localhost", "127.0.0.1:80", "[::1]:8765"]:
            with self.subTest(host=host):
                self.assertEqual(self.req(self.local, path="/api/state", host=host)[0], 200)

    def test_post_needs_header_and_same_origin(self):
        self.assertEqual(self.req(self.local, "POST", "/api/sync")[0], 403)
        self.assertEqual(self.req(self.local, "POST", "/api/sync",
                                  {"X-Devsync": "1", "Origin": "http://evil.example"})[0], 403)
        self.assertEqual(self.req(self.local, "POST", "/api/sync",
                                  {"X-Devsync": "1", "Origin": "null"})[0], 403)
        self.assertEqual(self.req(self.local, "POST", "/api/sync",
                                  {"X-Devsync": "1", "Sec-Fetch-Site": "cross-site"})[0], 403)
        status, _, body = self.req(self.local, "POST", "/api/sync",
                                   {"X-Devsync": "1", "Origin": "http://devsync.localhost:8765",
                                    "Sec-Fetch-Site": "same-origin"})
        self.assertEqual(status, 202)
        self.assertEqual(json.loads(body)["status"], "disabled")

    def test_other_methods_refused(self):
        self.assertEqual(self.req(self.local, "DELETE", "/api/sync")[0], 405)

    # --- tailnet listener ----------------------------------------------------------------
    def test_tailnet_requires_allowlisted_login(self):
        self.assertEqual(self.req(self.tailnet, path="/api/state", host="a-host")[0], 403)
        self.assertEqual(self.req(self.tailnet, path="/api/state", host="a-host",
                                  headers={"Tailscale-User-Login": "someone@else"})[0], 403)

    def test_tailnet_host_header_does_not_switch_trust(self):
        # Forged local Host on the tailnet listener still needs identity, and isn't a tailnet name.
        self.assertEqual(self.req(self.tailnet, path="/api/state", host="devsync.localhost",
                                  headers={"Tailscale-User-Login": "someone@else"})[0], 403)
        self.assertEqual(self.req(self.tailnet, path="/api/state", host="devsync.localhost",
                                  headers={"Tailscale-User-Login": LOGIN})[0], 421)

    def test_tailnet_allowed(self):
        for host in ["a-host", "A-HOST", "a-host.example.ts.net"]:
            with self.subTest(host=host):
                self.assertEqual(self.req(self.tailnet, path="/api/state", host=host,
                                          headers={"Tailscale-User-Login": LOGIN.upper()})[0], 200)

    def test_tailnet_post_origin_must_be_tailnet_name(self):
        h = {"Tailscale-User-Login": LOGIN, "X-Devsync": "1"}
        self.assertEqual(self.req(self.tailnet, "POST", "/api/sync", {**h, "Origin": "http://devsync.localhost"},
                                  host="a-host")[0], 403)
        self.assertEqual(self.req(self.tailnet, "POST", "/api/sync", {**h, "Origin": "http://a-host"},
                                  host="a-host")[0], 202)

    # --- peers ---------------------------------------------------------------------------
    def test_peer_timeout_keeps_last_state_and_never_blocks_requests(self):
        self.peers.data["b"] = {"state": {"machine": "b"}, "fetched": 123.0, "tried": 0}
        url = self.live.get().machines["b"].tailnet_url
        t = threading.Thread(target=self.peers.fetch_one, args=("b", url))
        start = time.time()
        t.start()
        status, _, _ = self.req(self.local, path="/api/dashboard")
        self.assertEqual(status, 200)
        self.assertLess(time.time() - start, 1.0)  # page served while the peer fetch hangs
        t.join(5)
        entry = self.peers.snapshot()["b"]
        self.assertTrue(entry["error"])
        self.assertEqual(entry["state"], {"machine": "b"})
        self.assertEqual(entry["fetched"], 123.0)

    def test_api_state_does_not_trigger_refresh_or_peer_activity(self):
        self.peers.ui_seen = 0
        saved = self.runner.snap["generated"]
        self.runner.snap["generated"] = 0  # stale
        try:
            self.req(self.local, path="/api/state")
            self.assertEqual(self.peers.ui_seen, 0)
            self.assertFalse(self.runner._refreshing)
        finally:
            self.runner.snap["generated"] = saved

    def test_page_never_renders_markup_from_data(self):
        # Peer and repo data reach the page as JSON and React renders it as text. Keep it that way.
        src = Path(__file__).resolve().parent.parent / "ui" / "src"
        for f in src.rglob("*.ts*"):
            text = f.read_text()
            with self.subTest(file=f.name):
                self.assertNotIn("dangerouslySetInnerHTML", text)
                self.assertNotIn("innerHTML", text)


class HostOnlyTest(unittest.TestCase):
    def test_host_only(self):
        self.assertEqual(server.host_only("Devsync.Localhost:80"), "devsync.localhost")
        self.assertEqual(server.host_only("[::1]:8765"), "[::1]")
        self.assertEqual(server.host_only("[fd7a::1]"), "[fd7a::1]")
        self.assertEqual(server.host_only(""), "")


if __name__ == "__main__":
    unittest.main()
