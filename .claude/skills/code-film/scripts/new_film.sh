#!/usr/bin/env bash
# new_film.sh <dir>: copy the working template film into <dir>.
set -euo pipefail
[[ $# -eq 1 ]] || { echo "usage: new_film.sh <dir>"; exit 1; }
SRC="$(cd "$(dirname "$0")/../template" && pwd)"
mkdir -p "$1"
for f in timeline.py ui.html render_ui.py scene.py render.py sound.py check.py film.sh; do
  cp "$SRC/$f" "$1/"
done
chmod +x "$1/film.sh"
echo "new film in $1 — edit timeline.py + ui.html, then: PY=<venv python> $1/film.sh preview"
