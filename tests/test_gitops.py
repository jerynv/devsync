import os
import unittest
from unittest import mock

from devsync import gitops
from tests.helpers import Fixture, commit, g

os.environ["DEVSYNC_CLONE_PROTOCOLS"] = "file"  # fixtures clone from local bare repos


def _no_process(*a, **kw):
    raise AssertionError(f"a git process was started: {a[0] if a else kw}")


class AllowlistTest(unittest.TestCase):
    # Process creation is blocked here, so even a broken allowlist can never run these commands.
    @mock.patch("devsync.gitops.subprocess.Popen", side_effect=_no_process)
    def test_refuses_everything_off_template(self, _popen):
        bad = [
            ["push"], ["push", "--force"], ["reset", "--hard"], ["checkout", "main"], ["clean", "-fdx"],
            ["rebase", "origin/main"], ["merge", "origin/main"], ["merge", "--ff-only"],
            ["branch", "-D", "x"], ["branch", "-f", "x"], ["branch", "-m", "x"], ["branch", "--show-current"],
            ["fetch", "origin", "+refs/heads/*:refs/heads/*"], ["fetch", "--all", "--prune", "--quiet"],
            ["fetch", "--all", "--prune", "--quiet", "--no-auto-gc", "--force"],
            ["clone", "-q", "--", "--upload-pack=touch /tmp/x", "p"], ["clone", "-q", "--", "ext::sh -c x", "p"],
            ["clone", "-q", "url", "p"], ["status"], ["gc"], ["stash"],
        ]
        for argv in bad:
            with self.subTest(argv=argv), self.assertRaises(gitops.GitRefused):
                gitops.check_argv(argv)
            with self.subTest(run=argv), self.assertRaises(gitops.GitRefused):
                gitops.run(argv, cwd=None)

    def test_accepts_templates(self):
        for name, tpl in gitops.TEMPLATES.items():
            argv = [{"<url>": "https://example.invalid/x.git", "<path>": "/tmp/x"}.get(a, a) for a in tpl]
            self.assertEqual(gitops.check_argv(argv), name)


class SyncRepoTest(unittest.TestCase):
    def setUp(self):
        self.fx = Fixture()

    def tearDown(self):
        self.fx.close()

    def sync(self, **kw):
        args = dict(self_repo=None, fetch=True, act=True)
        args.update(kw)
        return gitops.sync_repo(self.fx.entry(), self.fx.root, **args)

    def test_clean_and_behind_fast_forwards(self):
        self.fx.upstream_commit(2)
        st, actions, notes = self.sync()
        self.assertEqual(actions, ["GitHub/app: fast-forwarded 2 commit(s)"])
        self.assertEqual((st.behind, st.ahead, st.dirty), (0, 0, 0))

    def test_dirty_is_not_fast_forwarded(self):
        self.fx.upstream_commit()
        (self.fx.app / "f.txt").write_text("local edit")
        st, actions, notes = self.sync()
        self.assertEqual(actions, [])
        self.assertEqual(st.behind, 1)
        self.assertTrue(any("not pulled" in n for n in notes))
        self.assertEqual((self.fx.app / "f.txt").read_text(), "local edit")

    def test_ahead_is_not_fast_forwarded_or_pushed(self):
        self.fx.upstream_commit()
        commit(self.fx.app, "local.txt")
        head = g(self.fx.app, "rev-parse", "HEAD")
        st, actions, notes = self.sync()
        self.assertEqual(actions, [])
        self.assertEqual((st.ahead, st.behind), (1, 1))
        self.assertEqual(g(self.fx.app, "rev-parse", "HEAD"), head)
        self.assertNotIn(head, g(self.fx.origin, "rev-list", "--all"))

    def test_index_lock_is_busy_and_left_alone(self):
        self.fx.upstream_commit()
        lock = self.fx.app / ".git" / "index.lock"
        lock.write_text("")
        st, actions, notes = self.sync()
        self.assertTrue(st.busy)
        self.assertEqual(actions, [])
        self.assertTrue(lock.exists())

    def test_own_checkout_is_never_fast_forwarded(self):
        self.fx.upstream_commit()
        head = g(self.fx.app, "rev-parse", "HEAD")
        st, actions, notes = self.sync(self_repo=self.fx.app)
        self.assertEqual(actions, [])
        self.assertTrue(st.self_repo)
        self.assertTrue(any("update available" in n for n in notes))
        self.assertEqual(g(self.fx.app, "rev-parse", "HEAD"), head)

    def test_dry_run_changes_nothing(self):
        self.fx.upstream_commit()
        head = g(self.fx.app, "rev-parse", "HEAD")
        st, actions, notes = self.sync(fetch=False, act=False)
        self.assertEqual(g(self.fx.app, "rev-parse", "HEAD"), head)
        self.assertEqual(st.behind, 0)  # nothing fetched
        g(self.fx.app, "fetch", "-q")
        st, actions, notes = self.sync(fetch=False, act=False)
        self.assertEqual(actions, ["GitHub/app: would fast-forward 1 commit(s)"])
        self.assertEqual(g(self.fx.app, "rev-parse", "HEAD"), head)

    def test_missing_repo_is_cloned_only_when_acting(self):
        entry = self.fx.entry("GitHub/new")
        st, actions, _ = gitops.sync_repo(entry, self.fx.root, self_repo=None, fetch=False, act=False)
        self.assertEqual(actions, ["GitHub/new: would clone"])
        self.assertFalse((self.fx.root / "GitHub/new").exists())
        st, actions, _ = gitops.sync_repo(entry, self.fx.root, self_repo=None, fetch=True, act=True)
        self.assertEqual(actions, ["GitHub/new: cloned"])
        self.assertTrue((self.fx.root / "GitHub/new/.git").is_dir())
        self.assertEqual((st.present, st.is_repo, st.branch), (True, True, "main"))

    @unittest.skipIf(os.geteuid() == 0, "root ignores permissions")
    def test_permission_error_never_clones(self):
        locked = self.fx.root / "Locked"
        locked.mkdir()
        os.chmod(locked, 0)
        try:
            entry = self.fx.entry("Locked/app")
            st, actions, notes = gitops.sync_repo(entry, self.fx.root, self_repo=None, fetch=True, act=True)
            self.assertEqual(actions, [])
            self.assertIn("cannot read", st.error)
            self.assertTrue(any("nothing done" in n for n in notes))
        finally:
            os.chmod(locked, 0o755)
        self.assertEqual(list(locked.iterdir()), [])

    def test_failed_status_skips_fast_forward(self):
        self.fx.upstream_commit()
        (self.fx.app / ".git" / "HEAD").write_text("garbage\n")
        st, actions, notes = self.sync()
        self.assertEqual(actions, [])
        self.assertTrue(st.error)


class ParseStatusTest(unittest.TestCase):
    def test_parse(self):
        text = "# branch.oid abc\n# branch.head main\n# branch.upstream origin/main\n# branch.ab +2 -3\n" \
               "1 .M N... 100644 100644 100644 a b f.txt\n? new.txt\n"
        self.assertEqual(gitops.parse_status(text),
                         {"branch": "main", "upstream": "origin/main", "ahead": 2, "behind": 3, "dirty": 2})

    def test_detached(self):
        self.assertEqual(gitops.parse_status("# branch.head (detached)\n")["branch"], "")


if __name__ == "__main__":
    unittest.main()
