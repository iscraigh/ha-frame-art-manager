# Contributing

Thanks for improving Frame Art Manager. This repository ships the same
application two ways, so most changes touch one source file and one sync step.

## Layout, and what is canonical

```
webapp/frame-art-manager.html        # canonical application source
frame_art_manager/app/static/index.html   # generated copy used by the add-on
scripts/sync-webapp.sh               # copies the former to the latter
```

**Edit `webapp/frame-art-manager.html` only.** Then:

```bash
./scripts/sync-webapp.sh
```

CI fails if the two files differ, so an unsynced edit cannot be merged.

The HTML must work in both modes:

- opened from disk → `window.FAM_ADDON` is undefined; the app uses
  `ws://localhost:8765`, `http://127.0.0.1:8766` and connects to the TV directly
- served by the add-on → the server injects `window.FAM_ADDON = {tvIp: "..."}`
  and the app routes everything through same-origin endpoints (`tv`, `upload`,
  `sync`, `show`)

Any new network call belongs behind that flag. Keep the standalone path working —
it is the original app, and people still use it.

## Running the add-on server locally

The server only needs a data directory and a port; the TV is optional for UI work.

```bash
python3 -m venv .venv
.venv/bin/pip install -r frame_art_manager/requirements.txt

mkdir -p /tmp/famtest
printf '{"tv_ip": "10.0.1.149", "log_level": "debug"}' > /tmp/famtest/options.json

FAM_DATA=/tmp/famtest FAM_PORT=18099 python3 frame_art_manager/app/server.py
```

Then check:

```bash
curl -s localhost:18099/health
curl -s localhost:18099/ | grep -o 'window.FAM_ADDON = {[^}]*};'
curl -s -o /dev/null -w '%{http_code}\n' localhost:18099/api/hassio_ingress/fake/
```

`FAM_PORT` exists because 8099 may already be taken on a dev machine; inside the
add-on container it is always 8099.

Testing against a real TV needs the TV's IP and network access to port 8001/8002,
and the first connection asks for approval on the TV.

## Checks before committing

```bash
./scripts/sync-webapp.sh
python3 -m py_compile frame_art_manager/app/server.py webapp/*.py
```

CI runs the copy comparison and the Python compile on every push and pull request.
If you change the JavaScript, load the page in a browser (or the add-on) and
check the console — a syntax error in one script block stops the app from booting.

## Versioning

The add-on version comes from `frame_art_manager/config.yaml`; keep it in step
with the git tag and `CHANGELOG.md`.

- bug fix → patch (`1.0.1`)
- new feature, backwards compatible → minor (`1.1.0`)
- breaking change to options or endpoints → major (`2.0.0`)

`CHANGELOG.md` follows Keep a Changelog; add an entry under a new version heading.

## Release checklist

```bash
# 1. edit webapp/frame-art-manager.html
# 2. sync and bump
./scripts/sync-webapp.sh
$EDITOR frame_art_manager/config.yaml   # version: "1.0.1"
$EDITOR CHANGELOG.md                    # new heading + notes

# 3. verify
python3 -m py_compile frame_art_manager/app/server.py webapp/*.py

# 4. commit, tag, push
git add -A
git commit -m "Describe the change"
git tag -a v1.0.1 -m "Frame Art Manager 1.0.1"
git push origin main --tags

# 5. GitHub release
gh release create v1.0.1 --title "Frame Art Manager 1.0.1" --notes "See CHANGELOG.md"
```

Home Assistant shows a new add-on version after the repository is reloaded in the
Add-on Store (⋮ → Check for updates).

## Never commit

- `tv-token.txt` — the TV pairing token (`.gitignore` covers it)
- `thumbs_cache.js` — generated artwork cache
- `.venv/` — local virtualenv, full of symlinks and platform binaries

If you ever suspect a token was committed, rotate it by deleting the pair from
the TV's **Device Connection Manager → Device List** and reconnecting.

## Reporting problems

Open an issue with:

- the add-on log (`Settings → Add-ons → Frame Art Manager → Log`), at
  `log_level: debug`
- the output of `/health`
- your TV model and firmware year — behaviour differs sharply between 2019–2021
  and 2022–2025 Frames
