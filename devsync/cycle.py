"""The sync cycle (what the old 15-minute timer did) and the cached snapshot the web UI reads."""
from __future__ import annotations

import fcntl
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import __version__, gitops, naming, skills, syncthing
from .config import Config, LiveConfig, config_dir, state_dir

SELF_REPO = Path(__file__).resolve().parent.parent
MAX_PARALLEL = 4
HISTORY = 50          # cycles kept in memory (and shown to peers)
HISTORY_ACTIONS = 40  # actions kept per cycle


class CycleBusy(Exception):
    pass


class _Flock:
    """Cross-process lock so a CLI run and the server never run a cycle at the same time."""

    def __init__(self, path: Path):
        self.path = path

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(self.fd)
            raise CycleBusy("another devsync cycle is running")
        return self

    def __exit__(self, *exc):
        fcntl.flock(self.fd, fcntl.LOCK_UN)
        os.close(self.fd)


def documents_ok(cfg: Config) -> str:
    """Probe the repos root. Returns an error string, or "" when it is readable."""
    try:
        os.listdir(cfg.repos_root)
        return ""
    except OSError as e:
        return f"cannot read {cfg.repos_root}: {e.strerror or e}"


def _repos(cfg: Config, *, fetch: bool, act: bool, prev: dict) -> tuple[list, list, list]:
    entries = cfg.my_repos()

    def one(e):
        try:
            return gitops.sync_repo(e, cfg.repos_root, self_repo=SELF_REPO, fetch=fetch, act=act,
                                    prev=prev.get(e["path"]))
        except Exception as ex:  # one bad repo must not stop the others
            st = gitops.RepoState(path=e["path"], url=e.get("url", ""), error=f"{ex.__class__.__name__}: {ex}")
            return st, [], [f"{e['path']}: {st.error}"]

    with ThreadPoolExecutor(MAX_PARALLEL) as ex:
        results = list(ex.map(one, entries))
    states = [r[0] for r in results]
    actions = [a for r in results for a in r[1]]
    notes = [n for r in results for n in r[2]]
    return states, actions, notes


def run_cycle(cfg: Config, *, dry_run: bool = False, prev: dict | None = None) -> dict:
    """A full cycle. dry_run: no fetch, clone, fast-forward, linking or file writes of any kind."""
    if dry_run:  # read-only: no lock file either, so a dry run writes nothing at all
        return _cycle(cfg, dry_run=True, prev=prev or {})
    with _Flock(state_dir() / "cycle.lock"):
        return _cycle(cfg, dry_run=False, prev=prev or {})


def _cycle(cfg: Config, *, dry_run: bool, prev: dict) -> dict:
    started = time.time()
    banner = documents_ok(cfg)
    if banner:
        states, actions, notes, extra = [], [], [f"{banner}; repo work skipped"], []
    else:
        states, actions, notes = _repos(cfg, fetch=not dry_run, act=not dry_run, prev=prev)
        extra = gitops.unlisted(cfg.repos_root, cfg.scan_unlisted, {e["path"] for e in cfg.repos})
    health = syncthing.health(cfg.skip_dirs, walk=True)
    unreadable: list[str] = []
    names = naming.report(cfg, unreadable)
    if unreadable:
        notes.append(f"naming check could not read {len(unreadable)} folder(s), e.g. {unreadable[0]}")
    if dry_run:
        skill_actions, skill_notes = [], []
    else:
        skill_actions, skill_notes = skills.apply(cfg)
    snap = snapshot(cfg, states, health, banner=banner)
    snap["cycle"] = {"started": started, "finished": time.time(), "dry_run": dry_run,
                     "actions": actions, "skill_actions": skill_actions,
                     "attention": health["notes"] + notes, "skill_notes": skill_notes}
    snap["unlisted"] = extra
    snap["naming"] = names
    snap["naming_notes"] = notes[-1:] if unreadable else []
    if not dry_run:
        write_report(cfg, snap)
    return snap


def snapshot(cfg: Config, states: list, health: dict, banner: str = "") -> dict:
    return {
        "machine": cfg.machine,
        "version": __version__,
        "generated": time.time(),
        "banner": banner,
        "repos": {s.path: s.to_dict() for s in states},
        "syncthing": health,
        "skills": skills.check(cfg),
        "config_conflicts": syncthing.config_conflicts(config_dir()),
    }


def report_lines(cfg: Config, snap: dict) -> tuple[list[str], list[str]]:
    c = snap["cycle"]
    stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(c["finished"]))
    names = snap["naming"]
    attention = c["attention"] + [f"config conflict copy: {p}" for p in snap["config_conflicts"]]
    full = [f"devsync report ({cfg.machine}, {stamp}, devsync {snap['version']}"
            f"{', dry run' if c['dry_run'] else ''})", ""]
    done = c["actions"] + c["skill_actions"]
    full += ["Done this run:"] + [f"  {a}" for a in done or ["nothing"]] + [""]
    full += ["Needs attention:"] + [f"  {n}" for n in attention or ["nothing"]] + [""]
    full += ["Repos not in repos.toml:"] + [f"  {x}" for x in snap["unlisted"] or ["none"]] + [""]
    full += [f"Folder names that break the naming rule ({len(names)}):"] + [f"  {n}" for n in names]
    if c["skill_notes"]:
        full += ["", "Skill links:"] + [f"  {n}" for n in c["skill_notes"]]
    summary = [f"devsync ({stamp}): {len(cfg.my_repos())} repos checked, {len(c['actions'])} updated, "
               f"{len(attention)} need attention, {len(names)} folder names off-style"]
    summary += [f"  ! {n}" for n in attention[:8]]
    if len(attention) > 8:
        summary.append(f"  … {len(attention) - 8} more in {state_dir() / 'report.txt'}")
    return full, summary


def write_report(cfg: Config, snap: dict):
    full, summary = report_lines(cfg, snap)
    d = state_dir()
    d.mkdir(parents=True, exist_ok=True)
    for name, lines in (("report.txt", full), ("summary.txt", summary)):
        tmp = d / f".{name}.tmp"
        tmp.write_text("\n".join(lines) + "\n")
        os.replace(tmp, d / name)


class Runner:
    """Owns the cached snapshot. Runs the cycle on a wall-clock schedule and on request, and
    refreshes cheap local status only while someone is looking at the page."""

    STATUS_TTL = 60

    def __init__(self, live: LiveConfig):
        self.live = live
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.requested = False
        self.running = False
        self.last_error = ""
        self.snap: dict = {}
        self.last_cycle: dict = {}
        self.history: list[dict] = []  # newest first, bounded by HISTORY
        self.next_due = time.time() + 5  # first cycle shortly after start
        self._refreshing = False
        self.enabled = True  # False for `serve --no-cycle`

    # --- reading -------------------------------------------------------------------------
    def state(self) -> dict:
        with self.lock:
            snap = dict(self.snap)
            snap["cycle"] = dict(self.last_cycle)
            snap["cycle"].update({"running": self.running, "enabled": self.enabled,
                                  "next_due": self.next_due if self.enabled else None,
                                  "error": self.last_error, "queued": self.requested})
            snap["config_error"] = self.live.error or ""
            snap["history"] = list(self.history)
            return snap

    def _remember(self, entry: dict):
        with self.lock:
            self.history.insert(0, entry)
            del self.history[HISTORY:]

    # --- triggers ------------------------------------------------------------------------
    def request_sync(self) -> str:
        with self.lock:
            if not self.enabled:
                return "disabled"
            if self.running:
                return "running"
            self.requested = True
        self.wake.set()
        return "queued"

    def maybe_refresh_status(self):
        """Called on UI polls. Re-reads git status (no network) when the snapshot is stale."""
        with self.lock:
            fresh = time.time() - self.snap.get("generated", 0) < self.STATUS_TTL
            if fresh or self.running or self._refreshing:
                return
            self._refreshing = True
        threading.Thread(target=self._refresh, daemon=True).start()

    def _refresh(self):
        try:
            cfg = self.live.get()
            banner = documents_ok(cfg)
            prev = {p: gitops.RepoState(**d) for p, d in self.snap.get("repos", {}).items()}
            states = [] if banner else _repos(cfg, fetch=False, act=False, prev=prev)[0]
            old_health = self.snap.get("syncthing") or {}
            health = syncthing.health(cfg.skip_dirs, walk=False)
            # Conflict lists come from the last full walk; keep them.
            walked = {f["id"]: f for f in old_health.get("folders", [])}
            for f in health["folders"]:
                if f["id"] in walked:
                    f["conflicts"] = walked[f["id"]]["conflicts"]
                    f["skipped"] = walked[f["id"]].get("skipped", [])
            health["notes"] += syncthing.walk_notes(health["folders"])
            snap = snapshot(cfg, states, health, banner=banner)
            for k in ("unlisted", "naming", "naming_notes"):  # only the full cycle recomputes these
                if k in self.snap:
                    snap[k] = self.snap[k]
            with self.lock:
                if not self.running:
                    self.snap = snap
        except Exception as e:
            self.last_error = f"status refresh failed: {e.__class__.__name__}: {e}"
        finally:
            self._refreshing = False

    # --- loop ----------------------------------------------------------------------------
    def loop(self, stop: threading.Event):
        while not stop.is_set():
            # Check the wall clock at least every minute (catches up right after the machine sleeps).
            self.wake.wait(max(1.0, min(60.0, self.next_due - time.time())))
            self.wake.clear()
            if stop.is_set():
                return
            if self.requested or time.time() >= self.next_due:
                self.run_once()

    def run_once(self):
        with self.lock:
            self.running, self.requested = True, False
        started = time.time()
        try:
            cfg = self.live.get()
            prev = {p: gitops.RepoState(**d) for p, d in self.snap.get("repos", {}).items()}
            snap = run_cycle(cfg, prev=prev)
            with self.lock:
                self.last_cycle = snap.pop("cycle")
                self.snap = snap
                self.last_error = ""
            c = self.last_cycle
            done = c.get("actions", []) + c.get("skill_actions", [])
            self._remember({"started": c.get("started", started), "finished": c.get("finished"),
                            "actions": done[:HISTORY_ACTIONS], "action_count": len(done),
                            "attention_count": len(c.get("attention", [])), "error": ""})
        except CycleBusy as e:
            self.last_error = str(e)
        except Exception as e:
            self.last_error = f"cycle failed: {e.__class__.__name__}: {e}"
            self._remember({"started": started, "finished": time.time(), "actions": [], "action_count": 0,
                            "attention_count": 0, "error": self.last_error})
        finally:
            with self.lock:
                self.running = False
                self.next_due = time.time() + self.live.get().interval_s
