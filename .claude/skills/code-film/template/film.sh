#!/usr/bin/env bash
# film.sh: the whole pipeline in order.   ./film.sh [preview|draft|final] [--force]
#   PY=python with bpy+numpy+scipy+pillow+playwright (default: python3)
#   BLENDER=/path/to/blender  -> render with a Blender install instead of pip bpy
set -euo pipefail
cd "$(dirname "$0")"
Q="${1:-preview}"; FORCE="${2:-}"
PY="${PY:-python3}"
read -r FPS EVERY < <($PY -c "import timeline as T; print(T.FPS, T.QUALITY['$Q'][3])")

echo "== 1/5 UI frames + layout ($Q, every $EVERY)"
$PY render_ui.py --every "$EVERY" $FORCE
echo "== 2/5 sound"
$PY sound.py
echo "== 3/5 3D render"
if [[ -n "${BLENDER:-}" ]]; then "$BLENDER" -b --python-exit-code 1 -P render.py -- "$Q" $FORCE
else $PY render.py "$Q" $FORCE; fi
echo "== 4/5 QA"
$PY check.py "$Q" || { echo "QA failed: fix before encoding (or look at qa/*.jpg)"; exit 1; }
if [[ "$Q" == "preview" ]]; then
  # preview = every Nth frame at low quality: for QA sheets only. Encoding it makes a choppy,
  # noisy video that looks broken, so never hand it to anyone as "the film".
  echo "preview OK -> look at qa/preview_sheet.jpg + qa/preview_landings.jpg; deliver only draft/final"
  exit 0
fi
echo "== 5/5 encode"
# yuv420p is required: PNG input otherwise becomes yuv444, which QuickTime/phones/browsers won't play
ffmpeg -v error -y -framerate "$(python3 -c "print($FPS/$EVERY)")" -pattern_type glob -i "frames/$Q/f_*.png" \
  -i sound.wav -r "$FPS" -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -movflags +faststart -shortest "film_$Q.mp4"
ffprobe -v error -show_entries format=duration,size -of default=nw=1 "film_$Q.mp4"
echo "-> film_$Q.mp4"
