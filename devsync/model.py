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
    base = {"branch": st.get("branch") or "", "upstream": st.get("upstream") or "", "head": st.get("head") or "",
            "ahead": st.get("ahead") or 0, "behind": st.get("behind") or 0, "dirty": st.get("dirty") or 0,
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
    behind = [r for r in f.get("remote") or [] if r.get("completion", 100) < 100]
    if behind:
        out.append(issue(f"{behind[0]['name']} at {behind[0]['completion']:g}%", "info", "remote-behind"))
    return out


def folder_cell(f: dict | None, sy: dict | None) -> dict:
    if sy is None:
        return {"status": "none", "label": "no data", "issues": []}
    if f is None:
        return {"status": "absent", "label": "not shared here", "issues": []}
    issues = folder_issues(f)
    state = f.get("state") or "unknown"
    base = {"state": state, "type": f.get("type") or "", "error": f.get("error") or "",
            "conflicts": [tilde(c) for c in f.get("conflicts") or []][:200],
            "paused": bool(f.get("paused")), "need": f.get("need") or 0, "need_bytes": f.get("need_bytes") or 0,
            "local_files": f.get("local_files"), "global_files": f.get("global_files"),
            "local_bytes": f.get("local_bytes"), "global_bytes": f.get("global_bytes"),
            "state_changed": f.get("state_changed") or "", "devices": list(f.get("devices") or []),
            "remote": list(f.get("remote") or []), "error_paths": [tilde(p) for p in f.get("error_paths") or []]}
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
    gen = (st or {}).get("generated")
    return {"name": name, "me": me, "generated": gen, "reach": reach, "seen": seen, "error": err,
            "has_state": bool(st), "version": (st or {}).get("version") or "",
            "url": "" if me else cfg.machines[name].tailnet_url,
            "cycle": cycle_info(st or {}),
            "syncthing": {"reachable": bool(sy.get("reachable")), "error": sy.get("error") or "",
                          "connected": [{"name": c.get("name", ""), "connected": bool(c.get("connected")),
                                         "last_seen": c.get("last_seen", "")}
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


# --- drift: where machines disagree -------------------------------------------------------
def human_bytes(n) -> str:
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return ""


def _and(names) -> str:
    names = list(names)
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def short(sha: str) -> str:
    return (sha or "")[:7]


STALE_CYCLES = 2.5   # a machine whose last sync is older than this many intervals is "stale"
PEER_STALE_S = 600   # peer data older than this (while the page is open) is "stale"


def drift(cfg: Config, names: list[str], states: dict, peers: dict, now: float | None = None) -> list[dict]:
    """Every place where the machines disagree, worst first. Each item names the machines involved
    and what each one reports, so the page can show the comparison without judging anything."""
    now = now or time.time()
    out: list[dict] = []

    def add(area, kind, tone, subject, summary, per=None):
        out.append({"id": f"{area}:{kind}:{subject}", "area": area, "kind": kind, "tone": tone,
                    "subject": subject, "summary": summary, "machines": per or {}})

    have = [m for m in names if states.get(m)]

    # machines ----------------------------------------------------------------------------
    for m in names:
        if m == cfg.machine:
            continue
        p = peers.get(m) or {}
        if not states.get(m):
            if p.get("error"):
                add("machines", "no-data", "warn", m, p["error"])
            else:
                add("machines", "no-data", "info", m, "waiting for first contact")
        elif p.get("error"):
            add("machines", "unreachable", "warn", m,
                f"unreachable now; showing what it reported {_ago(p.get('fetched'), now)}", {m: p["error"]})
        elif p.get("fetched") and now - p["fetched"] > PEER_STALE_S:
            add("machines", "stale-peer", "info", m, f"last heard from {_ago(p['fetched'], now)}")
    for m in have:
        c = states[m].get("cycle") or {}
        if c.get("enabled", True) and c.get("finished") and now - c["finished"] > STALE_CYCLES * cfg.interval_s:
            add("machines", "stale-sync", "warn", m, f"last sync finished {_ago(c['finished'], now)}")
        for d in (states[m].get("syncthing") or {}).get("connected") or []:
            if not d.get("connected"):
                add("machines", "disconnected", "warn", f"{m} → {d.get('name', '?')}",
                    "Syncthing is not connected", {m: f"last seen {d.get('last_seen') or 'never'}"})
    versions = {m: states[m].get("version") or "?" for m in have}
    if len(set(versions.values())) > 1:
        add("machines", "version", "info", "devsync", "machines run different devsync versions", versions)

    # repos -------------------------------------------------------------------------------
    for entry in cfg.repos:
        path = entry["path"]
        kept = [m for m in entry.get("machines", []) if m in have]
        cells = {m: (states[m].get("repos") or {}).get(path) for m in kept}
        ok = {m: st for m, st in cells.items() if st and st.get("present") and st.get("is_repo") and not st.get("error")}
        missing = [m for m, st in cells.items() if st and not st.get("present") and not st.get("error")]
        if ok and missing:
            add("repos", "missing", "warn", path, f"cloned on {_and(ok)}, missing on {_and(missing)}")
        if len(ok) < 2:
            continue
        branches = {m: st.get("branch") or "(detached)" for m, st in ok.items()}
        if len(set(branches.values())) > 1:
            add("repos", "branch", "info", path, "different branches checked out", branches)
            continue
        heads = {m: st.get("head") for m, st in ok.items()}
        if all(heads.values()) and len(set(heads.values())) > 1:
            per = {}
            for m, st in ok.items():
                bits = [short(st["head"])]
                if st.get("ahead"):
                    bits.append(f"{st['ahead']} unpushed")
                if st.get("behind"):
                    bits.append(f"{st['behind']} behind {st.get('upstream') or 'upstream'}")
                if not st.get("ahead") and not st.get("behind") and st.get("upstream"):
                    bits.append(f"matches {st['upstream']}")
                per[m] = " · ".join(bits)
            add("repos", "commit", "warn", path, f"different commits of {next(iter(branches.values()))}", per)

    # folders -----------------------------------------------------------------------------
    reach = {m: states[m]["syncthing"] for m in have if (states[m].get("syncthing") or {}).get("reachable")}
    by_id: dict[str, dict] = {}
    for m, sy in reach.items():
        for f in sy.get("folders") or []:
            by_id.setdefault(f["id"], {})[m] = f
    for fid, on in by_id.items():
        label = next(iter(on.values())).get("label") or fid
        absent = [m for m in reach if m not in on]
        if absent:
            add("folders", "not-shared", "warn", label, f"shared on {_and(on)}, not on {_and(absent)}")
        paused = [m for m, f in on.items() if f.get("paused")]
        if paused and len(paused) < len(on):
            add("folders", "paused-one", "warn", label, f"paused on {_and(paused)} only")
        seen_remote = set()
        for m, f in on.items():
            for r in f.get("remote") or []:
                if r.get("completion", 100) < 100 and r["name"] not in seen_remote:
                    seen_remote.add(r["name"])
                    add("folders", "catching-up", "info", label,
                        f"{r['name']} is {r['completion']:g}% in sync",
                        {r["name"]: f"{r.get('need_items', 0)} item(s), {human_bytes(r.get('need_bytes'))} to go (seen from {m})"})
        settled = all(f.get("state") == "idle" and not f.get("need") and not f.get("paused")
                      and not any(r.get("completion", 100) < 100 for r in f.get("remote") or [])
                      and f.get("local_files") is not None
                      for f in on.values())
        counts = {m: f.get("local_files") for m, f in on.items()}
        if len(on) > 1 and settled and len(set(counts.values())) > 1:
            add("folders", "file-count", "info", label, "same folder, different file counts (ignore rules may differ)",
                {m: f"{n} files" for m, n in counts.items()})

    # skills ------------------------------------------------------------------------------
    sets = {m: set((states[m].get("skills") or {}).get("skills") or []) for m in have
            if (states[m].get("skills") or {}).get("source_exists")}
    if len(sets) > 1:
        union = set().union(*sets.values())
        per = {m: "missing " + ", ".join(sorted(union - s)) for m, s in sets.items() if union - s}
        if per:
            add("skills", "differ", "warn", "skills folder",
                f"{len(set().union(*(union - s for s in sets.values())))} skill(s) not on every machine", per)

    order = {m: i for i, m in enumerate(names)}
    for d in out:  # machines always listed in config order
        d["machines"] = dict(sorted(d["machines"].items(), key=lambda kv: order.get(kv[0], len(order))))
    rank = {"bad": 0, "warn": 1, "info": 2, "ok": 3}
    return sorted(out, key=lambda d: (rank.get(d["tone"], 9), d["area"], d["subject"]))


def _ago(ts, now) -> str:
    if not ts:
        return "never"
    s = max(0, now - ts)
    if s < 90:
        return "just now"
    if s < 5400:
        return f"{round(s / 60)} min ago"
    if s < 129600:
        return f"{round(s / 3600)} h ago"
    return f"{round(s / 86400)} d ago"


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

    activity, housekeeping, history = [], [], []
    for m in names:
        st = states.get(m)
        if not st:
            continue
        c = st.get("cycle") or {}
        activity.append({"machine": m, "finished": c.get("finished"), "dry_run": bool(c.get("dry_run")),
                         "actions": [tilde(a) for a in (c.get("actions") or []) + (c.get("skill_actions") or [])]})
        history += [{**h, "machine": m, "actions": [tilde(a) for a in h.get("actions") or []]}
                    for h in st.get("history") or []]
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
        "history": sorted(history, key=lambda h: h.get("finished") or 0, reverse=True)[:300],
        "housekeeping": housekeeping,
        "drift": drift(cfg, names, states, peers),
    }
