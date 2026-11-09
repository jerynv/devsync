"""The dashboard model: every machine's snapshot folded into one JSON document for the page.

All judgement about what counts as healthy lives here, in Python, so it is tested in one place.
The page only lays this out. Paths are shortened to ``~`` and every value is plain data; the
browser renders it as text, never as HTML.
"""
from __future__ import annotations

import re
import time

from .config import Config

TONES = ("ok", "info", "warn", "bad")  # worst last
_HOME = re.compile(r"^(/home|/Users)/[^/]+(?=/|$)")


def tilde(path: str) -> str:
    return _HOME.sub("~", path or "")


def short_url(url: str) -> str:
    u = re.sub(r"^(https?://|ssh://)?(git@)?", "", url or "")
    return re.sub(r"\.git$", "", u.replace(":", "/", 1) if "://" not in (url or "") and ":" in u else u)


def worst(tones) -> str:
    tones = [t for t in tones if t in TONES]
    return max(tones, key=TONES.index) if tones else "ok"


def issue(text: str, tone: str, tag: str) -> dict:
    return {"text": text, "tone": tone, "tag": tag}


# --- repos ---------------------------------------------------------------------------------
def repo_issues(st: dict) -> list[dict]:
    out = []
    if st.get("busy"):
        out.append(issue("busy", "warn", "busy"))
    if st.get("behind"):
        out.append(issue(f"{st['behind']} behind", "warn", "behind"))
    if st.get("ahead"):
        out.append(issue(f"{st['ahead']} unpushed", "warn", "unpushed"))
    if st.get("dirty"):
        out.append(issue(f"{st['dirty']} uncommitted", "warn", "uncommitted"))
    if st.get("self_repo") and st.get("behind"):
        out.append(issue("update available", "info", "update"))
    if st.get("fetch_error"):
        out.append(issue("fetch failed", "bad", "fetch-failed"))
    return out


def repo_cell(st: dict | None, kept: bool) -> dict:
    """One repo on one machine. ``status`` is ok/info/warn/bad, or none (no data) / absent (not kept)."""
    if not kept:
        return {"status": "absent", "label": "not kept here", "issues": []}
    if st is None:
        return {"status": "none", "label": "no data", "issues": []}
    base = {"branch": st.get("branch") or "", "upstream": st.get("upstream") or "",
            "last_fetch": st.get("last_fetch"), "error": st.get("error") or st.get("fetch_error") or ""}
    if st.get("error"):
        return {**base, "status": "bad", "label": "error", "issues": [issue("error", "bad", "error")]}
    if not st.get("present"):
        return {**base, "status": "warn", "label": "not cloned", "issues": [issue("not cloned", "warn", "missing")]}
    if not st.get("is_repo"):
        return {**base, "status": "bad", "label": "not a repo", "issues": [issue("not a repo", "bad", "error")]}
    issues = repo_issues(st)
    if issues:
        return {**base, "status": worst(i["tone"] for i in issues),
                "label": ", ".join(i["text"] for i in issues), "issues": issues}
    if st.get("branch") and not st.get("upstream"):
        return {**base, "status": "info", "label": "no upstream", "issues": [issue("no upstream", "info", "no-upstream")]}
    return {**base, "status": "ok", "label": "in sync", "issues": []}


# --- folders -------------------------------------------------------------------------------
STATE_WORDS = {"idle": "up to date"}


def folder_issues(f: dict) -> list[dict]:
    out = []
    if f.get("paused"):
        out.append(issue("paused", "warn", "paused"))
    if f.get("errors"):
        out.append(issue(f"{f['errors']} errors", "bad", "errors"))
    if f.get("conflicts"):
        out.append(issue(f"{len(f['conflicts'])} conflicts", "bad", "conflicts"))
    if f.get("need"):
        out.append(issue(f"{f['need']} to sync", "info", "pending"))
    return out


def folder_cell(f: dict | None, sy: dict | None) -> dict:
    if sy is None:
        return {"status": "none", "label": "no data", "issues": []}
    if f is None:
        return {"status": "absent", "label": "not shared here", "issues": []}
    issues = folder_issues(f)
    state = f.get("state") or "unknown"
    base = {"state": state, "type": f.get("type") or "", "error": f.get("error") or "",
            "conflicts": [tilde(c) for c in f.get("conflicts") or []][:200]}
    if issues:
        return {**base, "status": worst(i["tone"] for i in issues),
                "label": ", ".join(i["text"] for i in issues), "issues": issues}
    if state != "idle":
        return {**base, "status": "info", "label": STATE_WORDS.get(state, state), "issues": []}
    return {**base, "status": "ok", "label": "up to date", "issues": []}


# --- attention -----------------------------------------------------------------------------
def attention_items(st: dict) -> list[str]:
    """Built from the current snapshot (not only the last cycle), so it is right between cycles."""
    c = st.get("cycle") or {}
    items = [x for x in (st.get("banner"), c.get("error"), st.get("config_error")) if x]
    items += (st.get("syncthing") or {}).get("notes") or []
    for r in (st.get("repos") or {}).values():
        items += r.get("notes") or []
    items += c.get("skill_notes") or []
    items += st.get("naming_notes") or []
    items += [f"config conflict copy: {p}" for p in st.get("config_conflicts") or []]
    return items


def split_note(item: str) -> tuple[str, str]:
    """"GitHub/app: 2 uncommitted change(s)" -> ("GitHub/app", "2 uncommitted change(s)")."""
    subj, sep, msg = item.partition(": ")
    if not sep or " " in subj.strip("/"):
        return "", item
    return subj, msg


def attention(names: list[str], states: dict) -> list[dict]:
    groups: dict[tuple[str, str], dict] = {}
    for m in names:
        if not states.get(m):
            continue
        for x in attention_items(states[m]):
            subj, msg = split_note(x)
            g = groups.setdefault((m, subj or x), {"machine": m, "subject": tilde(subj or x), "messages": []})
            if subj:
                g["messages"].append(tilde(msg))
    return list(groups.values())


# --- machines, skills, activity, housekeeping ----------------------------------------------
def cycle_info(st: dict) -> dict:
    c = st.get("cycle") or {}
    return {"enabled": c.get("enabled", True), "running": bool(c.get("running")), "queued": bool(c.get("queued")),
            "started": c.get("started"), "finished": c.get("finished"), "next_due": c.get("next_due"),
            "error": c.get("error") or ""}


def machine(cfg: Config, name: str, st: dict | None, peer: dict | None) -> dict:
    me = name == cfg.machine
    if me:
        reach, seen, err = "ok", time.time(), ""
    elif not peer:
        reach, seen, err = "none", None, ""
    else:
        reach, seen, err = ("bad" if peer.get("error") else "ok"), peer.get("fetched") or None, peer.get("error") or ""
    sy = (st or {}).get("syncthing") or {}
    return {"name": name, "me": me, "reach": reach, "seen": seen, "error": err,
            "has_state": bool(st), "version": (st or {}).get("version") or "",
            "url": "" if me else cfg.machines[name].tailnet_url,
            "cycle": cycle_info(st or {}),
            "syncthing": {"reachable": bool(sy.get("reachable")), "error": sy.get("error") or "",
                          "connected": [{"name": c.get("name", ""), "connected": bool(c.get("connected"))}
                                        for c in sy.get("connected") or []]}}


def skills(name: str, st: dict | None) -> dict:
    if not st:
        return {"machine": name, "has_state": False}
    sk = st.get("skills") or {}
    targets = []
    for t in sk.get("targets") or []:
        problems = [{"name": r["name"], "status": r["status"]} for r in t["links"] if r["status"] != "ok"]
        problems += [{"name": s, "status": "dangling link"} for s in t["stale"]]
        targets.append({"path": tilde(t["path"]), "ok": t["ok"], "total": len(t["links"]), "problems": problems})
    return {"machine": name, "has_state": True, "source": tilde(sk.get("source", "")),
            "source_exists": bool(sk.get("source_exists")), "skills": list(sk.get("skills") or []),
            "targets": targets,
            "instructions": [{"path": tilde(i["path"]), "status": i["status"]} for i in sk.get("instructions") or []]}


def build(cfg: Config, own: dict, peers: dict) -> dict:
    """``own`` is this machine's snapshot; ``peers`` maps name -> {state, fetched, error}."""
    names = list(cfg.machines)
    states = {cfg.machine: own}
    for n, p in peers.items():
        if p.get("state") and n in cfg.machines:
            states[n] = p["state"]

    repos = []
    for entry in cfg.repos:
        cells = {}
        for m in names:
            st = states.get(m)
            cells[m] = repo_cell((st.get("repos") or {}).get(entry["path"]) if st else None,
                                 m in entry.get("machines", []))
        repos.append({"path": entry["path"], "url": entry.get("url") or "",
                      "remote": short_url(entry.get("url") or ""), "machines": cells,
                      "status": worst(c["status"] for c in cells.values())})

    order, info = [], {}
    for m in [cfg.machine] + [n for n in names if n != cfg.machine]:
        for f in ((states.get(m) or {}).get("syncthing") or {}).get("folders") or []:
            if f["id"] not in info:
                order.append(f["id"])
                info[f["id"]] = f
    folders = []
    for fid in order:
        cells = {}
        for m in names:
            sy = (states.get(m) or {}).get("syncthing") if states.get(m) else None
            by_id = {f["id"]: f for f in (sy or {}).get("folders") or []}
            cells[m] = folder_cell(by_id.get(fid), sy)
        f0 = info[fid]
        folders.append({"id": fid, "label": f0.get("label") or fid, "path": tilde(f0.get("path", "")),
                        "machines": cells, "status": worst(c["status"] for c in cells.values())})

    activity, housekeeping = [], []
    for m in names:
        st = states.get(m)
        if not st:
            continue
        c = st.get("cycle") or {}
        activity.append({"machine": m, "finished": c.get("finished"), "dry_run": bool(c.get("dry_run")),
                         "actions": [tilde(a) for a in (c.get("actions") or []) + (c.get("skill_actions") or [])]})
        housekeeping.append({"machine": m, "unlisted": [tilde(x) for x in st.get("unlisted") or []],
                             "naming": [tilde(x) for x in st.get("naming") or []],
                             "config_conflicts": [tilde(x) for x in st.get("config_conflicts") or []]})

    return {
        "me": cfg.machine,
        "version": own.get("version") or "",
        "generated": time.time(),
        "interval_s": cfg.interval_s,
        "cycle": cycle_info(own),
        "machines": [machine(cfg, m, states.get(m), peers.get(m)) for m in names],
        "attention": attention(names, states),
        "repos": repos,
        "folders": folders,
        "skills": [skills(m, states.get(m)) for m in names],
        "activity": activity,
        "housekeeping": housekeeping,
    }
