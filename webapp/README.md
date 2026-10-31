# Standalone web app

Open `frame-art-manager.html` in a browser on the same network as the TV.

Two helpers must be running:

```bash
pip install websockets samsungtvws pillow
./launch.sh
```

- `relay.py` listens on `ws://localhost:8765` and forwards the two-phase image
  upload to the TV over raw TCP (browsers cannot open raw sockets).
- `thumb_server.py` listens on `http://127.0.0.1:8766` and provides:
  - `/sync?ip=TV_IP` — download artwork thumbnails into `thumbs_cache.js`
  - `/show?ip=TV_IP&id=CONTENT_ID` — display one artwork on the TV

First connection: enter the TV IP, click **Trust certificate** and accept the
warning at `https://TV_IP:8002`, then **Connect** and allow the pairing prompt
on the TV. The token is stored in `tv-token.txt` next to these files.

`thumbs_cache.js` is generated — do not commit it. `tv-token.txt` is a secret —
never commit it.
