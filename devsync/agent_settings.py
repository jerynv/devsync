"""Shared agent settings: a few chosen keys, merged into each machine's agent settings files.

Only the keys listed under ``[agent_settings.values]`` are written. Nested tables merge key by
key, so ``env = { X = "1" }`` sets X and leaves every other variable in ``env`` alone. Nothing is
ever removed. A file that isn't valid JSON is left untouched and reported.

Login and credential settings are never managed: the config is refused if a value's key path
looks like auth, and targets must be ``settings.json`` or ``settings.local.json``, so this can't
be pointed at a file that holds an account or token.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .config import Config

TARGET_NAMES = ("settings.json", "settings.local.json")

_AUTH_WORDS = re.compile(r"auth|token|secret|passw|credential|login|apikey|api_key|oauth|cookie", re.I)
_AUTH_KEYS = {"apiKeyHelper", "awsAuthRefresh", "awsCredentialExport", "gcpAuthRefresh",
              "forceLoginMethod", "forceLoginOrgUUID", "otelHeadersHelper", "primaryApiKey"}
_AUTH_ENV = re.compile(r"^(ANTHROPIC_|AWS_|GOOGLE_|GCLOUD_|CLOUD_ML_|VERTEX_|AZURE_|"
                       r"CLAUDE_CODE_USE_(BEDROCK|VERTEX|FOUNDRY)|CLAUDE_CODE_OAUTH)", re.I)


def auth_paths(values: dict, prefix: tuple[str, ...] = ()) -> list[str]:
    """Key paths in ``values`` that touch login or credentials. Empty means safe to manage."""
    bad = []
    for k, v in values.items():
        path = prefix + (k,)
        in_env = len(path) == 2 and path[0] == "env"
        if k in _AUTH_KEYS or _AUTH_WORDS.search(k) or (in_env and _AUTH_ENV.match(k)):
            bad.append(".".join(path))
        elif isinstance(v, dict):
            bad.extend(auth_paths(v, path))
    return bad


def _merge(current: dict, want: dict) -> tuple[dict, list[str]]:
    """Deep-merge ``want`` into a copy of ``current``. Returns (merged, changed key paths)."""
    out, changed = dict(current), []
    for k, v in want.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            sub, sub_changed = _merge(out[k], v)
            out[k] = sub
            changed += [f"{k}.{c}" for c in sub_changed]
        elif k not in out or type(out[k]) is not type(v) or out[k] != v:  # false != 0 here
            out[k] = v
            changed.append(k)
    return out, changed


def _read(path: Path) -> tuple[dict | None, str]:
    """(object, problem). A missing file reads as an empty object."""
    try:
        text = path.read_text()
    except FileNotFoundError:
        return {}, ""
    except OSError as e:
        return None, f"unreadable ({e.strerror})"
    if not text.strip():
        return {}, ""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return None, f"not valid JSON (line {e.lineno})"
    if not isinstance(data, dict):
        return None, "not a JSON object"
    return data, ""


def _write(path: Path, data: dict):
    tmp = path.with_name(f".{path.name}.devsync-tmp")
    try:
        mode = path.stat().st_mode & 0o777
    except FileNotFoundError:
        mode = 0o600
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def _plan(cfg: Config):
    """Yield (path, current, merged, changed, problem) for each target whose folder exists."""
    for path in cfg.agent_settings_targets:
        if not path.parent.is_dir():
            continue
        if path.name not in TARGET_NAMES:
            yield path, None, None, [], f"skipped: only {' or '.join(TARGET_NAMES)} can be managed"
            continue
        if path.is_symlink():
            yield path, None, None, [], "skipped: is a symlink"
            continue
        current, problem = _read(path)
        if current is None:
            yield path, None, None, [], problem
            continue
        merged, changed = _merge(current, cfg.agent_settings_values)
        yield path, current, merged, changed, ""


def check(cfg: Config) -> list[dict]:
    rows = []
    if not cfg.agent_settings_values:
        return rows
    for path, _cur, _m, changed, problem in _plan(cfg):
        status = problem or ("ok" if not changed else "differs")
        rows.append({"path": str(path), "status": status, "keys": changed})
    return rows


def apply(cfg: Config) -> tuple[list[str], list[str]]:
    """Merge the managed keys into each target. Returns (actions, notes)."""
    actions, notes = [], []
    if not cfg.agent_settings_values:
        return actions, notes
    bad = auth_paths(cfg.agent_settings_values)
    if bad:  # load() refuses these already; this guards a hand-built Config
        return actions, [f"agent settings not applied: auth keys are never managed ({', '.join(bad)})"]
    for path, _cur, merged, changed, problem in _plan(cfg):
        if problem:
            notes.append(f"skip {path}: {problem}")
        elif changed:
            _write(path, merged)
            actions.append(f"set {', '.join(changed)} in {path}")
    return actions, notes
