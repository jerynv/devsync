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
