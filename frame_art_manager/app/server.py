"""Frame Art Manager — Home Assistant add-on server.

One aiohttp process serves the single-page app behind HA Ingress and acts as
the only thing that talks to the television:

  WS  .../tv      websocket proxy -> wss://TV:8002/api/v2/channels/com.samsung.art-app
  WS  .../upload  websocket proxy -> raw TCP image frame (the browser cannot
                  open raw sockets; this replaces relay.py)
  GET .../sync    pull artwork thumbnails from the TV into thumbs_cache.js
  GET .../show    display one artwork on the TV
  GET .../        the application itself

The TV pairing token is kept in /data/tv-token.txt and captured from the
first successful `ms.channel.connect`, so the browser never needs it.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import ssl
import sys
from pathlib import Path
from urllib.parse import quote

from aiohttp import ClientSession, ClientWSTimeout, WSMsgType, web

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
DATA_DIR = Path(os.environ.get("FAM_DATA", "/data"))
TOKEN_FILE = DATA_DIR / "tv-token.txt"
THUMBS_FILE = DATA_DIR / "thumbs_cache.js"
OPTIONS_FILE = DATA_DIR / "options.json"

ART_CHANNEL = "/api/v2/channels/com.samsung.art-app"
INGRESS_PREFIX = re.compile(r"^/api/hassio_ingress/[^/]+")
CLIENT_NAME = base64.b64encode(b"FrameArtManager").decode()
# samsungtvws wants the plain name; it base64-encodes it itself. This must match
# the app so the pairing token already stored on the TV is accepted.
TV_CLIENT_NAME = "FrameArtManager"
MAX_UPLOAD = 64 * 1024 * 1024

log = logging.getLogger("frame_art_manager")


def load_options() -> dict:
    """Read Home Assistant add-on options, tolerating a plain dev run."""
    try:
        return json.loads(OPTIONS_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as ex:
        log.warning("Could not read %s: %s", OPTIONS_FILE, ex)
        return {}


OPTIONS = load_options()
TV_IP = str(OPTIONS.get("tv_ip") or "").strip()
LOG_LEVEL = str(OPTIONS.get("log_level") or "info").upper()
PORT = int(os.environ.get("FAM_PORT", "8099"))


def read_token() -> str:
    try:
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def write_token(token: str) -> None:
    if not token:
        return
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(token, encoding="utf-8")
        os.chmod(TOKEN_FILE, 0o600)
        log.info("Stored a new TV pairing token")
    except OSError as ex:
        log.warning("Could not persist the TV token: %s", ex)


def insecure_ssl() -> ssl.SSLContext:
    """The Frame serves a self-signed certificate on 8002."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def tv_host(fallback: str = "") -> str:
    host = TV_IP or fallback
    if not host:
        raise RuntimeError("No TV IP configured — set 'tv_ip' in the add-on options")
    return host


# ── Art channel proxy ────────────────────────────────────────────────────


async def _open_art_channel(session: ClientSession):
    """Connect to the TV art channel, trying the usual port/scheme pairs."""
    token = read_token()
    query = f"?name={CLIENT_NAME}"
    if token:
        query += "&token=" + quote(token, safe="")
    host = tv_host()
    last: Exception | None = None
    for scheme, port in (("wss", 8002), ("ws", 8001), ("wss", 8001), ("ws", 8002)):
        url = f"{scheme}://{host}:{port}{ART_CHANNEL}{query}"
        try:
            ws = await session.ws_connect(
                url,
                ssl=insecure_ssl() if scheme == "wss" else None,
                heartbeat=30,
                max_msg_size=0,
                timeout=ClientWSTimeout(ws_close=10),
            )
            log.info("Art channel connected over %s://%s:%s", scheme, host, port)
            return ws
        except Exception as ex:  # noqa: BLE001 - try the next transport
            last = ex
            log.debug("Art channel %s://%s:%s failed: %s", scheme, host, port, ex)
    raise RuntimeError(f"could not reach the TV art channel: {last}")


def _capture_token(payload: str) -> None:
    """Persist the token the TV returns on a successful handshake."""
    try:
        msg = json.loads(payload)
    except (TypeError, ValueError):
        return
    if msg.get("event") != "ms.channel.connect":
        return
    token = (msg.get("data") or {}).get("token")
    if token and token != read_token():
        write_token(str(token))


async def handle_tv(request: web.Request) -> web.WebSocketResponse:
    client = web.WebSocketResponse(heartbeat=30, max_msg_size=MAX_UPLOAD)
    await client.prepare(request)

    async with ClientSession() as session:
        try:
            tv = await _open_art_channel(session)
        except Exception as ex:  # noqa: BLE001 - reported to the page
            log.warning("%s", ex)
            await client.send_str(
                json.dumps({"event": "fam.error", "data": {"message": str(ex)}})
            )
            await client.close()
            return client

        async def browser_to_tv() -> None:
            async for msg in client:
                if msg.type == WSMsgType.TEXT:
                    await tv.send_str(msg.data)
                elif msg.type == WSMsgType.BINARY:
                    await tv.send_bytes(msg.data)
                else:
                    break
            await tv.close()

        async def tv_to_browser() -> None:
            async for msg in tv:
                if msg.type == WSMsgType.TEXT:
                    _capture_token(msg.data)
                    if not client.closed:
                        await client.send_str(msg.data)
                elif msg.type == WSMsgType.BINARY:
                    if not client.closed:
                        await client.send_bytes(msg.data)
                else:
                    break
            await client.close()

        await asyncio.gather(browser_to_tv(), tv_to_browser(), return_exceptions=True)

    return client


# ── Upload relay (raw TCP, replaces relay.py) ────────────────────────────


def send_frame(host: str, port: int, secured: bool, data: bytes) -> None:
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(30)
    try:
        if secured:
            ctx = insecure_ssl()
            sock = ctx.wrap_socket(sock, server_hostname=host)
        sock.connect((host, port))
        sock.sendall(data)
    finally:
        sock.close()


async def handle_upload(request: web.Request) -> web.WebSocketResponse:
    client = web.WebSocketResponse(heartbeat=None, max_msg_size=MAX_UPLOAD)
    await client.prepare(request)
    try:
        first = await client.receive(timeout=15)
        if first.type != WSMsgType.TEXT:
            raise RuntimeError("expected a JSON target frame first")
        target = json.loads(first.data)
        frame = await client.receive(timeout=90)
        if frame.type == WSMsgType.BINARY:
            data = frame.data
        elif frame.type == WSMsgType.TEXT:
            data = frame.data.encode("latin-1")
        else:
            raise RuntimeError("no image frame received")

        host = tv_host(str(target.get("ip") or ""))
        port = int(target.get("port") or 8002)
        secured = bool(target.get("secured", True))
        log.info("Relaying %s bytes to %s:%s (TLS=%s)", f"{len(data):,}", host, port, secured)
        await asyncio.to_thread(send_frame, host, port, secured, data)
        await client.send_str("ok")
    except Exception as ex:  # noqa: BLE001 - the page shows the message
        log.warning("Upload relay failed: %s", ex)
        try:
            await client.send_str(f"error: {ex}")
        except ConnectionError:
            pass
    finally:
        await client.close()
    return client


# ── Thumbnails and library actions (samsungtvws) ─────────────────────────


def _tv_art(host: str):
    from samsungtvws import SamsungTVWS

    return SamsungTVWS(
        host=host,
        port=8002,
        token_file=str(TOKEN_FILE),
        name=TV_CLIENT_NAME,
    ).art()


def sync_thumbs(host: str) -> dict:
    import base64 as b64
    import io

    from PIL import Image

    art = _tv_art(host)
    available = art.available("MY-C0002")
    ids = [
        item["content_id"]
        for item in available
        if "content_id" in item and item["content_id"].startswith("MY")
    ]
    lines = [f"Found {len(ids)} custom photos on the TV."]
    thumbs: dict[str, str] = {}

    for cid in ids:
        try:
            # Per-item get_thumbnail only. get_thumbnail_list is rejected with
            # error -1 by several 2022-2025 firmwares ("unsupported request"),
            # and one failed batch call must not cost the whole library.
            raw = art.get_thumbnail(cid)
            if not raw:
                lines.append(f"empty thumbnail for {cid}")
                continue
            img = Image.open(io.BytesIO(raw)).convert("RGB")
            img.thumbnail((320, 180))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=80)
            thumbs[cid] = "data:image/jpeg;base64," + b64.b64encode(buf.getvalue()).decode("ascii")
            lines.append(f"pulled {cid}")
        except Exception as ex:  # noqa: BLE001 - one bad item must not stop the sync
            lines.append(f"failed {cid}: {ex}")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    THUMBS_FILE.write_text(
        "// Auto-generated by the Frame Art Manager add-on\n"
        f"window.FAM_PRELOADED_THUMBS = {json.dumps(thumbs)};\n"
        "(function () {\n"
        "  if (!window.FAM_PRELOADED_THUMBS) return;\n"
        "  for (const [cid, dataUrl] of Object.entries(window.FAM_PRELOADED_THUMBS)) {\n"
        "    try { localStorage.setItem('fam_thumb_' + cid, dataUrl); } catch (e) {}\n"
        "  }\n"
        "  console.log('Loaded ' + Object.keys(window.FAM_PRELOADED_THUMBS).length + ' TV thumbnails.');\n"
        "})();\n",
        encoding="utf-8",
    )
    return {"ok": True, "count": len(thumbs), "thumbs": thumbs, "log": "\n".join(lines)}


def show_on_tv(host: str, content_id: str) -> str:
    cid = content_id
    if cid.startswith("F"):
        cid = "MY_" + cid
    _tv_art(host).select_image(cid, show=True)
    return cid


# ── HTTP ─────────────────────────────────────────────────────────────────


def inject_config(html: str, ingress_path: str = "") -> str:
    base = (ingress_path.rstrip("/") + "/") if ingress_path else "/"
    cfg = json.dumps({"tvIp": TV_IP, "base": base})
    return html.replace("</head>", f"<script>window.FAM_ADDON = {cfg};</script>\n</head>", 1)


async def serve_index(request: web.Request) -> web.Response:
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    # Home Assistant tells the add-on which ingress prefix it used; handing that
    # to the page removes any guessing from relative URL construction.
    return web.Response(
        text=inject_config(html, request.headers.get("X-Ingress-Path", "")),
        content_type="text/html",
    )


async def serve_thumbs(_request: web.Request) -> web.Response:
    if THUMBS_FILE.exists():
        return web.FileResponse(THUMBS_FILE)
    return web.Response(
        text="window.FAM_PRELOADED_THUMBS = {};\n",
        content_type="application/javascript",
    )


async def handle_sync(request: web.Request) -> web.Response:
    try:
        host = tv_host(request.query.get("ip", ""))
        log.info("Thumbnail sync requested for %s", host)
        result = await asyncio.to_thread(sync_thumbs, host)
        log.info("Thumbnail sync finished: %s thumbnails", result.get("count", 0))
        return web.json_response(result)
    except Exception as ex:  # noqa: BLE001 - the page shows the message
        log.warning("Thumbnail sync failed: %s", ex)
        return web.json_response({"ok": False, "error": str(ex)}, status=502)


async def handle_show(request: web.Request) -> web.Response:
    content_id = request.query.get("id", "").strip()
    if not content_id:
        return web.json_response({"ok": False, "error": "Missing id"}, status=400)
    try:
        host = tv_host(request.query.get("ip", ""))
        cid = await asyncio.to_thread(show_on_tv, host, content_id)
        return web.json_response({"ok": True, "id": cid})
    except Exception as ex:  # noqa: BLE001
        log.warning("Show on TV failed: %s", ex)
        return web.json_response({"ok": False, "error": str(ex)}, status=502)


async def handle_health(_request: web.Request) -> web.Response:
    return web.json_response(
        {
            "ok": True,
            "tv_ip_configured": bool(TV_IP),
            "art_token": bool(read_token()),
            "thumbs_cache": THUMBS_FILE.exists(),
        }
    )


async def handle(request: web.Request) -> web.StreamResponse:
    """Single dispatch point so Ingress prefixes need no special casing."""
    path = INGRESS_PREFIX.sub("", request.path)
    tail = path.rstrip("/").lstrip("/")
    segment = tail.split("/")[-1] if tail else ""

    if request.headers.get("Upgrade", "").lower() == "websocket":
        if segment == "tv":
            return await handle_tv(request)
        if segment == "upload":
            return await handle_upload(request)
        raise web.HTTPBadRequest(text="unknown websocket endpoint")

    if segment in ("", "index.html"):
        return await serve_index(request)
    if segment == "thumbs_cache.js":
        return await serve_thumbs(request)
    if segment == "sync":
        return await handle_sync(request)
    if segment == "show":
        return await handle_show(request)
    if segment == "health":
        return await handle_health(request)
    raise web.HTTPNotFound()


def main() -> None:
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    if not TV_IP:
        log.warning("Option 'tv_ip' is empty — set it in the add-on configuration")

    app = web.Application(client_max_size=MAX_UPLOAD)
    app.router.add_route("*", "/{tail:.*}", handle)
    log.info("Frame Art Manager listening on 0.0.0.0:%s (tv_ip=%s)", PORT, TV_IP or "unset")
    web.run_app(app, host="0.0.0.0", port=PORT, print=None)


if __name__ == "__main__":
    main()
