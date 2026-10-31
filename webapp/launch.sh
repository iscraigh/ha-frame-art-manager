#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

PY_BIN="python3"
[ -f "$DIR/.venv/bin/python" ] && PY_BIN="$DIR/.venv/bin/python"

if ! pgrep -f "python.*relay.py" > /dev/null; then
    nohup "$PY_BIN" "$DIR/relay.py" > /tmp/frame-art-relay.log 2>&1 &
fi

if ! pgrep -f "python.*thumb_server.py" > /dev/null; then
    nohup "$PY_BIN" "$DIR/thumb_server.py" > /tmp/frame-art-thumbs.log 2>&1 &
fi

sleep 1
xdg-open "$DIR/frame-art-manager.html"
