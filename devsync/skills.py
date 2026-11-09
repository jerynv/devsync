"""Agent skill links: one shared skills folder, linked into each agent's config.

check() only reads. apply() creates or retargets symlinks and removes symlinks that no longer
resolve and point into the shared folder. It never removes a real file or folder, with one
exception kept from the original script: an instructions file whose contents are identical to the
shared one is replaced by a link to it.
"""
from __future__ import annotations

import filecmp
import os
from pathlib import Path

from .config import Config


def _targets(cfg: Config, create: bool) -> list[Path]:
    seen, out = set(), []
    for t in cfg.skills_targets:
        if not t.parent.is_dir():
            continue
        if create:
            t.mkdir(exist_ok=True)
        if not t.is_dir():
            continue
        real = t.resolve()
        if real not in seen:
            seen.add(real)
            out.append(real)
    return out


def _skills(src: Path) -> list[str]:
    try:
        return sorted(p.name for p in src.iterdir() if p.is_dir())
    except OSError:
        return []


def _symlink(target: str, link: Path):
    """ln -sfn: point ``link`` at ``target``, replacing an existing symlink atomically."""
    tmp = link.with_name(f".{link.name}.devsync-tmp")
    if tmp.is_symlink():
        tmp.unlink()
    os.symlink(target, tmp)
    os.replace(tmp, link)


def _prunable(link: Path, cfg: Config) -> bool:
    if not link.is_symlink() or link.exists():
        return False
    dest = os.readlink(link)
    prefixes = [str(cfg.skills_source)] + [str(p) for p in cfg.skills_prune_prefixes]
    return any(dest.startswith(p + "/") for p in prefixes)


def check(cfg: Config) -> dict:
    src = cfg.skills_source
    out = {"source": str(src), "source_exists": src.is_dir(), "skills": _skills(src),
           "targets": [], "instructions": []}
    if not out["source_exists"]:
        return out
    for t in _targets(cfg, create=False):
        rows = []
        for name in out["skills"]:
            link, want = t / name, str(src / name)
            if link.is_symlink():
                status = "ok" if os.readlink(link) == want else "wrong target"
            elif link.exists():
                status = "blocked by a real folder"
            else:
                status = "missing"
            rows.append({"name": name, "status": status})
        stale = []
        try:
            stale = sorted(p.name for p in t.iterdir() if _prunable(p, cfg))
        except OSError:
            pass
        out["targets"].append({"path": str(t), "links": rows, "stale": stale,
                               "ok": sum(r["status"] == "ok" for r in rows)})
    out["instructions"] = _check_instructions(cfg)
    return out


def _check_instructions(cfg: Config) -> list[dict]:
    rows = []
    if not cfg.instructions or not cfg.instructions.is_file():
        return rows
    for f in cfg.instruction_links:
        if not f.parent.is_dir():
            continue
        if f.is_symlink():
            status = "ok" if os.readlink(f) == str(cfg.instructions) else "wrong target"
        elif not f.exists():
            status = "missing"
        elif filecmp.cmp(f, cfg.instructions, shallow=False):
            status = "identical copy (will be linked)"
        else:
            status = "differs (left alone)"
        rows.append({"path": str(f), "status": status})
    return rows


def apply(cfg: Config) -> tuple[list[str], list[str]]:
    """Make the links match. Returns (actions, notes)."""
    actions, notes = [], []
    src = cfg.skills_source
    if not src.is_dir():
        return actions, notes
    for t in _targets(cfg, create=True):
        for name in _skills(src):
            link, want = t / name, str(src / name)
            if link.is_symlink():
                if os.readlink(link) != want:
                    _symlink(want, link)
                    actions.append(f"relinked {link}")
            elif link.exists():
                notes.append(f"skip {link}: a real folder is in the way")
            else:
                os.symlink(want, link)
                actions.append(f"linked {link}")
        for link in sorted(t.iterdir()):
            if _prunable(link, cfg):
                link.unlink()  # a dangling symlink only; _prunable never matches real files
                actions.append(f"removed dangling link {link}")
    if cfg.instructions and cfg.instructions.is_file():
        want = str(cfg.instructions)
        for f in cfg.instruction_links:
            if not f.parent.is_dir():
                continue
            if f.is_symlink() or not f.exists():
                if not (f.is_symlink() and os.readlink(f) == want):
                    _symlink(want, f)
                    actions.append(f"linked {f}")
            elif filecmp.cmp(f, cfg.instructions, shallow=False):
                _symlink(want, f)
                actions.append(f"linked {f} (was an identical copy)")
            else:
                notes.append(f"skip {f}: differs from {cfg.instructions}")
    return actions, notes
