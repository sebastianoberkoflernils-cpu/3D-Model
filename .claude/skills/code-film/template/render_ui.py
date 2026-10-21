"""render_ui.py: measure ui.html into layout.json and render one UI texture per frame.

  python render_ui.py [--every N] [--force]

Frame f (1-based) shows time t = (f - 1) / FPS. Output: ui/f_0001.png ...
"""
import argparse, json, os, shutil, sys
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import timeline as T


def chromium_path():
    # Prefer a system Chromium so we never need `playwright install` (no network).
    for p in (os.environ.get("CHROMIUM"), "/opt/pw-browsers/chromium",
              shutil.which("chromium"), shutil.which("chromium-browser"), shutil.which("google-chrome")):
        if p and os.path.exists(p):
            return p
    return None  # fall back to Playwright's own download


def plan_check(lay):
    """Hops faster than MAX_HOP_SPEED (m/s) smear and outrun the camera: catch them before rendering."""
    S = T.SCREEN_W / T.UI_W
    c = lambda r: (r[0] + r[2] / 2, r[1] + r[3] / 2)
    prev, bad = c(lay["targets"][T.START]), []
    for (t0, t1, tgt) in T.HOPS:
        p = c(lay["targets"][tgt])
        dist = ((p[0] - prev[0]) ** 2 + (p[1] - prev[1]) ** 2) ** .5 * S
        speed = dist / max(1e-6, T.b(t1) - T.b(t0))
        if speed > T.MAX_HOP_SPEED:
            need = dist / T.MAX_HOP_SPEED / T.BEAT
            bad.append(f"-> {tgt}: {dist:.2f} m in {T.b(t1) - T.b(t0):.2f} s = {speed:.1f} m/s "
                       f"(needs >= {need:.2f} beats)")
        prev = p
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--every", type=int, default=1)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    out = os.path.join(HERE, "ui")
    os.makedirs(out, exist_ok=True)
    frames = [f for f in range(1, T.FRAMES + 1) if (f - 1) % a.every == 0 or f == T.FRAMES]
    if T.stale(out, ["timeline.py", "ui.html"], partial=False):
        print("ui.html/timeline.py changed since the last UI render: old UI frames deleted")

    with sync_playwright() as p:
        br = p.chromium.launch(executable_path=chromium_path())
        pg = br.new_page(viewport={"width": T.UI_W, "height": T.UI_H}, device_scale_factor=1)
        pg.add_init_script(f"window.TL = {T.to_json()};")
        pg.goto("file://" + os.path.join(HERE, "ui.html"))
        pg.evaluate("document.fonts.ready")
        pg.evaluate("render(-1)")
        lay = pg.evaluate("layout()")
        missing = [n for (_, _, n) in T.HOPS if n not in lay["targets"]] + \
                  [n for n in T.PANELS if n not in lay["panels"]] + \
                  ([T.START] if T.START not in lay["targets"] else [])
        if missing:
            sys.exit(f"ui.html is missing targets/panels used by timeline.py: {missing}")
        too_fast = plan_check(lay)
        if too_fast and not os.environ.get("ALLOW_FAST"):
            sys.exit("timeline.py: hops too fast to read (give them more beats, or ALLOW_FAST=1):\n  "
                     + "\n  ".join(too_fast))
        with open(os.path.join(HERE, "layout.json"), "w") as fh:
            json.dump(lay, fh, indent=1)
        done = 0
        for f in frames:
            path = os.path.join(out, f"f_{f:04d}.png")
            if os.path.exists(path) and not a.force:
                continue
            pg.evaluate(f"render({(f - 1) / T.FPS})")
            pg.screenshot(path=path)
            done += 1
        br.close()
    print(f"layout.json written; {done} UI frames rendered to ui/")


if __name__ == "__main__":
    main()
