"""Report-only check that synced folder names follow the naming rule (lowercase-dash by default)."""
from __future__ import annotations

import os
import re
from pathlib import Path

from .config import Config


def report(cfg: Config, unreadable: list[str] | None = None) -> list[str]:
    rule = re.compile(cfg.name_rule)
    skip, tools, bundles = set(cfg.skip_dirs), set(cfg.tool_dirs), tuple(cfg.bundle_ext)
    home = Path.home()
    prefix = cfg.name_under.rstrip("/") + "/"
    bad = []
    for _, _, rel in cfg.folders:
        if not rel.startswith(prefix):
            continue
        def onerror(e: OSError):
            if unreadable is not None:
                unreadable.append(f"{e.filename}: {e.strerror or e}")

        for root, dirs, _ in os.walk(home / rel, onerror=onerror):
            dirs[:] = [d for d in dirs if d not in skip and d not in tools
                       and not d.startswith((".", "_")) and not d.endswith(bundles)]
            bad += [os.path.join(root, d) for d in dirs if not rule.match(d)]
        if not rule.match(Path(rel).name):
            bad.append(str(home / rel))
    return bad
