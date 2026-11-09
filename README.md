# devsync

I work across a couple of machines, and I got tired of finding out on the wrong one that a repo
was three commits behind, a Syncthing folder had quietly stopped, or my agent skills weren't
linked. devsync is the small web page I keep open instead. Each machine runs its own copy, and
every copy shows every machine.

It looks after three things:

- **Repos.** You list them in `repos.toml` (path, clone URL, which machines keep it). devsync
  clones what's missing, fetches, fast-forwards branches that are clean, and shows what's behind,
  unpushed or uncommitted on each machine.
- **Synced folders.** Syncthing folders, read through Syncthing's local API: whether they're up
  to date, paused or erroring, and any conflict copies lying around.
- **Agent skills.** One shared skills folder, linked into each agent CLI's skills directory, plus
  the instruction files that point at it.

It runs a sync every 15 minutes, or when you press **Sync now**.

## What it won't do

devsync only takes safe steps on its own: fetch, clone a missing repo, fast-forward a clean
branch, fix a skill link. It never pushes, merges, rebases, resets, deletes a branch or removes a
folder. It also never updates its own checkout; when there's a new version it tells you, and you
pull and restart it yourself.

## Running it

You need Python 3.11 or newer. Nothing else gets installed: the server is standard library only,
and the web page ships prebuilt inside the package.

```sh
mkdir -p ~/.config/devsync
cp examples/config.example.toml ~/.config/devsync/config.toml    # then edit it
cp examples/repos.example.toml  ~/.config/devsync/repos.toml
cp examples/folders.example.tsv ~/.config/devsync/folders.tsv

DEVSYNC_MACHINE=laptop python3 -m devsync status   # a dry run: prints a report, changes nothing
DEVSYNC_MACHINE=laptop python3 -m devsync serve    # then open http://devsync.localhost:8765
```

Your config lives in `~/.config/devsync`, never in this repo. Keeping that folder in Syncthing
is the easy way to share one config between machines. `contrib/` has a systemd user unit and a
macOS LaunchAgent template for running it in the background.

### Without the port

`devsync.localhost` always means the machine you're sitting at; browsers send `*.localhost` to
your own computer. To drop the `:8765`, devsync has to answer on port 80:

- **Linux:** allow unprivileged programs to use port 80
  (`sysctl net.ipv4.ip_unprivileged_port_start=80`) and start devsync with `--local-port 80`.
- **macOS:** normal programs can't listen on port 80 at all, so forward it with a `pf` rule
  (loopback port 80 to 8765). This needs `sudo` once.

### From your other machines

devsync only ever listens on loopback. To reach one machine's page from another, put it behind
[Tailscale](https://tailscale.com/kb/1312/serve):

```sh
tailscale serve --bg --http=80 http://127.0.0.1:8766
```

Then open `http://<machine-name>/` from anywhere on your tailnet. Requests through that port must
carry a Tailscale login you've allowlisted in `config.toml`. Nothing is exposed past your tailnet.

## Status

It's been running on my machines daily. The dashboard reads everything and **Sync now** works on
the machine you're on. Next up: per-machine repo switches and pausing or resuming Syncthing
folders from the page.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The short version: run the tests, keep personal data out
of the repo, and anything that changes something on disk needs an explicit click and a test that
proves the guard.

## License

devsync is released into the public domain under the [Unlicense](LICENSE): do whatever you like
with it. The bundled Geist and Geist Mono fonts keep their own
[SIL Open Font License](ui/src/fonts/OFL.txt).
