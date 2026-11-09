"""Read-only Syncthing health through its local REST API (address, TLS and API key from config.xml)."""
from __future__ import annotations

import json
import os
import re
import ssl
import urllib.request
from pathlib import Path

CONFIG_CANDIDATES = [
    "~/.local/state/syncthing/config.xml",
    "~/.config/syncthing/config.xml",
    "~/Library/Application Support/Syncthing/config.xml",
]


class Syncthing:
    def __init__(self, base: str, key: str, insecure_tls: bool):
        self.base, self.key = base, key
        self.ctx = ssl._create_unverified_context() if insecure_tls else None  # loopback, self-signed

    @classmethod
    def discover(cls) -> "Syncthing | None":
        env = os.environ.get("DEVSYNC_SYNCTHING_CONFIG")
        paths = [env] if env else CONFIG_CANDIDATES
        for p in paths:
            path = Path(os.path.expanduser(p))
            if path.exists():
                return cls.from_xml(path.read_text())
        return None

    @classmethod
    def from_xml(cls, xml: str) -> "Syncthing":
        key = re.search(r"<apikey>([^<]+)</apikey>", xml).group(1)
        gui = re.search(r"<gui([^>]*)>(.*?)</gui>", xml, re.S)
        addr = re.search(r"<address>([^<]+)</address>", gui.group(2)).group(1)
        tls = 'tls="true"' in gui.group(1)
        return cls(f"{'https' if tls else 'http'}://{addr}/rest", key, tls)

    def get(self, path: str, timeout: float = 10):
        req = urllib.request.Request(self.base + path, headers={"X-API-Key": self.key})
        with urllib.request.urlopen(req, timeout=timeout, context=self.ctx) as r:
            return json.load(r)


def find_conflicts(root: str, skip_dirs: set[str], skipped: list[str]) -> list[str]:
    found = []

    def onerror(e: OSError):
        skipped.append(f"{e.filename}: {e.strerror or e}")

    for dirpath, dirs, files in os.walk(root, onerror=onerror):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        found += [os.path.join(dirpath, n) for n in files if ".sync-conflict-" in n]
    return found


def health(skip_dirs: list[str], walk: bool, client: Syncthing | None = None) -> dict:
    """Folder and connection status. ``walk`` also scans folders for conflict copies (slow)."""
    out = {"reachable": False, "error": "", "connected": [], "folders": [], "notes": [], "walked": walk}
    st = client or Syncthing.discover()
    if st is None:
        out["error"] = "not installed"
        out["notes"].append("Syncthing: not installed")
        return out
    try:
        conns = st.get("/system/connections")["connections"]
        devices = {d["deviceID"]: d.get("name", "") for d in st.get("/config/devices")}
        try:
            seen = st.get("/stats/device")
        except Exception:
            seen = {}
        out["connected"] = [{"name": devices.get(did, did[:7]), "connected": bool(c.get("connected")),
                             "last_seen": (seen.get(did) or {}).get("lastSeen", "")}
                            for did, c in conns.items()]
        try:
            my_id = st.get("/system/status").get("myID", "")
        except Exception:
            my_id = ""
        if conns and not any(c.get("connected") for c in conns.values()):
            out["notes"].append("Syncthing: the other machine is not connected (files will catch up when it is)")
        skip = set(skip_dirs)
        for f in st.get("/config/folders"):
            s = st.get(f"/db/status?folder={urllib.request.quote(f['id'])}")
            errors = s.get("errors") or s.get("pullErrors") or 0  # pullErrors is the old alias
            row = {"id": f["id"], "label": f.get("label") or f["id"], "path": f["path"], "type": f["type"],
                   "paused": bool(f.get("paused")), "state": s.get("state", ""), "errors": errors,
                   "error": s.get("error") or s.get("watchError") or "", "need": s.get("needTotalItems", 0),
                   "conflicts": [], "skipped": [],
                   "local_files": s.get("localFiles", 0), "global_files": s.get("globalFiles", 0),
                   "local_bytes": s.get("localBytes", 0), "global_bytes": s.get("globalBytes", 0),
                   "need_bytes": s.get("needBytes", 0), "state_changed": s.get("stateChanged", ""),
                   "devices": [], "remote": []}
            for d in f.get("devices") or []:
                did = d.get("deviceID", "")
                if did == my_id:
                    continue
                name = devices.get(did, did[:7])
                row["devices"].append(name)
                if conns.get(did, {}).get("connected") and not row["paused"]:
                    try:
                        c = st.get(f"/db/completion?folder={urllib.request.quote(f['id'])}&device={did}")
                        row["remote"].append({"name": name, "completion": round(float(c.get("completion", 0)), 1),
                                              "need_items": c.get("needItems", 0), "need_bytes": c.get("needBytes", 0)})
                    except Exception:
                        pass
            if errors:
                try:
                    fe = st.get(f"/folder/errors?folder={urllib.request.quote(f['id'])}&perpage=5")
                    row["error_paths"] = [e.get("path", "") for e in (fe.get("errors") or [])]
                except Exception:
                    row["error_paths"] = []
                out["notes"].append(f"Syncthing '{row['label']}': {errors} error(s)")
            if row["paused"]:
                out["notes"].append(f"Syncthing '{row['label']}': paused")
            if walk:
                row["conflicts"] = find_conflicts(f["path"], skip, row["skipped"])
            out["folders"].append(row)
        out["reachable"] = True
        out["notes"] += walk_notes(out["folders"])
    except Exception as e:  # Syncthing down or still starting
        out["error"] = e.__class__.__name__
        out["notes"].append(f"Syncthing: not reachable ({e.__class__.__name__})")
    return out


def walk_notes(folders: list[dict]) -> list[str]:
    """Notes from the (slow) folder walk; also re-attached between cycles from the last walk."""
    notes = [f"Syncthing '{r['label']}': conflict scan could not read {len(r['skipped'])} folder(s), "
             f"e.g. {r['skipped'][0]}" for r in folders if r.get("skipped")]
    conflicts = [c for r in folders for c in r.get("conflicts") or []]
    if conflicts:
        notes.append(f"Syncthing: {len(conflicts)} conflict copy(ies), e.g. {conflicts[0]}")
    return notes


def config_conflicts(cdir: Path) -> list[str]:
    try:
        return sorted(str(p) for p in cdir.iterdir() if ".sync-conflict-" in p.name)
    except OSError:
        return []
