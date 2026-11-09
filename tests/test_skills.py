import os
import tempfile
import unittest
from pathlib import Path

from devsync import skills
from devsync.config import Config


def make_cfg(base: Path) -> Config:
    return Config(
        machine="a", machines={}, tailnet_logins=[], tailnet_hosts=[], tailscale_cli=[],
        repos_root=base, scan_unlisted=[], repos=[], folders=[],
        skills_source=base / "agents/skills", skills_targets=[base / "claude/skills", base / "work/skills"],
        skills_prune_prefixes=[base / "codex/skills"],
        instructions=base / "agents/CLAUDE.md",
        instruction_links=[base / "claude/CLAUDE.md", base / "work/CLAUDE.md", base / "codex/AGENTS.md"],
    )


class SkillsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        for d in ["agents/skills/alpha", "agents/skills/beta", "claude", "work", "codex"]:
            (self.base / d).mkdir(parents=True)
        (self.base / "agents/CLAUDE.md").write_text("rules\n")
        self.cfg = make_cfg(self.base)

    def tearDown(self):
        self.tmp.cleanup()

    def test_links_created_and_check_reports_ok(self):
        skills.apply(self.cfg)
        for t in ["claude/skills", "work/skills"]:
            for s in ["alpha", "beta"]:
                link = self.base / t / s
                self.assertTrue(link.is_symlink())
                self.assertEqual(os.readlink(link), str(self.base / "agents/skills" / s))
        c = skills.check(self.cfg)
        self.assertTrue(all(r["status"] == "ok" for t in c["targets"] for r in t["links"]))
        self.assertEqual(skills.apply(self.cfg), ([], []))  # idempotent

    def test_real_folder_is_never_touched(self):
        real = self.base / "claude/skills/alpha"
        real.mkdir(parents=True)
        (real / "keep.txt").write_text("mine")
        actions, notes = skills.apply(self.cfg)
        self.assertFalse(real.is_symlink())
        self.assertEqual((real / "keep.txt").read_text(), "mine")
        self.assertTrue(any("real folder" in n for n in notes))

    def test_dangling_links_into_shared_folder_are_pruned_others_kept(self):
        t = self.base / "claude/skills"
        t.mkdir()
        os.symlink(str(self.base / "agents/skills/gone"), t / "gone")
        os.symlink(str(self.base / "codex/skills/old"), t / "old")
        os.symlink(str(self.base / "elsewhere/x"), t / "foreign")
        skills.apply(self.cfg)
        self.assertFalse((t / "gone").is_symlink())
        self.assertFalse((t / "old").is_symlink())
        self.assertTrue((t / "foreign").is_symlink())

    def test_wrong_target_link_is_retargeted(self):
        t = self.base / "claude/skills"
        t.mkdir()
        os.symlink(str(self.base / "codex"), t / "alpha")
        skills.apply(self.cfg)
        self.assertEqual(os.readlink(t / "alpha"), str(self.base / "agents/skills/alpha"))

    def test_instruction_links(self):
        (self.base / "work/CLAUDE.md").write_text("rules\n")        # identical copy -> linked
        (self.base / "codex/AGENTS.md").write_text("different\n")   # differs -> left alone
        skills.apply(self.cfg)
        self.assertTrue((self.base / "claude/CLAUDE.md").is_symlink())
        self.assertTrue((self.base / "work/CLAUDE.md").is_symlink())
        self.assertFalse((self.base / "codex/AGENTS.md").is_symlink())
        self.assertEqual((self.base / "codex/AGENTS.md").read_text(), "different\n")

    def test_check_does_not_write(self):
        before = sorted(str(p) for p in self.base.rglob("*"))
        skills.check(self.cfg)
        self.assertEqual(sorted(str(p) for p in self.base.rglob("*")), before)


if __name__ == "__main__":
    unittest.main()


class NamingTest(unittest.TestCase):
    @unittest.skipIf(os.geteuid() == 0, "root ignores permissions")
    def test_unreadable_folders_are_reported(self):
        from unittest import mock
        from devsync import naming
        with tempfile.TemporaryDirectory() as home:
            docs = Path(home) / "Documents" / "notes"
            (docs / "Bad Name").mkdir(parents=True)
            (docs / "locked").mkdir()
            os.chmod(docs / "locked", 0)
            try:
                cfg = make_cfg(Path(home))
                cfg.folders = [("notes", "Notes", "Documents/notes")]
                unreadable = []
                with mock.patch("devsync.naming.Path.home", return_value=Path(home)):
                    bad = naming.report(cfg, unreadable)
            finally:
                os.chmod(docs / "locked", 0o755)
        self.assertEqual([Path(b).name for b in bad], ["Bad Name"])
        self.assertEqual(len(unreadable), 1)
