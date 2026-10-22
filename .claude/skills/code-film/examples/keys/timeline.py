"""timeline.py: KEYS. A character plays Ode to Joy by hopping on a tablet piano.

Single source of truth for ui.html, scene.py, sound.py, check.py. Times in beats.
Each landing on a key IS a note: picture and sound come from the same list.
"""
import json

FPS = 30
BPM = 120
BEAT = 60.0 / BPM


def b(beats):
    return beats * BEAT


DURATION = b(28)                 # 14.0 s
FRAMES = round(DURATION * FPS)   # 420

UI_W, UI_H = 1920, 1080
SCREEN_W = 4.0
PANEL_GAP_PX = 0
SLAB_T = 0.004

QUALITY = {
    "preview": (480, 270, 8, 6),
    "draft":   (960, 540, 32, 1),
    "final":   (1920, 1080, 96, 1),
}

PANELS = ["screen"]
KEEP_PANEL = "screen"
START = "start"

# Ode to Joy (Beethoven, public domain): (land_beat, key). Takeoff = land - air beats.
MELODY = [
    (4, "E4"), (5, "E4"), (6, "F4"), (7, "G4"),
    (8, "G4"), (9, "F4"), (10, "E4"), (11, "D4"),
    (12, "C4"), (13, "C4"), (14, "D4"), (15, "E4"),
    (16, "E4"), (17.5, "D4"), (18, "D4"),
]
AIR = 0.6                         # beats in the air for a melody hop
FINALE_LAND = 21.0                # big hop up onto the screen, title + glissando
HOPS, _prev = [], 2.0
for (t, k) in MELODY:                      # a fast note gets a shorter hop (75 % of the gap)
    air = 1.2 if not HOPS else min(AIR, 0.75 * (t - _prev))   # first hop: long entrance
    HOPS.append((t - air, t, k))
    _prev = t
HOPS.append((19.5, FINALE_LAND, "title"))

HOP_MIN_H = 0.10
HOP_H_PER_M = 0.30
HOP_MAX_H = 0.40
MAX_HOP_SPEED = 3.0
CHAR_SCALE = 0.8

GLISS = (FINALE_LAND, 1.5)        # key light-wave + sound sweep: start beat, length in beats
TITLE = "PLAYED BY CODE"
SUBTITLE = "BLENDER  ·  PYTHON  ·  FFMPEG"
SYNC_BAND = (2000, 4000)          # check.py listens for the key-tap transient in this band

# camera beats
INTRO_END = 3.5                   # slow push-in ends
CRANE = (21.0, 26.5)              # crane up to the top-down hero shot

# (unused template knobs kept so shared scripts import cleanly)
PLAY_START, PLAY_END = 0, 0
POWER_DOWN = 99
FALL_START, FALL_STAGGER, FALL_DUR = 99, 0, 1


def presses():
    """Key presses = landings on [data-btn] targets: [(time_s, key)]."""
    return [(b(t1), tgt) for (_, t1, tgt) in HOPS if tgt not in ("start", "title")]


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
    if is_stale:
        for f in os.listdir(out_dir):
            if f.endswith(".png"):
                os.remove(os.path.join(out_dir, f))
    if not partial:
        open(stamp, "w").write(fp)
    return is_stale


def to_json():
    return json.dumps({
        "FPS": FPS, "BPM": BPM, "BEAT": BEAT, "DURATION": DURATION, "FRAMES": FRAMES,
        "UI_W": UI_W, "UI_H": UI_H, "PRESSES": presses(),
        "FINALE": b(FINALE_LAND), "GLISS": [b(GLISS[0]), b(GLISS[1])],
        "TITLE": TITLE, "SUBTITLE": SUBTITLE,
    })


if __name__ == "__main__":
    print(to_json())
