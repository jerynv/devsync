# Contributing to devsync

Thanks for taking a look. devsync touches people's repos and synced files, so a few rules matter
more than usual.

## Safety rules

- **Nothing destructive by default.** devsync fetches, clones missing repos, fast-forwards clean
  branches and links skills. Anything else (push, merge, rebase, reset, checkout, clean, deleting
  a branch, force, removing a Syncthing folder) needs an explicit click in the page, and lands
  only with tests that prove the guard holds.
- **All git goes through `devsync/gitops.py`.** It runs only the exact argument lists in
  `TEMPLATES`. Don't call git anywhere else. The tests that feed it forbidden commands block
  process creation, so a broken allowlist can't run them in your own checkout. Don't weaken that.
- **devsync never updates itself.** It reports "update available"; pulling and restarting is
  done by hand.
- **Trust comes from the listener, never the `Host` header.** The local listener (127.0.0.1 and
  ::1) trusts everything on the machine. The tailnet listener (127.0.0.1 only, reached through
  `tailscale serve`) requires an allowlisted `Tailscale-User-Login` on every request. Every bind
  is loopback; never bind a wildcard address.
- **Requests never do slow work.** Pages read a cached snapshot. Git status refreshes at most
  once a minute and only while a page is open; fetches and folder scans run on the sync cycle.
  `/api/state`, which other machines read, never triggers work.
- **Data is rendered as text.** The page gets plain JSON and React renders it as text. Never use
  `dangerouslySetInnerHTML` or `innerHTML`; a test checks for it.

## No personal data

Real configuration lives in `~/.config/devsync/`, never here: no machine names, hostnames,
tailnet names or IPs, logins, email addresses or personal paths in code, tests, fixtures,
examples, screenshots or logs. Use `example.com` / `example.invalid` and generic names like
`laptop` and `server`. Search your diff for these before you commit.

## Layout

- `devsync/`: the Python package (standard library only, Python 3.11+). `model.py` turns every
  machine's snapshot into the JSON the page shows, and all judgement about what's healthy, and
  where machines disagree (`drift()`), lives there, in tested Python. New fields from a newer
  machine may be missing from an older one; treat unknown as "no claim", never as a difference.
- `ui/`: the page, built with React, Tailwind and [shadcn/ui](https://ui.shadcn.com). It
  compiles into `devsync/web/`, which is committed, so running devsync never needs Node.
- `contrib/`: service templates. `examples/`: sample config.

## Working on it

```sh
python3 -m unittest discover -s tests -t .    # report how many tests ran; 0 means discovery broke
```

For page changes:

```sh
cd ui
npm ci
npm run dev       # live reload; proxies /api to a devsync on port 18765
npm run build     # typechecks, then writes devsync/web/ (commit the result)
```

Run a throwaway devsync to look at the page against a scratch config:

```sh
DEVSYNC_CONFIG_DIR=/tmp/devsync-config DEVSYNC_STATE_DIR=/tmp/devsync-state DEVSYNC_MACHINE=laptop \
  python3 -m devsync serve --no-cycle --local-port 18765 --tailnet-port 18766
```

Check it in light and dark mode and at phone width.

## Design notes

- Colour tokens follow shadcn's names and sit at the top of `ui/src/index.css`, in light and
  dark. Keep text and background pairs at WCAG AA contrast.
- Healthy states stay quiet: a dot and muted text. Only problems get a tinted pill.
- New pages go in `ui/src/routes.tsx`: one entry plus its component.

## Commits

Short imperative subject line. Keep each change focused, and include the test that shows it works.
