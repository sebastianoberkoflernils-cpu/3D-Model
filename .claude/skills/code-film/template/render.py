"""render.py: render frames (resumable).

  python render.py [preview|draft|final] [--frames 100-140] [--every N] [--force]
  blender -b -P render.py -- draft          (same, with a Blender install instead of pip bpy)

Skips frames that already exist, so a crash or a fix to frames 100-140 only costs those
frames. The UI texture is swapped to ui/f_####.png before each frame.
"""
import argparse, os, sys, time
import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import timeline as T
import scene


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("quality", nargs="?", default="preview", choices=list(T.QUALITY))
    ap.add_argument("--frames", default=None, help="e.g. 100-140")
    ap.add_argument("--every", type=int, default=None)
    ap.add_argument("--force", action="store_true")
    # works both as `python render.py ...` (pip bpy) and `blender -b -P render.py -- ...`
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
    every = a.every or T.QUALITY[a.quality][3]
    lo, hi = (map(int, a.frames.split("-")) if a.frames else (1, T.FRAMES))
    frames = [f for f in range(lo, hi + 1) if (f - 1) % every == 0 or f == T.FRAMES]

    out = os.path.join(HERE, "frames", a.quality)
    os.makedirs(out, exist_ok=True)
    if T.stale(out, ["timeline.py", "scene.py", "ui.html"], partial=bool(a.frames)):
        print("sources changed since these frames were rendered: old frames deleted")
    todo = [f for f in frames if a.force or not os.path.exists(os.path.join(out, f"f_{f:04d}.png"))]
    missing_ui = [f for f in todo if not os.path.exists(os.path.join(HERE, "ui", f"f_{f:04d}.png"))]
    if missing_ui:
        sys.exit(f"UI frames missing (run render_ui.py --every {every}): {missing_ui[:5]}...")

    sc = scene.build(a.quality)
    scene.screen_track(sc, os.path.join(HERE, "qa", "screen_track.json"))
    img = bpy.data.images["UI"]
    t_all = time.time()
    for i, f in enumerate(todo):
        t0 = time.time()
        sc.frame_set(f)
        img.filepath = os.path.join(HERE, "ui", f"f_{f:04d}.png")
        img.reload()
        sc.render.filepath = os.path.join(out, f"f_{f:04d}.png")
        bpy.ops.render.render(write_still=True)
        dt = time.time() - t0
        eta = (time.time() - t_all) / (i + 1) * (len(todo) - i - 1)
        print(f"frame {f}: {dt:.2f} s  ({i + 1}/{len(todo)}, eta {eta / 60:.1f} min)", flush=True)
    print(f"done: {len(todo)} frames in {(time.time() - t_all) / 60:.1f} min -> {out}")


if __name__ == "__main__":
    main()
