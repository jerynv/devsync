"""Other machines' state (read-only JSON over the tailnet) and this machine's tailnet names."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
import urllib.request

from .config import Config, LiveConfig

MAC_CLI = "/Applications/Tailscale.app/Contents/MacOS/Tailscale"
UI_ACTIVE_S = 300   # fetch peers only while a page was viewed in the last 5 minutes
INTERVAL_S = 60
TIMEOUT_S = 2


def tailscale_cli(cfg: Config) -> list[str] | None:
    if cfg.tailscale_cli:
        return cfg.tailscale_cli
    found = shutil.which("tailscale")
    if found:
        return [found]
    if os.path.exists(MAC_CLI):
        return [MAC_CLI]
    return None


def tailnet_names(cfg: Config) -> set[str]:
    """Host names a browser may use for this machine on the tailnet: the MagicDNS name, its first
    label and the tailnet IPs. Compared case-insensitively. HostName is not used."""
    names = set(cfg.tailnet_hosts)
    cli = tailscale_cli(cfg)
    if not cli:
        return names
    try:
        r = subprocess.run(cli + ["status", "--self", "--peers=false", "--json"], capture_output=True,
                           text=True, timeout=5)
        me = json.loads(r.stdout)["Self"]
    except Exception:
        return names
    dns = (me.get("DNSName") or "").rstrip(".").lower()
    if dns:
        names.add(dns)
        names.add(dns.split(".")[0])
    for ip in me.get("TailscaleIPs") or []:
        names.add(f"[{ip.lower()}]" if ":" in ip else ip)
    return names


class Peers:
    def __init__(self, live: LiveConfig):
        self.live = live
        self.lock = threading.Lock()
        self.data: dict[str, dict] = {}   # name -> {"state", "fetched", "error", "tried"}
        self.ui_seen = 0.0
        self.kick = threading.Event()

    def touch(self):
        self.ui_seen = time.time()
        self.kick.set()

    def snapshot(self) -> dict:
        with self.lock:
            return {k: dict(v) for k, v in self.data.items()}

    def fetch_one(self, name: str, url: str):
        entry = {"tried": time.time()}
        try:
            req = urllib.request.Request(url + "/api/state", headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
                if "application/json" not in r.headers.get("Content-Type", ""):
                    raise ValueError("peer did not return JSON")
                state = json.loads(r.read(4 * 1024 * 1024))
            if not isinstance(state, dict):
                raise ValueError("peer returned something other than an object")
            entry.update(state=state, fetched=time.time(), error="")
        except Exception as e:
            entry["error"] = f"{e.__class__.__name__}: {getattr(e, 'reason', e)}"
        with self.lock:
            old = self.data.get(name, {})
            if entry.get("error"):
                entry["state"], entry["fetched"] = old.get("state"), old.get("fetched", 0)
            self.data[name] = entry

    def loop(self, stop: threading.Event):
        while not stop.is_set():
            if time.time() - self.ui_seen >= UI_ACTIVE_S:
                self.kick.wait(60)  # idle: sleep until a page is viewed
                self.kick.clear()
                continue
            cfg = self.live.get()
            for m in cfg.peers():
                last = self.data.get(m.name, {}).get("tried", 0)
                if m.tailnet_url and time.time() - last >= INTERVAL_S:
                    self.fetch_one(m.name, m.tailnet_url)
            stop.wait(5)
