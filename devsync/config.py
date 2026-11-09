"""Configuration: config.toml, repos.toml and folders.tsv from the (synced) config folder.

Paths in config are written with ``~`` so one file works on every machine. The machine this
process runs on is never guessed: ``DEVSYNC_MACHINE`` must name one of the configured machines.
"""
from __future__ import annotations

import os
import threading
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_NAME_RULE = r"^[a-z0-9]+([._-][a-z0-9]+)*$"
DEFAULT_SKIP_DIRS = ["node_modules", ".git", "__pycache__", ".venv", ".next", ".stfolder", ".stversions"]
DEFAULT_TOOL_DIRS = ["ios", "android", "macos", "linux", "windows"]
DEFAULT_BUNDLE_EXT = [".xcodeproj", ".xcworkspace", ".xcassets", ".lproj", ".appiconset", ".imageset",
                      ".app", ".bundle"]


class ConfigError(Exception):
    pass


def expand(p: str | os.PathLike) -> Path:
    return Path(os.path.expanduser(str(p)))


def config_dir() -> Path:
    return expand(os.environ.get("DEVSYNC_CONFIG_DIR", "~/.config/devsync"))


def state_dir() -> Path:
    return expand(os.environ.get("DEVSYNC_STATE_DIR", "~/.local/state/devsync"))


@dataclass
class Machine:
    name: str
    tailnet_url: str = ""
    local_port: int = 8765
    tailnet_port: int = 8766


@dataclass
class Config:
    machine: str
    machines: dict[str, Machine]
    tailnet_logins: list[str]
    tailnet_hosts: list[str]
    tailscale_cli: list[str]
    repos_root: Path
    scan_unlisted: list[str]
    repos: list[dict]
    folders: list[tuple[str, str, str]]
    skills_source: Path
    skills_targets: list[Path]
    skills_prune_prefixes: list[Path]
    instructions: Path | None
    instruction_links: list[Path]
    name_rule: str = DEFAULT_NAME_RULE
    name_under: str = "Documents"
    skip_dirs: list[str] = field(default_factory=lambda: list(DEFAULT_SKIP_DIRS))
    tool_dirs: list[str] = field(default_factory=lambda: list(DEFAULT_TOOL_DIRS))
    bundle_ext: list[str] = field(default_factory=lambda: list(DEFAULT_BUNDLE_EXT))
    interval_s: int = 900

    @property
    def me(self) -> Machine:
        return self.machines[self.machine]

    def my_repos(self) -> list[dict]:
        return [r for r in self.repos if self.machine in r.get("machines", [])]

    def peers(self) -> list[Machine]:
        return [m for n, m in self.machines.items() if n != self.machine]


def _read_folders(path: Path) -> list[tuple[str, str, str]]:
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) == 3:
            rows.append((parts[0], parts[1], parts[2]))
    return rows


def load(cdir: Path | None = None, machine: str | None = None) -> Config:
    cdir = cdir or config_dir()
    machine = machine or os.environ.get("DEVSYNC_MACHINE", "")
    if not machine:
        raise ConfigError("DEVSYNC_MACHINE is not set; it must name a machine in config.toml")
    cfg_path = cdir / "config.toml"
    if not cfg_path.exists():
        raise ConfigError(f"{cfg_path} not found (see examples/config.example.toml)")
    raw = tomllib.loads(cfg_path.read_text())

    machines = {}
    for name, m in raw.get("machines", {}).items():
        machines[name] = Machine(name, m.get("tailnet_url", "").rstrip("/"),
                                 int(m.get("local_port", 8765)), int(m.get("tailnet_port", 8766)))
    if machine not in machines:
        raise ConfigError(f"DEVSYNC_MACHINE={machine!r} is not one of {sorted(machines)} in config.toml")

    access = raw.get("access", {})
    repos_cfg = raw.get("repos", {})
    skills = raw.get("skills", {})
    naming = raw.get("naming", {})
    repos_path = cdir / "repos.toml"
    repos = tomllib.loads(repos_path.read_text()).get("repo", []) if repos_path.exists() else []
    instr = skills.get("instructions")
    return Config(
        machine=machine,
        machines=machines,
        tailnet_logins=[x.lower() for x in access.get("tailnet_logins", [])],
        tailnet_hosts=[x.lower() for x in access.get("tailnet_hosts", [])],
        tailscale_cli=list(access.get("tailscale_cli", [])),
        repos_root=expand(repos_cfg.get("root", "~/Documents")),
        scan_unlisted=list(repos_cfg.get("scan_unlisted", [])),
        repos=repos,
        folders=_read_folders(cdir / "folders.tsv"),
        skills_source=expand(skills.get("source", "~/.agents/skills")),
        skills_targets=[expand(t) for t in skills.get("targets", [])],
        skills_prune_prefixes=[expand(t) for t in skills.get("prune_link_prefixes", [])],
        instructions=expand(instr) if instr else None,
        instruction_links=[expand(t) for t in skills.get("instruction_links", [])],
        name_rule=naming.get("rule", DEFAULT_NAME_RULE),
        name_under=naming.get("under", "Documents"),
        skip_dirs=list(naming.get("skip_dirs", DEFAULT_SKIP_DIRS)),
        tool_dirs=list(naming.get("tool_dirs", DEFAULT_TOOL_DIRS)),
        bundle_ext=list(naming.get("bundle_ext", DEFAULT_BUNDLE_EXT)),
        interval_s=int(raw.get("cycle", {}).get("interval_minutes", 15)) * 60,
    )


class LiveConfig:
    """Reloads the config when any of its files changes on disk (they are synced between machines)."""

    FILES = ("config.toml", "repos.toml", "folders.tsv")

    def __init__(self, cdir: Path | None = None, machine: str | None = None):
        self.cdir = cdir or config_dir()
        self.machine = machine
        self._lock = threading.Lock()
        self._stamp = None
        self._cfg = None
        self.error: str | None = None
        self.get()
        if self._cfg is None:
            raise ConfigError(self.error or "config failed to load")

    def _mtimes(self):
        out = []
        for f in self.FILES:
            try:
                out.append((self.cdir / f).stat().st_mtime_ns)
            except OSError:
                out.append(None)
        return tuple(out)

    def get(self) -> Config:
        with self._lock:
            stamp = self._mtimes()
            if stamp != self._stamp:
                try:
                    self._cfg = load(self.cdir, self.machine)
                    self.error = None
                except (ConfigError, tomllib.TOMLDecodeError, OSError) as e:
                    # Keep the last good config; a half-synced file must not take the server down.
                    self.error = f"config reload failed: {e}"
                self._stamp = stamp
            return self._cfg
