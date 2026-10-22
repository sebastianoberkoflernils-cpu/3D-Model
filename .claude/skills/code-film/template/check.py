"""check.py: QA before anyone watches the film.

  python check.py [preview|draft|final]

Writes qa/<quality>_sheet.jpg (every rendered frame, labelled), qa/<quality>_landings.jpg
(the frame of every landing, cropped around the character) and prints hard failures:
missing frames, black/blown frames, a character that is off-screen, audio length mismatch.
Look at both images every iteration. Exit code 1 if anything failed.
"""
import json, os, sys, wave
from PIL import Image, ImageDraw, ImageStat

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import timeline as T

q = sys.argv[1] if len(sys.argv) > 1 else "preview"
d = os.path.join(HERE, "frames", q)
qa = os.path.join(HERE, "qa")
os.makedirs(qa, exist_ok=True)
fails = []

files = sorted(f for f in os.listdir(d) if f.endswith(".png")) if os.path.isdir(d) else []
nums = [int(f[2:6]) for f in files]
every = T.QUALITY[q][3]
want = [f for f in range(1, T.FRAMES + 1) if (f - 1) % every == 0 or f == T.FRAMES]
miss = sorted(set(want) - set(nums))
if miss:
    fails.append(f"{len(miss)} frames missing, first: {miss[:8]}")

# brightness per frame: catches black frames, blown frames and sudden pops
lum = {}
for f, n in zip(files, nums):
    im = Image.open(os.path.join(d, f)).convert("L")
    lum[n] = ImageStat.Stat(im).mean[0]
for n, v in lum.items():
    if v < 4:
        fails.append(f"frame {n} is nearly black (mean {v:.1f})")
    if v > 235:
        fails.append(f"frame {n} is blown out (mean {v:.1f})")
seq = [lum[n] for n in sorted(lum)]
for i in range(1, len(seq)):
    if abs(seq[i] - seq[i - 1]) > 40 * max(1, every / 3):
        fails.append(f"brightness jump between frames {sorted(lum)[i - 1]} and {sorted(lum)[i]}")

# contact sheet
if files:
    cols = 6
    w0, h0 = Image.open(os.path.join(d, files[0])).size
    tw = 320
    th = round(h0 * tw / w0)
    step = max(1, len(files) // 36)
    pick = files[::step]
    sheet = Image.new("RGB", (cols * tw, ((len(pick) + cols - 1) // cols) * th), "black")
    for i, f in enumerate(pick):
        im = Image.open(os.path.join(d, f)).convert("RGB").resize((tw, th))
        ImageDraw.Draw(im).text((6, 4), f"{int(f[2:6])}  {(int(f[2:6]) - 1) / T.FPS:.2f}s", fill="yellow")
        sheet.paste(im, ((i % cols) * tw, (i // cols) * th))
    sheet.save(os.path.join(qa, f"{q}_sheet.jpg"), quality=88)

# landing frames (nearest rendered frame to each landing), full frame so framing is judged too
lands = [(T.b(t1), tgt) for (_, t1, tgt) in T.HOPS]
tiles = []
for t, tgt in lands:
    f = round(t * T.FPS) + 1
    near = min(nums, key=lambda n: abs(n - f)) if nums else None
    if near is None:
        continue
    im = Image.open(os.path.join(d, f"f_{near:04d}.png")).convert("RGB").resize((480, 270))
    ImageDraw.Draw(im).text((6, 4), f"land {tgt} @ {t:.2f}s (frame {near})", fill="yellow")
    tiles.append(im)
if tiles:
    sheet = Image.new("RGB", (960, 270 * ((len(tiles) + 1) // 2)), "black")
    for i, im in enumerate(tiles):
        sheet.paste(im, ((i % 2) * 480, (i // 2) * 270))
    sheet.save(os.path.join(qa, f"{q}_landings.jpg"), quality=88)

# audio
wav = os.path.join(HERE, "sound.wav")
if os.path.exists(wav):
    with wave.open(wav) as w:
        alen = w.getnframes() / w.getframerate()
    if abs(alen - T.DURATION) > 0.05:
        fails.append(f"sound.wav is {alen:.2f}s, film is {T.DURATION:.2f}s")
else:
    print("note: no sound.wav yet")

# layout sanity: every hop target exists and lies on a panel
L = json.load(open(os.path.join(HERE, "layout.json")))
for (_, _, tgt) in T.HOPS:
    x, y, w, h = L["targets"][tgt]
    if not any(px <= x + w / 2 <= px + pw and py <= y + h / 2 <= py + ph for px, py, pw, ph in L["panels"].values()):
        fails.append(f"hop target {tgt} is not on any panel (character would land in the void)")

# character framing + motion smoothness (screen_track.json is written by render.py)
st = os.path.join(qa, "screen_track.json")
if os.path.exists(st):
    tr = json.load(open(st))
    off = [r[0] for r in tr if not (0.03 < r[1] < 0.97 and 0.03 < r[2] < 0.97 and r[3] > 0)]
    if off:
        fails.append(f"character out of frame on {len(off)} frames: {off[:10]}")
    # too fast to read: character crosses > 12% of the frame in one frame
    sp = [((tr[i][1] - tr[i - 1][1]) ** 2 + (tr[i][2] - tr[i - 1][2]) ** 2) ** .5 for i in range(1, len(tr))]
    fast = [tr[i + 1][0] for i, v in enumerate(sp) if v > 0.12]
    if fast:
        fails.append(f"character moves > 12% of frame per frame (unreadable) at frames {fast[:10]}")
    # camera pops: sudden change of camera velocity (second difference of position, metres/frame^2)
    import math
    cam = [r[4:7] for r in tr]
    acc = [math.dist([cam[i + 1][k] - 2 * cam[i][k] + cam[i - 1][k] for k in range(3)], [0, 0, 0])
           for i in range(1, len(cam) - 1)]
    pops = [tr[i + 1][0] for i, a_ in enumerate(acc) if a_ > 0.01]
    if pops:
        fails.append(f"camera pops (accel > 0.01 m/frame^2) at frames {pops[:10]}")
    print(f"framing: character on screen in {len(tr) - len(off)}/{len(tr)} frames, "
          f"max screen speed {max(sp):.3f}/frame, max camera accel {max(acc):.4f}")

# audio sync: energy at the landing 'knock' frequency must peak at every landing
if os.path.exists(wav):
    import numpy as np
    from scipy.io import wavfile
    from scipy.signal import butter, sosfilt
    sr, x = wavfile.read(wav)
    x = x.mean(1) / 32768 if x.ndim > 1 else x / 32768
    # loudness: a silent or whisper-quiet track is a failure, not a style choice
    rms_db = 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-12)
    if rms_db < -30:
        fails.append(f"soundtrack is nearly silent (RMS {rms_db:.1f} dBFS, want about -20..-12)")
    print(f"audio level: RMS {rms_db:.1f} dBFS")
    band = list(getattr(T, "SYNC_BAND", (1250, 1450)))      # where the landing transient lives
    bp = sosfilt(butter(4, band, "bandpass", fs=sr, output="sos"), x)
    hop = sr // 1000                                       # 1 ms envelope
    e = np.convolve(bp ** 2, np.ones(5 * hop) / (5 * hop), "same")[::hop]
    # judge each landing locally (a global threshold breaks when music shares the band):
    # onset = steepest rise within +-100 ms; it must also be a real rise vs. 50-150 ms before
    worst = 0.0
    for (_, t1, tgt) in T.HOPS:
        i = int(T.b(t1) * 1000)
        win = e[max(0, i - 100):i + 100]
        onset = (max(0, i - 100) + int(np.argmax(np.diff(win)))) / 1000
        before = e[max(0, i - 150):max(1, i - 50)].mean()
        rise = win.max() / (before + 1e-12)
        if rise < 2:
            fails.append(f"no audible landing sound at {T.b(t1):.2f}s ({tgt}), rise x{rise:.1f}")
        worst = max(worst, abs(onset - T.b(t1)))
    if worst > 1.0 / T.FPS:
        fails.append(f"landing sound off by {worst * 1000:.0f} ms (> 1 frame)")
    print(f"audio sync: worst landing offset {worst * 1000:.0f} ms")

print(f"{len(files)} frames checked, mean brightness {sum(seq) / max(1, len(seq)):.1f}")
print(f"sheets: qa/{q}_sheet.jpg  qa/{q}_landings.jpg")
for f in fails:
    print("FAIL:", f)
sys.exit(1 if fails else 0)
