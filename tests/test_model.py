import unittest

from devsync import model


class RepoCellTest(unittest.TestCase):
    def test_not_kept_and_no_data(self):
        self.assertEqual(model.repo_cell(None, kept=False)["status"], "absent")
        self.assertEqual(model.repo_cell(None, kept=True)["status"], "none")

    def test_states(self):
        base = {"present": True, "is_repo": True, "branch": "main", "upstream": "origin/main"}
        cases = [
            (base, "ok", "in sync"),
            ({**base, "upstream": ""}, "info", "no upstream"),
            ({**base, "behind": 2, "dirty": 1}, "warn", "2 behind, 1 uncommitted"),
            ({**base, "fetch_error": "auth"}, "bad", "fetch failed"),
            ({"present": False}, "warn", "not cloned"),
            ({"present": True, "is_repo": False}, "bad", "not a repo"),
            ({"error": "permission denied"}, "bad", "error"),
        ]
        for st, status, label in cases:
            with self.subTest(label=label):
                cell = model.repo_cell(st, kept=True)
                self.assertEqual((cell["status"], cell["label"]), (status, label))

    def test_issue_tags_drive_filters(self):
        cell = model.repo_cell({"present": True, "is_repo": True, "branch": "m", "upstream": "o/m",
                                "ahead": 1, "behind": 1, "dirty": 3}, kept=True)
        self.assertEqual([i["tag"] for i in cell["issues"]], ["behind", "unpushed", "uncommitted"])


class FolderCellTest(unittest.TestCase):
    def test_states(self):
        sy = {"reachable": True}
        self.assertEqual(model.folder_cell(None, None)["status"], "none")
        self.assertEqual(model.folder_cell(None, sy)["status"], "absent")
        self.assertEqual(model.folder_cell({"state": "idle"}, sy)["label"], "up to date")
        self.assertEqual(model.folder_cell({"state": "syncing"}, sy)["status"], "info")
        bad = model.folder_cell({"state": "idle", "paused": True, "conflicts": ["/home/u/a.sync-conflict-1"]}, sy)
        self.assertEqual(bad["status"], "bad")
        self.assertEqual(bad["conflicts"], ["~/a.sync-conflict-1"])


class HelpersTest(unittest.TestCase):
    def test_tilde_and_short_url(self):
        self.assertEqual(model.tilde("/Users/someone/Documents/x"), "~/Documents/x")
        self.assertEqual(model.tilde("/srv/x"), "/srv/x")
        self.assertEqual(model.short_url("git@example.com:me/app.git"), "example.com/me/app")
        self.assertEqual(model.short_url("https://example.com/me/app.git"), "example.com/me/app")

    def test_worst(self):
        self.assertEqual(model.worst(["ok", "warn", "info"]), "warn")
        self.assertEqual(model.worst(["none", "absent"]), "ok")


if __name__ == "__main__":
    unittest.main()


class DriftTest(unittest.TestCase):
    def setUp(self):
        from types import SimpleNamespace as NS
        self.cfg = NS(machine="a", interval_s=900, repos=[
            {"path": "GitHub/app", "machines": ["a", "b"]},
            {"path": "GitHub/lib", "machines": ["a", "b"]},
            {"path": "GitHub/docs", "machines": ["a", "b"]},
            {"path": "GitHub/same", "machines": ["a", "b"]},
        ])
        import time
        now = time.time()
        repo = lambda **k: {"present": True, "is_repo": True, "branch": "main", "upstream": "origin/main", **k}
        folder = lambda fid, **k: {"id": fid, "label": fid, "state": "idle", "need": 0, "local_files": 10, **k}
        self.states = {
            "a": {"version": "1", "cycle": {"finished": now}, "repos": {
                    "GitHub/app": repo(head="aaa1111", ahead=1), "GitHub/lib": repo(head="c0ffee0"),
                    "GitHub/docs": repo(head="d0c5"), "GitHub/same": repo(head="5ame")},
                  "syncthing": {"reachable": True, "connected": [{"name": "b", "connected": True}], "folders": [
                    folder("notes", remote=[{"name": "b", "completion": 80.5, "need_items": 4, "need_bytes": 2048}]),
                    folder("photos"), folder("music", local_files=10)]},
                  "skills": {"source_exists": True, "skills": ["x", "y"]}},
            "b": {"version": "2", "cycle": {"finished": now - 10000}, "repos": {
                    "GitHub/app": repo(head="bbb2222", behind=1), "GitHub/lib": repo(branch="dev", head="1"),
                    "GitHub/docs": {"present": False}, "GitHub/same": repo(head="5ame")},
                  "syncthing": {"reachable": True, "connected": [{"name": "a", "connected": False}], "folders": [
                    folder("notes"), folder("music", local_files=12, paused=True)]},
                  "skills": {"source_exists": True, "skills": ["x"]}},
        }

    def kinds(self):
        d = model.drift(self.cfg, ["a", "b"], self.states, {"b": {"fetched": __import__("time").time()}})
        return {(x["kind"], x["subject"]): x for x in d}, d

    def test_every_kind_of_disagreement(self):
        k, d = self.kinds()
        self.assertIn("aaa1111 · 1 unpushed", k[("commit", "GitHub/app")]["machines"]["a"])
        self.assertIn("1 behind origin/main", k[("commit", "GitHub/app")]["machines"]["b"])
        self.assertEqual(k[("branch", "GitHub/lib")]["machines"], {"a": "main", "b": "dev"})
        self.assertIn("missing on b", k[("missing", "GitHub/docs")]["summary"])
        self.assertNotIn(("commit", "GitHub/same"), k)
        self.assertIn("not on b", k[("not-shared", "photos")]["summary"])
        self.assertIn("80.5%", k[("catching-up", "notes")]["summary"])
        self.assertIn(("paused-one", "music"), k)
        self.assertNotIn(("file-count", "music"), k)  # paused/unsettled: counts aren't comparable
        self.assertIn(("stale-sync", "b"), k)
        self.assertIn(("disconnected", "b → a"), k)
        self.assertEqual(k[("version", "devsync")]["machines"], {"a": "1", "b": "2"})
        self.assertEqual(k[("differ", "skills folder")]["machines"], {"b": "missing y"})
        self.assertEqual([x["tone"] for x in d], sorted([x["tone"] for x in d], key=["bad", "warn", "info"].index))

    def test_file_counts_compared_only_when_settled(self):
        self.states["b"]["syncthing"]["folders"][1].pop("paused")
        k, _ = self.kinds()
        self.assertEqual(k[("file-count", "music")]["machines"], {"a": "10 files", "b": "12 files"})

    def test_peer_without_data_or_unreachable(self):
        st = {"a": self.states["a"]}
        d = model.drift(self.cfg, ["a", "b"], st, {"b": {"error": "timed out"}})
        self.assertEqual([(x["kind"], x["summary"]) for x in d if x["area"] == "machines"][0], ("no-data", "timed out"))

    def test_old_peers_without_new_fields_do_not_crash(self):
        for r in self.states["b"]["repos"].values():
            r.pop("head", None)
        k, _ = self.kinds()
        self.assertNotIn(("commit", "GitHub/app"), k)  # unknown head: no claim either way


class HistoryTest(unittest.TestCase):
    def test_runner_keeps_a_bounded_newest_first_history(self):
        from devsync import cycle
        r = cycle.Runner.__new__(cycle.Runner)
        import threading
        r.lock, r.history = threading.Lock(), []
        for i in range(cycle.HISTORY + 5):
            r._remember({"finished": i})
        self.assertEqual(len(r.history), cycle.HISTORY)
        self.assertEqual(r.history[0]["finished"], cycle.HISTORY + 4)
