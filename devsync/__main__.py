"""Command line: python3 -m devsync serve | sync [--dry-run] [--print] | status"""
from __future__ import annotations

import argparse
import sys

from . import __version__
from .config import ConfigError, LiveConfig, load


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="devsync", description="Keep your machines lined up.")
    ap.add_argument("--version", action="version", version=f"devsync {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve", help="run the web app and the sync cycle")
    s.add_argument("--local-port", type=int)
    s.add_argument("--tailnet-port", type=int)
    s.add_argument("--no-tailnet", action="store_true", help="don't open the tailnet listener")
    s.add_argument("--no-cycle", action="store_true", help="never run the sync cycle (dashboard only)")
    y = sub.add_parser("sync", help="run one cycle now")
    y.add_argument("--dry-run", action="store_true", help="report only: no fetch, clone, fast-forward, "
                   "linking or file writes")
    y.add_argument("--print", action="store_true", help="print the full report")
    sub.add_parser("status", help="same as: sync --dry-run --print")
    args = ap.parse_args(argv)

    try:
        if args.cmd == "serve":
            from .server import serve
            return serve(LiveConfig(), args.local_port, args.tailnet_port,
                         tailnet=not args.no_tailnet, cycle=not args.no_cycle)
        from .cycle import CycleBusy, report_lines, run_cycle
        cfg = load()
        dry = args.cmd == "status" or args.dry_run
        try:
            snap = run_cycle(cfg, dry_run=dry)
        except CycleBusy as e:
            print(f"devsync: {e}", file=sys.stderr)
            return 75
        full, summary = report_lines(cfg, snap)
        print("\n".join(full if (args.cmd == "status" or args.print) else summary))
        return 0
    except ConfigError as e:
        print(f"devsync: {e}", file=sys.stderr)
        return 78


if __name__ == "__main__":
    sys.exit(main())
