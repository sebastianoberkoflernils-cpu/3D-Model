#!/usr/bin/env bash
# setup.sh: one-time environment for code-film. Creates a venv (default /opt/b3d) with
# bpy (Blender as a Python module), numpy, scipy, pillow, pedalboard, playwright.
# bpy wheels are tied to one Python version: bpy 5.1+ = Python 3.13, bpy 4.x = Python 3.11.
set -euo pipefail
VENV="${VENV:-/opt/b3d}"
PYV=$(python3 -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')
case "$PYV" in
  3.13) BPY="bpy>=5.1" ;;
  3.11) BPY="bpy>=4.2,<5" ;;
  *) echo "python3 is $PYV; bpy needs 3.13 (bpy 5.x) or 3.11 (bpy 4.x)."
     echo "Install one (e.g. 'uv python install 3.13') and re-run with PATH pointing to it,"
     echo "or install Blender and run renders with BLENDER=/path/to/blender ./film.sh"; exit 1 ;;
esac
python3 -m venv --system-site-packages "$VENV"
"$VENV/bin/pip" install -q "$BPY" numpy scipy pillow pedalboard "playwright>=1.40"
# Use a system Chromium if one exists (render_ui.py looks for it); else fetch Playwright's.
if ! ls /opt/pw-browsers/chromium >/dev/null 2>&1 && ! command -v chromium >/dev/null && ! command -v google-chrome >/dev/null; then
  "$VENV/bin/playwright" install chromium
fi
"$VENV/bin/python" -c "import bpy; print('bpy', bpy.app.version_string, 'ok')"
echo "PY=$VENV/bin/python"
