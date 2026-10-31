#!/usr/bin/env bash
# Copies the canonical standalone app into the add-on's static directory.
# The two copies must stay byte-identical; CI enforces it.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
src="$here/webapp/frame-art-manager.html"
dst="$here/frame_art_manager/app/static/index.html"
cp "$src" "$dst"
echo "synced: webapp/frame-art-manager.html -> frame_art_manager/app/static/index.html"
