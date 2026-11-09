"""Git, restricted to a fixed set of exact commands.

Every git call goes through ``run()``, which refuses any argv that is not one of the templates
below. devsync can clone, fetch, read status and fast-forward. It cannot push, merge, rebase,
reset, check out, clean, delete branches or force anything.
"""
from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

# Exact argument lists (after "git"). "<url>" and "<path>" are the only substitutions allowed.
TEMPLATES = {
    "status": ["--no-optional-locks", "status", "--porcelain=v2", "--branch"],
    "fetch": ["fetch", "--all", "--prune", "--quiet", "--no-auto-gc"],
    "ff": ["merge", "--ff-only", "--quiet", "@{u}"],
    "clone": ["clone", "-q", "--", "<url>", "<path>"],
}
CLONE_PROTOCOLS_DEFAULT = "https:ssh"
TIMEOUTS = {"status": 60, "fetch": 300, "ff": 120, "clone": 1800}


class GitRefused(Exception):
    pass


def check_argv(argv: list[str]) -> str:
    """Return the template name that argv matches exactly, or raise GitRefused."""
    for name, tpl in TEMPLATES.items():
        if len(argv) != len(tpl):
            continue
        ok = True
        for a, t in zip(argv, tpl):
            if t == "<url>":
                ok = bool(a) and not a.startswith("-") and "::" not in a
            elif t == "<path>":
                ok = bool(a) and not a.startswith("-")
            else:
                ok = a == t
            if not ok:
                break
        if ok:
            return name
    raise GitRefused(f"git {' '.join(argv)!r} is not an allowed command")


@dataclass
class Result:
    code: int
    out: str
    err: str


def _env(op: str) -> dict:
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes")
    if op == "clone":
        env["GIT_ALLOW_PROTOCOL"] = os.environ.get("DEVSYNC_CLONE_PROTOCOLS", CLONE_PROTOCOLS_DEFAULT)
    return env


def run(argv: list[str], cwd: Path | None = None) -> Result:
    op = check_argv(argv)
    cmd = ["git"] + (["-C", str(cwd)] if cwd else []) + argv
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                         env=_env(op), start_new_session=True, stdin=subprocess.DEVNULL)
    try:
        out, err = p.communicate(timeout=TIMEOUTS[op])
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        p.communicate()
        return Result(124, "", f"timed out after {TIMEOUTS[op]}s")
    return Result(p.returncode, out.strip(), err.strip())


# --- repo state -----------------------------------------------------------------------------

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def repo_lock(path: Path) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(str(path), threading.Lock())


@dataclass
class RepoState:
    path: str                      # as written in repos.toml
    url: str = ""
    present: bool = False
    is_repo: bool = False
    branch: str = ""
    upstream: str = ""
    ahead: int = 0
    behind: int = 0
    dirty: int = 0
    busy: bool = False
    self_repo: bool = False
    error: str = ""
    fetch_error: str = ""
    last_fetch: float = 0.0
    checked: float = 0.0
    notes: list[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


def git_dir(path: Path) -> Path | None:
    dot = path / ".git"
    if dot.is_dir():
        return dot
    if dot.is_file():
        line = dot.read_text().strip()
        if line.startswith("gitdir:"):
            g = Path(line[7:].strip())
            return g if g.is_absolute() else (path / g).resolve()
    return None


def parse_status(text: str) -> dict:
    out = {"branch": "", "upstream": "", "ahead": 0, "behind": 0, "dirty": 0}
    for line in text.splitlines():
        if line.startswith("# branch.head "):
            head = line[len("# branch.head "):]
            out["branch"] = "" if head == "(detached)" else head
        elif line.startswith("# branch.upstream "):
            out["upstream"] = line[len("# branch.upstream "):]
        elif line.startswith("# branch.ab "):
            a, b = line[len("# branch.ab "):].split()
            out["ahead"], out["behind"] = int(a), -int(b)
        elif line and not line.startswith("#"):
            out["dirty"] += 1
    return out


def inspect(state: RepoState, abs_path: Path) -> bool:
    """Fill status fields. Returns False (and records why) when the repo can't be read."""
    gd = git_dir(abs_path)
    state.busy = bool(gd and (gd / "index.lock").exists())
    r = run(TEMPLATES["status"], abs_path)
    state.checked = time.time()
    if r.code:
        state.error = f"status failed: {r.err[:160]}"
        return False
    for k, v in parse_status(r.out).items():
        setattr(state, k, v)
    state.error = ""
    return True


def locate(state: RepoState, abs_path: Path) -> bool:
    """Decide present / not present. Only a definite FileNotFoundError counts as missing."""
    try:
        os.stat(abs_path)
    except FileNotFoundError:
        state.present = False
        return True
    except OSError as e:  # PermissionError (macOS privacy controls), I/O errors...
        state.present = False
        state.error = f"cannot read: {e.__class__.__name__}: {e.strerror or e}"
        return False
    state.present = True
    try:
        state.is_repo = git_dir(abs_path) is not None
    except OSError as e:
        state.error = f"cannot read: {e.__class__.__name__}: {e.strerror or e}"
        return False
    return True


def sync_repo(entry: dict, root: Path, *, self_repo: Path | None, fetch: bool, act: bool,
              prev: RepoState | None = None) -> tuple[RepoState, list[str], list[str]]:
    """One repo's part of the cycle. Returns (state, actions, notes).

    fetch: run ``git fetch`` (network). act: clone and fast-forward; with act=False the would-be
    actions are reported as "would ..." and nothing is changed.
    """
    rel, url = entry["path"], entry.get("url", "")
    abs_path = root / rel
    st = RepoState(path=rel, url=url)
    if prev:
        st.last_fetch, st.fetch_error = prev.last_fetch, prev.fetch_error
    actions, notes = [], []
    st.notes = notes

    if not locate(st, abs_path):
        notes.append(f"{rel}: {st.error} (nothing done)")
        return st, actions, notes
    if not st.present:
        if not url:
            notes.append(f"{rel}: missing here and has no remote to clone from")
        elif not act:
            actions.append(f"{rel}: would clone")
        else:
            with repo_lock(abs_path):
                abs_path.parent.mkdir(parents=True, exist_ok=True)
                r = run(["clone", "-q", "--", url, str(abs_path)])
            if r.code:
                notes.append(f"{rel}: clone failed: {r.err[:160]}")
            else:
                actions.append(f"{rel}: cloned")
                st.present, st.is_repo, st.last_fetch = True, True, time.time()
                inspect(st, abs_path)
        return st, actions, notes
    if not st.is_repo:
        notes.append(f"{rel}: folder exists but is not a git repo")
        return st, actions, notes

    st.self_repo = bool(self_repo) and abs_path.resolve() == self_repo.resolve()
    with repo_lock(abs_path):
        gd = git_dir(abs_path)
        if gd and (gd / "index.lock").exists():
            st.busy = True
            notes.append(f"{rel}: busy (git index.lock present); skipped")
            return st, actions, notes
        if url and fetch:
            r = run(TEMPLATES["fetch"], abs_path)
            st.last_fetch = time.time()
            st.fetch_error = "" if r.code == 0 else r.err[:160]
            if r.code:
                notes.append(f"{rel}: fetch failed: {st.fetch_error}")
        if not inspect(st, abs_path):
            notes.append(f"{rel}: {st.error} (nothing done)")
            return st, actions, notes
        if st.branch and url and not st.upstream:
            notes.append(f"{rel}: branch '{st.branch}' has no upstream")
        clean = not st.dirty and not st.ahead and not st.busy
        if st.behind and clean and st.upstream:
            if st.self_repo:
                notes.append(f"{rel}: devsync update available ({st.behind} commit(s)); "
                             "pull and restart by hand")
            elif not act:
                actions.append(f"{rel}: would fast-forward {st.behind} commit(s)")
            else:
                r = run(TEMPLATES["ff"], abs_path)
                if r.code == 0:
                    actions.append(f"{rel}: fast-forwarded {st.behind} commit(s)")
                    inspect(st, abs_path)
                else:
                    actions.append(f"{rel}: fast-forward failed: {r.err[:120]}")
        elif st.behind:
            notes.append(f"{rel}: {st.behind} new commit(s) on the remote not pulled (local work in the way)")
    if st.ahead:
        notes.append(f"{rel}: {st.ahead} unpushed commit(s) on '{st.branch}'")
    if st.dirty:
        notes.append(f"{rel}: {st.dirty} uncommitted change(s) on '{st.branch or 'detached'}'")
    return st, actions, notes


def unlisted(root: Path, scan: list[str], listed: set[str]) -> list[str]:
    found = []
    for base_rel in scan:
        base = root / base_rel
        try:
            entries = sorted(base.iterdir())
        except OSError:
            continue
        for d in entries:
            rel = str(d.relative_to(root))
            try:
                if (d / ".git").is_dir() and rel not in listed:
                    found.append(rel)
            except OSError:
                continue
    return found
