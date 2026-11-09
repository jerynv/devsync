"""HTTP server: two loopback listeners with different trust.

* local   (127.0.0.1 and [::1], default port 8765): this machine's browser. Everything running on
          this machine is trusted, as with any loopback service on a single-user machine.
* tailnet (127.0.0.1 only, default port 8766): reached through ``tailscale serve``. Every request
          must carry an allowlisted Tailscale-User-Login (serve sets it and strips client copies).

Trust is decided by which listener accepted the connection, never by the Host header.
"""
from __future__ import annotations

import errno
import json
import signal
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from urllib.parse import urlsplit

from . import model
from .config import LiveConfig
from .cycle import Runner
from .peers import Peers, tailnet_names

LOCAL_HOSTS = frozenset({"devsync.localhost", "localhost", "127.0.0.1", "[::1]"})
# Scripts stay strict: only our own bundle runs. Styles allow inline because the UI's component
# library (Radix, Sonner) injects small <style> tags for scroll locking and toast placement.
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self'; connect-src 'self'; "
       "frame-ancestors 'none'; base-uri 'none'; form-action 'none'; object-src 'none'")


def host_only(value: str) -> str:
    v = value.strip().lower()
    if v.startswith("["):
        end = v.find("]")
        return v[: end + 1] if end > 0 else ""
    return v.rsplit(":", 1)[0] if v.count(":") == 1 else v


TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".woff2": "font/woff2", ".svg": "image/svg+xml",
         ".json": "application/json", ".txt": "text/plain; charset=utf-8", ".png": "image/png"}


def load_web() -> dict[str, tuple[bytes, str]]:
    """The built page (``ui/`` compiles into ``devsync/web``): URL path -> (body, content type)."""
    out: dict[str, tuple[bytes, str]] = {}
    root = resources.files("devsync") / "web"

    def walk(node, prefix):
        for child in node.iterdir():
            if child.is_dir():
                walk(child, f"{prefix}{child.name}/")
            else:
                ext = "." + child.name.rsplit(".", 1)[-1] if "." in child.name else ""
                out[f"{prefix}{child.name}"] = (child.read_bytes(), TYPES.get(ext, "application/octet-stream"))

    if root.is_dir():
        walk(root, "/")
    if "/index.html" in out:
        out["/"] = out["/index.html"]
    return out


class App:
    def __init__(self, live: LiveConfig, runner: Runner, peers: Peers):
        self.live, self.runner, self.peers = live, runner, peers
        self.static = load_web()  # loaded once, at startup
        self._names: set[str] = set()
        self._names_at = 0.0
        self._names_lock = threading.Lock()

    def tailnet_host_ok(self, host: str) -> bool:
        with self._names_lock:
            if host in self._names:
                return True
            if time.time() - self._names_at < 60:
                return False
            self._names = tailnet_names(self.live.get())
            self._names_at = time.time()
            return host in self._names


def make_handler(app: App, kind: str):
    class Handler(BaseHTTPRequestHandler):
        server_version = "devsync"
        sys_version = ""
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):  # keep the journal quiet
            pass

        # --- responses ---------------------------------------------------------------------
        def send(self, code: int, body: bytes, ctype: str, cache: str = "no-store"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Security-Policy", CSP)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cache-Control", cache)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def json(self, code: int, obj):
            self.send(code, json.dumps(obj).encode(), "application/json")

        def deny(self, code: int, why: str):
            self.json(code, {"error": why})

        # --- trust -------------------------------------------------------------------------
        def allowed(self) -> bool:
            host = host_only(self.headers.get("Host", ""))
            if kind == "local":
                if host not in LOCAL_HOSTS:
                    self.deny(421, "unexpected Host")
                    return False
                return True
            cfg = app.live.get()
            login = (self.headers.get("Tailscale-User-Login") or "").strip().lower()
            if not login or login not in cfg.tailnet_logins:
                self.deny(403, "tailnet identity not allowed")
                return False
            if not app.tailnet_host_ok(host):
                self.deny(421, "unexpected Host")
                return False
            return True

        def mutation_allowed(self) -> bool:
            if self.headers.get("X-Devsync") != "1":
                self.deny(403, "missing X-Devsync header")
                return False
            origin = self.headers.get("Origin")
            if origin is not None:
                parts = urlsplit(origin)
                ohost = (parts.hostname or "").lower()
                if ":" in ohost:
                    ohost = f"[{ohost}]"
                ok = ohost in LOCAL_HOSTS if kind == "local" else app.tailnet_host_ok(ohost)
                if parts.scheme not in ("http", "https") or not ok:
                    self.deny(403, "cross-origin request refused")
                    return False
            site = self.headers.get("Sec-Fetch-Site")
            if site is not None and site not in ("same-origin", "none"):
                self.deny(403, "cross-site request refused")
                return False
            return True

        # --- routes ------------------------------------------------------------------------
        def do_GET(self):
            if not self.allowed():
                return
            path = self.path.split("?", 1)[0]
            if path == "/api/dashboard":
                cfg = app.live.get()
                app.peers.touch()
                app.runner.maybe_refresh_status()
                self.json(200, model.build(cfg, app.runner.state(), app.peers.snapshot()))
            elif path == "/api/state":
                self.json(200, app.runner.state())  # cached snapshot; never triggers work
            elif path in app.static:
                body, ctype = app.static[path]
                # Built assets carry a content hash in their name, so they can be cached for good.
                cache = "max-age=31536000, immutable" if path.startswith("/assets/") else "no-store"
                self.send(200, body, ctype, cache)
            else:
                self.deny(404, "not found")

        do_HEAD = do_GET

        def do_POST(self):
            if not self.allowed() or not self.mutation_allowed():
                return
            n = int(self.headers.get("Content-Length") or 0)
            if n:
                self.rfile.read(min(n, 65536))
            if self.path == "/api/sync":
                self.json(202, {"status": app.runner.request_sync()})
            else:
                self.deny(404, "not found")

        def do_PUT(self):
            self.deny(405, "method not allowed")

        do_DELETE = do_PATCH = do_OPTIONS = do_PUT

    return Handler


class _Stop(Exception):
    pass


def _raise_stop(*_):
    raise _Stop


class Server4(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class Server6(Server4):
    address_family = socket.AF_INET6

    def server_bind(self):
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        super().server_bind()


def bind(app: App, kind: str, addr: str, port: int):
    cls = Server6 if ":" in addr else Server4
    return cls((addr, port), make_handler(app, kind))


def serve(live: LiveConfig, local_port: int | None = None, tailnet_port: int | None = None,
          tailnet: bool = True, cycle: bool = True) -> int:
    cfg = live.get()
    local_port = cfg.me.local_port if local_port is None else local_port
    tailnet_port = cfg.me.tailnet_port if tailnet_port is None else tailnet_port
    runner, peers = Runner(live), Peers(live)
    runner.enabled = cycle
    app = App(live, runner, peers)
    servers = []
    plan = [("local", "127.0.0.1", local_port), ("local", "::1", local_port)]
    if tailnet:
        plan.append(("tailnet", "127.0.0.1", tailnet_port))
    for kind, addr, port in plan:  # loopback only, never a wildcard address
        try:
            servers.append(bind(app, kind, addr, port))
        except OSError as e:
            if addr == "::1" and e.errno in (errno.EADDRNOTAVAIL, errno.EAFNOSUPPORT):
                print(f"devsync: IPv6 loopback unavailable, serving IPv4 only ({e})", file=sys.stderr)
                continue
            print(f"devsync: cannot listen on {addr}:{port}: {e}", file=sys.stderr)
            for s in servers:
                s.server_close()
            return 1
    stop = threading.Event()
    threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in servers]
    threads.append(threading.Thread(target=peers.loop, args=(stop,), daemon=True))
    if cycle:
        threads.append(threading.Thread(target=runner.loop, args=(stop,), daemon=True))
    else:
        runner.maybe_refresh_status()
    for t in threads:
        t.start()
    bound = ", ".join(f"{s.server_address[0]}:{s.server_address[1]}" for s in servers)
    print(f"devsync {cfg.machine}: listening on {bound}", file=sys.stderr, flush=True)
    signal.signal(signal.SIGTERM, _raise_stop)  # raise, don't take locks inside a signal handler
    try:
        while True:
            time.sleep(3600)
    except (KeyboardInterrupt, _Stop):
        pass
    stop.set()
    runner.wake.set()
    peers.kick.set()
    for s in servers:
        s.shutdown()
        s.server_close()
    return 0
