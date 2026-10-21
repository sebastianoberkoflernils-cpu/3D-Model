"""timeline.py: the single source of truth for the film.

Every other script (ui.html via render_ui.py, scene.py, sound.py, check.py) reads
this file. Change a number here, re-run the pipeline, and picture + sound stay in sync.

Times are written in BEATS so every hop lands on the music. b(x) converts to seconds.
Positions are never typed in by hand: targets are names of elements in ui.html
([data-btn] / [data-spot]); render_ui.py measures them into layout.json.
"""
import json

FPS = 30
BPM = 120
BEAT = 60.0 / BPM


def b(beats):
    return beats * BEAT


DURATION = b(18)                 # 9.0 s
FRAMES = round(DURATION * FPS)   # 270

# UI texture (the fake app) in pixels, and its size in the 3D world in metres.
UI_W, UI_H = 1920, 1080
SCREEN_W = 4.0                   # metres; height follows the aspect ratio
PANEL_GAP_PX = 6                 # inset per panel so seams read as separate slabs
SLAB_T = 0.035                   # slab thickness (m)

# Render quality presets: (width, height, samples, every_nth_frame)
QUALITY = {
    "preview": (480, 270, 8, 6),
    "draft":   (960, 540, 24, 1),
    "final":   (1920, 1080, 96, 1),
}

# Panels of the UI that become separate 3D slabs (ids of [data-panel] in ui.html).
PANELS = ["menubar", "toolbar", "project", "comp", "effects", "timeline"]
KEEP_PANEL = "comp"              # the one that survives the power-down

# Character starts here (a [data-spot] in ui.html).
START = "start"

# HOPS: (takeoff_beat, land_beat, target). Landing on a [data-btn] presses it.
HOPS = [
    (1.0, 2.0, "Type"),         # long first hop off the project panel
    (3.5, 4.0, "Rect"),
    (5.5, 6.0, "Pen"),
    (7.5, 8.0, "Glow"),
    (9.5, 10.0, "Play"),
    (10.75, 12.0, "land"),        # big hop down into the comp viewer
    (14.5, 15.0, "land"),        # celebration hops in place
    (15.5, 16.0, "land"),
]

HOP_MIN_H = 0.10                 # metres, apex height for tiny hops
HOP_H_PER_M = 0.30               # extra apex height per metre travelled
HOP_MAX_H = 0.32                 # cap so the camera can keep the apex in frame
MAX_HOP_SPEED = 3.0              # m/s; render_ui.py refuses faster hops (readability)
CHAR_SCALE = 0.8                 # character size vs. the buttons (keep presses visible)

# Comp (title card) events driven by button presses, in beats.
PLAY_START, PLAY_END = 10.0, 12.0       # playhead ride after "Play"
POWER_DOWN = 12.5                        # panels flicker off from here
FALL_START, FALL_STAGGER, FALL_DUR = 13.0, 0.35, 3.0

TITLE = "MADE WITH CODE"
SUBTITLE = "BLENDER  ·  PYTHON  ·  FFMPEG"


def presses():
    """Button presses = landings on [data-btn] targets: [(time_s, name)]."""
    spots = {"land", "start"}
    return [(b(t1), tgt) for (_, t1, tgt) in HOPS if tgt not in spots]


def fingerprint(*names):
    """Hash of source files: frames rendered from other sources are stale."""
    import hashlib, os
    h = hashlib.sha1()
    here = os.path.dirname(os.path.abspath(__file__))
    for n in names:
        p = os.path.join(here, n)
        if os.path.exists(p):
            h.update(open(p, "rb").read())
    return h.hexdigest()[:12]


def stale(out_dir, names, partial):
    """If out_dir holds frames made from different sources, delete them and return True.
    A partial (--frames) re-render never wipes, so you can patch a range on purpose."""
    import os
    os.makedirs(out_dir, exist_ok=True)
    stamp, fp = os.path.join(out_dir, ".stamp"), fingerprint(*names)
    old = open(stamp).read().strip() if os.path.exists(stamp) else None
    is_stale = old is not None and old != fp and not partial
    if is_stale:                                   # wipe, so no stale frame can survive
        for f in os.listdir(out_dir):
            if f.endswith(".png"):
                os.remove(os.path.join(out_dir, f))
    if not partial:
        open(stamp, "w").write(fp)
    return is_stale


def to_json():
    return json.dumps({
        "FPS": FPS, "BPM": BPM, "BEAT": BEAT, "DURATION": DURATION, "FRAMES": FRAMES,
        "UI_W": UI_W, "UI_H": UI_H, "PANELS": PANELS, "KEEP_PANEL": KEEP_PANEL,
        "PRESSES": presses(), "PLAY": [b(PLAY_START), b(PLAY_END)],
        "POWER_DOWN": b(POWER_DOWN),
        "FALL": [b(FALL_START), b(FALL_STAGGER), b(FALL_DUR)],
        "TITLE": TITLE, "SUBTITLE": SUBTITLE,
    })


if __name__ == "__main__":
    print(to_json())
