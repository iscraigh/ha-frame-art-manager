# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
this project adheres to [Semantic Versioning](https://semver.org/).

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

[1.0.1]: https://github.com/iscraigh/ha-frame-art-manager/releases/tag/v1.0.1
[1.0.0]: https://github.com/iscraigh/ha-frame-art-manager/releases/tag/v1.0.0
