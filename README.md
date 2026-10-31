# Frame Art Manager — Home Assistant add-on + standalone web app

Crop, pair, matte and upload artwork to a Samsung Frame TV, then browse the TV's
library with thumbnails and run a browser-side slideshow.

This repository packages the same application two ways:

| Delivery | Where | How it reaches the TV |
|---|---|---|
| **Home Assistant add-on** | `frame_art_manager/` | The add-on talks to the TV. The page is served through HA Ingress, so it works remotely and needs no certificate trust step. The pairing token lives in the add-on's `/data`. |
| **Standalone web app** | `webapp/` | Your browser talks to the TV directly; `relay.py` bridges the raw image upload and `thumb_server.py` serves the thumbnail cache. |

The HTML is one file and knows which mode it is in: opened from disk it uses
`localhost:8765` / `127.0.0.1:8766`; served by the add-on it routes everything
through same-origin endpoints.

## Install the add-on

1. In Home Assistant: **Settings → Add-ons → Add-on Store → ⋮ → Repositories**.
2. Add `https://github.com/iscraigh/ha-frame-art-manager`.
3. Install **Frame Art Manager**, then open **Configuration** and set:
   - `tv_ip` — the TV's LAN address (e.g. `10.0.1.149`)
   - `log_level` — `info` by default
4. Start it. The sidebar entry **Frame Art** opens the app.

The first time the app connects, the TV asks to allow the connection — accept it
on the TV. The add-on stores the returned token in `/data/tv-token.txt`, so it
only asks once.

## Run the standalone app

```bash
cd webapp
python3 -m venv .venv
. .venv/bin/activate
pip install websockets samsungtvws pillow
./launch.sh          # starts relay.py + thumb_server.py and opens the page
```

Then enter the TV IP in the app, trust the TV certificate once
(`https://TV_IP:8002`), and click Connect.

## Layout

```
repository.yaml                 # makes this repo an HA add-on repository
frame_art_manager/              # the add-on
  config.yaml  Dockerfile  requirements.txt
  app/server.py                 # Ingress UI + TV proxying + thumbnails
  app/static/index.html         # synced copy of the web app (CI-checked)
webapp/                         # standalone app
  frame-art-manager.html        # canonical source
  relay.py  thumb_server.py  sync_thumbs.py  launch.sh
scripts/sync-webapp.sh          # copy webapp/ -> add-on static/
```

`webapp/frame-art-manager.html` is the canonical source. After editing it run
`scripts/sync-webapp.sh`; CI fails if the two copies differ.

## Credits and licence

Based on [boysbytes/frame-art-manager](https://github.com/boysbytes/frame-art-manager)
(MIT, © Louis Yong), with local additions: the 2024/2025 firmware compatibility
shim, the interactive 4K cropper, the TV-library thumbnail cache and the
browser-side slideshow. The TV protocol work derives from
[Nick Waterton's samsung-tv-ws-api](https://github.com/NickWaterton/samsung-tv-ws-api).
Released under the MIT licence — see `LICENSE`.
