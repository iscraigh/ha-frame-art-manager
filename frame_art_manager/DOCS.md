# Frame Art Manager

Crop and upload artwork to a Samsung Frame TV, browse what is already on it,
and run a slideshow — all from the Home Assistant sidebar.

## Configuration

```yaml
tv_ip: 10.0.1.149        # required: the TV's LAN address
log_level: info          # debug | info | warning | error
```

## What it does

- Serves the app through HA Ingress (no extra ports, works remotely).
- Proxies the TV's art websocket, so the browser never needs to trust the TV's
  self-signed certificate.
- Relays image uploads over raw TCP, which browsers cannot open themselves.
- Stores the TV pairing token in `/data/tv-token.txt` (mode 0600).
- Caches TV artwork thumbnails in `/data/thumbs_cache.js`.

## First run

1. Make sure the TV is on and on the same network as Home Assistant.
2. Open **Frame Art**, then **TV Library → Connect**.
3. Accept the pairing prompt on the TV. The token is stored; later connections
   are silent.

If the TV is unreachable, check `tv_ip` and that port 8002 is not blocked
between the Home Assistant host and the TV.

## Troubleshooting

- **Thumbnails return 0.** The TV only serves thumbnails through the batch
  request `get_thumbnail_list`; the single `get_thumbnail` is silently ignored by
  some firmwares. The add-on tries the batch call first, then per item, and only
  then the single request — do not "simplify" that order.
- **Thumbnail sync fails even though the page lists artwork.** The TV serves one
  art client at a time. During a sync the page disconnects on purpose and the
  add-on runs as the only client, then the page reconnects.
- **Sync client never gets replies.** It must present its own pairing token
  (`/data/tv-token-sync.txt`), not the page's token: a foreign token is accepted
  for `get_content_list` but not for the thumbnail socket. Delete that file to
  force a fresh pairing.
- **Nothing connects.** Check `tv_ip`, that the TV is on, and that HA and the TV
  are on the same subnet (Samsung refuses websockets across VLANs).

## Notes

- This add-on replaces the standalone `relay.py` and `thumb_server.py`; you do
  not need to run them.
- The TV's own art websocket is single-client-ish: close the Samsung app's art
  screens if the connection is refused.
