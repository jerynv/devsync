import json
import os
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from devsync import config, cycle, syncthing
from tests.helpers import Fixture, g

os.environ["DEVSYNC_CLONE_PROTOCOLS"] = "file"


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        (self.d / "config.toml").write_text('[machines.a]\n[machines.b]\n[access]\ntailnet_logins = ["X@Y"]\n')

    def tearDown(self):
        self.tmp.cleanup()

    def test_machine_is_required(self):
        with mock.patch.dict(os.environ, {"DEVSYNC_MACHINE": ""}):
            with self.assertRaises(config.ConfigError):
                config.load(self.d)
        with self.assertRaises(config.ConfigError):
            config.load(self.d, "c")
        self.assertEqual(config.load(self.d, "a").tailnet_logins, ["x@y"])

    def test_reload_on_change_and_keep_last_good(self):
        live = config.LiveConfig(self.d, "a")
        self.assertEqual(live.get().tailnet_logins, ["x@y"])
        time.sleep(0.01)
        (self.d / "config.toml").write_text('[machines.a]\n[access]\ntailnet_logins = ["new@y"]\n')
        self.assertEqual(live.get().tailnet_logins, ["new@y"])
        time.sleep(0.01)
        (self.d / "config.toml").write_text("not = [valid toml")
        self.assertEqual(live.get().tailnet_logins, ["new@y"])
        self.assertIn("reload failed", live.error)


class CycleTest(unittest.TestCase):
    def setUp(self):
        self.fx = Fixture()
        self.cdir = Path(self.fx.tmp.name) / "cfg"
        self.sdir = Path(self.fx.tmp.name) / "state"
        self.cdir.mkdir()
        (self.cdir / "config.toml").write_text(f'[machines.a]\n[repos]\nroot = "{self.fx.root}"\n'
                                               f'scan_unlisted = ["GitHub"]\n')
        (self.cdir / "repos.toml").write_text(f'[[repo]]\npath = "GitHub/app"\nurl = "{self.fx.url}"\n'
                                              f'machines = ["a"]\n')
        self.env = mock.patch.dict(os.environ, {"DEVSYNC_CONFIG_DIR": str(self.cdir),
                                                "DEVSYNC_STATE_DIR": str(self.sdir),
                                                "DEVSYNC_SYNCTHING_CONFIG": str(self.cdir / "none.xml")})
        self.env.start()
        self.cfg = config.load(self.cdir, "a")

    def tearDown(self):
        self.env.stop()
        self.fx.close()

    def test_dry_run_writes_nothing(self):
        self.fx.upstream_commit()
        g(self.fx.app, "fetch", "-q")
        head = g(self.fx.app, "rev-parse", "HEAD")
        snap = cycle.run_cycle(self.cfg, dry_run=True)
        self.assertFalse(self.sdir.exists())
        self.assertEqual(g(self.fx.app, "rev-parse", "HEAD"), head)
        self.assertEqual(snap["cycle"]["actions"], ["GitHub/app: would fast-forward 1 commit(s)"])
        full, _ = cycle.report_lines(self.cfg, snap)
        self.assertIn("dry run", full[0])

    def test_real_cycle_writes_report_and_summary(self):
        self.fx.upstream_commit()
        snap = cycle.run_cycle(self.cfg)
        self.assertEqual(snap["cycle"]["actions"], ["GitHub/app: fast-forwarded 1 commit(s)"])
        report = (self.sdir / "report.txt").read_text()
        self.assertIn("devsync report (a, ", report)
        self.assertIn("fast-forwarded 1 commit(s)", report)
        self.assertTrue((self.sdir / "summary.txt").read_text().startswith("devsync ("))

    def test_cycles_never_overlap(self):
        with cycle._Flock(self.sdir / "cycle.lock"):
            with self.assertRaises(cycle.CycleBusy):
                cycle.run_cycle(self.cfg)

    def test_unreadable_root_skips_repo_work(self):
        self.cfg.repos_root = Path(self.fx.tmp.name) / "does-not-exist"
        snap = cycle.run_cycle(self.cfg, dry_run=True)
        self.assertTrue(snap["banner"])
        self.assertEqual(snap["repos"], {})

    def test_runner_sync_now_runs_on_the_cycle_thread(self):
        self.fx.upstream_commit()
        live = config.LiveConfig(self.cdir, "a")
        runner = cycle.Runner(live)
        runner.next_due = time.time() + 3600
        stop = threading.Event()
        t = threading.Thread(target=runner.loop, args=(stop,), daemon=True)
        t.start()
        try:
            self.assertEqual(runner.request_sync(), "queued")
            deadline = time.time() + 20
            while time.time() < deadline and not runner.last_cycle:
                time.sleep(0.05)
            self.assertEqual(runner.last_cycle.get("actions"), ["GitHub/app: fast-forwarded 1 commit(s)"])
            self.assertFalse(runner.state()["cycle"]["running"])
        finally:
            stop.set()
            runner.wake.set()
            t.join(5)


class SyncthingTest(unittest.TestCase):
    def test_health_with_stub(self):
        tmp = tempfile.TemporaryDirectory()
        folder = Path(tmp.name) / "notes"
        (folder / "sub").mkdir(parents=True)
        (folder / "sub" / "a.sync-conflict-20260101-000000-ABC.md").write_text("x")
        (folder / "locked").mkdir()
        os.chmod(folder / "locked", 0)
        (folder / "node_modules").mkdir()
        (folder / "node_modules" / "b.sync-conflict-1.js").write_text("x")
        routes = {
            "/rest/system/connections": {"connections": {"PEER": {"connected": False}}},
            "/rest/config/devices": [{"deviceID": "PEER", "name": "other"}],
            "/rest/config/folders": [{"id": "notes", "label": "Notes", "path": str(folder), "type": "sendreceive",
                                      "paused": True}],
            "/rest/db/status": {"state": "idle", "errors": 2, "pullErrors": 2, "needTotalItems": 3},
            "/rest/folder/errors": {"errors": [{"path": "bad.txt", "error": "x"}]},
            "/rest/system/status": {"myID": "ME"},
            "/rest/stats/device": {"PEER": {"lastSeen": "2026-01-01T00:00:00Z"}},
        }
        seen_keys = []

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                seen_keys.append(self.headers.get("X-API-Key"))
                body = json.dumps(routes[self.path.split("?")[0]]).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)

        srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            xml = (f'<configuration><gui enabled="true" tls="false"><address>127.0.0.1:{srv.server_address[1]}'
                   f'</address><apikey>KEY</apikey></gui></configuration>')
            h = syncthing.health(["node_modules"], walk=True, client=syncthing.Syncthing.from_xml(xml))
        finally:
            srv.shutdown()
            srv.server_close()
            os.chmod(folder / "locked", 0o755)
            tmp.cleanup()
        self.assertTrue(h["reachable"])
        self.assertEqual(set(seen_keys), {"KEY"})
        f = h["folders"][0]
        self.assertEqual((f["paused"], f["errors"], f["need"]), (True, 2, 3))
        self.assertEqual(len(f["conflicts"]), 1)  # node_modules skipped
        self.assertEqual(f["error_paths"], ["bad.txt"])
        notes = " | ".join(h["notes"])
        for want in ["not connected", "2 error(s)", "paused", "1 conflict copy"]:
            self.assertIn(want, notes)
        if os.geteuid() != 0:
            self.assertIn("could not read 1 folder", notes)

    def test_counts_and_remote_completion(self):
        routes = {
            "/rest/system/connections": {"connections": {"PEER": {"connected": True}}},
            "/rest/config/devices": [{"deviceID": "ME", "name": "here"}, {"deviceID": "PEER", "name": "other"}],
            "/rest/config/folders": [{"id": "f", "label": "F", "path": "/nonexistent", "type": "sendreceive",
                                      "devices": [{"deviceID": "ME"}, {"deviceID": "PEER"}]}],
            "/rest/db/status": {"state": "idle", "localFiles": 10, "globalFiles": 12, "needBytes": 2048},
            "/rest/system/status": {"myID": "ME"},
            "/rest/stats/device": {},
            "/rest/db/completion": {"completion": 91.234, "needItems": 3, "needBytes": 4096},
        }

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                body = json.dumps(routes[self.path.split("?")[0]]).encode()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(body)

        srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            xml = (f'<configuration><gui enabled="true" tls="false"><address>127.0.0.1:{srv.server_address[1]}'
                   f'</address><apikey>K</apikey></gui></configuration>')
            h = syncthing.health([], walk=False, client=syncthing.Syncthing.from_xml(xml))
        finally:
            srv.shutdown()
            srv.server_close()
        f = h["folders"][0]
        self.assertEqual((f["local_files"], f["global_files"], f["need_bytes"]), (10, 12, 2048))
        self.assertEqual(f["devices"], ["other"])  # this machine is left out
        self.assertEqual(f["remote"], [{"name": "other", "completion": 91.2, "need_items": 3, "need_bytes": 4096}])

    def test_unreachable(self):
        c = syncthing.Syncthing("http://127.0.0.1:9/rest", "k", False)
        h = syncthing.health([], walk=False, client=c)
        self.assertFalse(h["reachable"])
        self.assertIn("not reachable", h["notes"][0])


if __name__ == "__main__":
    unittest.main()
