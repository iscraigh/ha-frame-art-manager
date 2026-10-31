# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
this project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.8] — 2026-10-31

### Changed

- `get_thumbnail` now tries the art app's own instance id (taken from the `from`
  field of its replies) before falling back to `host`. Newer firmware may only
  serve the d2d thumbnail request when it is addressed to the app instance;
  older firmware expects `host`. Each attempt is 8 s, so a failure is still
  bounded.

## [1.0.7] — 2026-10-31

### Fixed

- `get_thumbnail` was silently ignored by the TV because `conn_info.id` was an
  arbitrary string. It is now a UUID (as `samsungtvws` sends) and the request id
  is a UUID too. Debug logs showed the request leaving and no reply arriving;
  this firmware validates the id shape before opening the d2d socket.

## [1.0.6] — 2026-10-31

### Added

- `log_level: debug` now records the art traffic in both directions
  (`browser->TV` / `TV->browser`, truncated to 400 characters), so a request the
  TV never answers is visible in the add-on log.
- The first thumbnail failure on the page is reported to `/thumb-debug` with its
  error message, so a timeout or TV error lands in the add-on log without
  needing the browser console.

## [1.0.5] — 2026-10-31

### Added

- Diagnostic for thumbnail replies that arrive without `conn_info`: the page
  reports the raw reply to `POST /thumb-debug`, the add-on logs it (truncated)
  as `get_thumbnail reply without conn_info: ...`, and the first failure is also
  shown in the page so the shape is visible without devtools.

### Changed

- A TV error for `get_thumbnail`/`get_thumbnail_list` now rejects the matching
  pending request instead of leaving it to hit the 15 s timeout.
- `conn_info` is accepted at the top level or nested under `data`, as a string or
  an object.

## [1.0.4] — 2026-10-31

### Fixed

- Thumbnail sync hung (then timed out) because the TV serves **one art client at
  a time**: the add-on's own samsungtvws connection connected but never received
  replies while the page held the art channel.
- Thumbnails are now requested over the page's existing art connection:
  `get_thumbnail` returns `conn_info`, the page posts it to the new `POST /thumb`
  endpoint, and the add-on performs the raw TCP read the browser cannot.
  Progress is shown on the button (`⏳ 12/67`), and failures are counted.
- `POST /thumb` reads the TV's 4-byte-length + JSON-header + file frame with
  bounds checks, converts to a 320×180 JPEG data URL, and never returns more
  than 16 MB.

## [1.0.3] — 2026-10-31

### Fixed

- Thumbnail sync hung indefinitely after "Thumbnail sync requested". The
  server-side samsungtvws connection was opening with the same client name as
  the page's proxied connection, so the TV routed the replies to one socket and
  the other waited forever. It now connects under its own identity with its own
  token file (`/data/tv-token-sync.txt`, seeded from the existing pairing).
- The sync request has a hard 120 s ceiling; on timeout it returns a clear
  message ("accept the allow prompt on the TV and retry") instead of hanging.
- Logs distinguish requested / finished / timed out.

## [1.0.2] — 2026-10-31

### Fixed

- The page now receives the exact Ingress prefix from Home Assistant
  (`X-Ingress-Path`) instead of deriving it from `location.pathname`, so sync and
  "show on TV" always address the add-on rather than a sibling HA path.
- The TV address is filled in as soon as the adapter runs and the thumbnail
  button uses the configured `tv_ip` directly; it can no longer fall through to
  an IP prompt whose cancellation silently does nothing.
- Thumbnail sync logs a start line and the final count at `info`, so a request
  that never arrives is distinguishable from one that runs and finds nothing.
- Removed a deprecated aiohttp websocket timeout argument that printed a
  `DeprecationWarning` on every start.

## [1.0.1] — 2026-10-31

### Fixed

- Thumbnail sync failed on firmwares that reject `get_thumbnail_list` with
  `TV error -1`. The add-on now fetches each thumbnail with `get_thumbnail`
  (per item), so one unsupported batch request can no longer empty the library.
- Thumbnail sync and "show on TV" now use the same client name (`FrameArtManager`)
  as the app, so the pairing token already stored on the TV is reused instead of
  opening a second, unauthorised client identity.
- The page no longer shows a scary error box for TV errors that belong to the
  add-on's own thumbnail requests — the TV broadcasts those to every connected
  art client. They are logged to the console instead.
- The sync failure message in add-on mode no longer tells you to run `launch.sh`.

## [1.0.0] — 2026-10-31

First packaged release. The application itself is based on
[boysbytes/frame-art-manager](https://github.com/boysbytes/frame-art-manager);
this release adds the Home Assistant packaging and the local feature work that
had only existed as loose files.

### Added

- **Home Assistant add-on** (`frame_art_manager/`): serves the app behind HA
  Ingress with a sidebar panel entry, configured by `tv_ip` and `log_level`.
- **TV proxy**: the add-on owns the connection to the television.
  - `WS /tv` proxies the `com.samsung.art-app` websocket and captures the
    pairing token into `/data/tv-token.txt` (0600).
  - `WS /upload` relays the raw TCP image frame, replacing `relay.py`.
  - `GET /sync` and `GET /show` replace `thumb_server.py`.
  - `GET /health` reports configuration and token state.
- **Single-file dual mode**: `webapp/frame-art-manager.html` detects whether it
  is served by the add-on (`window.FAM_ADDON`) or opened standalone, and routes
  TV, relay and thumbnail calls accordingly. The add-on hides the certificate
  trust step and locks the TV address to the configured option.
- **Standalone web app** (`webapp/`): the original workflow preserved —
  `launch.sh`, `relay.py`, `thumb_server.py`, `sync_thumbs.py`.
- **Interactive 4K cropper** with aspect ratios, matte padding, zoom and rotate.
- **TV Library thumbnails**: cached previews, "show on TV", multi-select delete.
- **Browser-side slideshow** with playlists.
- **2024/2025 firmware compatibility shim** for `set_slideshow_status`,
  `change_matte` and `set_auto_rotation_status`.
- **Diptych framing** with generated matte textures.
- CI check that the webapp and add-on copies of the HTML stay identical and that
  all Python compiles; `scripts/sync-webapp.sh` to sync them.
- Add-on icon, logo, `DOCS.md` and this changelog.

### Changed

- Scripts that sat after `</body></html>` in the application moved inside the
  document body.

### Fixed

- Upload tracking stays in sync when artwork is deleted on the TV.
- Sequential uploads no longer contaminate each other's `image_added` handlers.
- UI reflects a closed websocket connection.

[1.0.8]: https://github.com/iscraigh/ha-frame-art-manager/releases/tag/v1.0.8
[1.0.7]: https://github.com/iscraigh/ha-frame-art-manager/releases/tag/v1.0.7
[1.0.6]: https://github.com/iscraigh/ha-frame-art-manager/releases/tag/v1.0.6
[1.0.5]: https://github.com/iscraigh/ha-frame-art-manager/releases/tag/v1.0.5
[1.0.4]: https://github.com/iscraigh/ha-frame-art-manager/releases/tag/v1.0.4
[1.0.3]: https://github.com/iscraigh/ha-frame-art-manager/releases/tag/v1.0.3
[1.0.2]: https://github.com/iscraigh/ha-frame-art-manager/releases/tag/v1.0.2
[1.0.1]: https://github.com/iscraigh/ha-frame-art-manager/releases/tag/v1.0.1
[1.0.0]: https://github.com/iscraigh/ha-frame-art-manager/releases/tag/v1.0.0
