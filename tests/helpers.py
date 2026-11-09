import os
import subprocess
import tempfile
from pathlib import Path

GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@example.invalid", "GIT_CONFIG_GLOBAL": os.devnull,
           "GIT_CONFIG_NOSYSTEM": "1"}


_FIXTURE_ROOTS: set[Path] = set()


def g(cwd, *args):
    """Raw git for building fixtures (tests only; devsync itself goes through gitops.run).
    Refuses to run anywhere except inside a live Fixture's temporary directory."""
    here = Path(cwd).resolve()
    if not any(here == r or r in here.parents for r in _FIXTURE_ROOTS):
        raise AssertionError(f"fixture git outside a fixture directory: {cwd}")
    r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True,
                       env={**os.environ, **GIT_ENV})
    if r.returncode:
        raise RuntimeError(r.stderr)
    return r.stdout.strip()


def commit(repo, name="f.txt", text="x"):
    (Path(repo) / name).write_text(text)
    g(repo, "add", name)
    g(repo, "commit", "-qm", f"edit {name}")


class Fixture:
    """A bare origin, a 'root' (like ~/Documents) with a clone at GitHub/app, and a second clone
    ('upstream') used to push new commits to the origin."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name).resolve()
        _FIXTURE_ROOTS.add(base)
        self.base = base
        self.origin = base / "origin.git"
        self.root = base / "root"
        self.up = base / "upstream"
        g(base, "init", "-q", "--bare", "-b", "main", str(self.origin))
        g(base, "clone", "-q", str(self.origin), str(self.up))
        g(self.up, "checkout", "-q", "-b", "main")
        commit(self.up, text="one")
        g(self.up, "push", "-q", "origin", "main")
        self.root.mkdir()
        (self.root / "GitHub").mkdir()
        self.app = self.root / "GitHub" / "app"
        g(base, "clone", "-q", str(self.origin), str(self.app))
        self.url = f"file://{self.origin}"

    def upstream_commit(self, n=1):
        for i in range(n):
            commit(self.up, text=f"up{i}-{os.urandom(4).hex()}")
        g(self.up, "push", "-q", "origin", "main")

    def entry(self, path="GitHub/app"):
        return {"path": path, "url": self.url, "machines": ["a"]}

    def close(self):
        _FIXTURE_ROOTS.discard(self.base)
        self.tmp.cleanup()
