"""sound.py: synthesize the music + every sound effect from timeline.py.

  python sound.py            -> sound.wav (exactly DURATION long, 48 kHz stereo)

No samples, no AI: oscillators + noise + envelopes (numpy), filters (scipy),
reverb/compression (pedalboard, optional). SFX times come from the same HOPS the
animation uses, and the music grid is the same BPM, so everything lands together.
"""
import os, sys
import numpy as np
from scipy.signal import butter, sosfilt
from scipy.io import wavfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import timeline as T

SR = 48000
N = int(round(T.DURATION * SR))
rng = np.random.default_rng(7)          # fixed seed: same film, same sound, every run


def t_arr(dur):
    return np.arange(int(dur * SR)) / SR


def env(dur, a=0.002, d=0.2):
    t = t_arr(dur)
    return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / d)


def filt(x, kind, f):
    sos = butter(2, f, btype=kind, fs=SR, output="sos")
    return sosfilt(sos, x)


def put(bus, x, at, gain=1.0, pan=0.0):
    i = int(at * SR)
    if i >= N or i + len(x) <= 0:
        return
    x = x[: N - i] * gain
    bus[0, i:i + len(x)] += x * np.sqrt(0.5 * (1 - pan))
    bus[1, i:i + len(x)] += x * np.sqrt(0.5 * (1 + pan))


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


# ------------------------------------------------------------------ instruments
def kick():
    t = t_arr(0.4)
    f = 45 + 90 * np.exp(-t * 30)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(0.4, 0.001, 0.14)


def snare():
    n = filt(rng.standard_normal(int(0.25 * SR)), "bandpass", [1200, 5000]) * env(0.25, 0.001, 0.06)
    tone = np.sin(2 * np.pi * 185 * t_arr(0.25)) * env(0.25, 0.001, 0.04)
    return 0.6 * n + 0.5 * tone


def hat(open_=False):
    d = 0.18 if open_ else 0.05
    return filt(rng.standard_normal(int(d * SR)), "highpass", 7000) * env(d, 0.001, d / 3)


def keys(notes, dur):
    """Soft Rhodes-ish chord: sine + a little 2nd harmonic, slow attack, tremolo."""
    t = t_arr(dur)
    out = np.zeros_like(t)
    for m in notes:
        f = hz(m) * (1 + 0.0015 * rng.standard_normal())       # slight detune = warmth
        out += np.sin(2 * np.pi * f * t) + 0.25 * np.sin(4 * np.pi * f * t)
    trem = 1 + 0.12 * np.sin(2 * np.pi * 4.5 * t)
    e = np.minimum(1, t / 0.03) * np.exp(-t / (dur * 0.9))
    return out * trem * e / len(notes)


def glock(midi):
    t = t_arr(1.2)
    f = hz(midi)
    x = sum(a * np.sin(2 * np.pi * f * r * t) * np.exp(-t * k)
            for r, a, k in ((1, 1, 3), (2.76, .35, 9), (5.4, .15, 18)))
    return x * np.minimum(1, t / 0.002)


# ------------------------------------------------------------------ sound effects
def boing():
    t = t_arr(0.28)
    f = 220 + 520 * (1 - np.exp(-t * 18)) + 25 * np.sin(2 * np.pi * 22 * t)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(0.28, 0.004, 0.09)


def glass_knock():
    t = t_arr(0.35)
    x = sum(a * np.sin(2 * np.pi * 1350 * r * t) * np.exp(-t * k)
            for r, a, k in ((1, 1, 28), (2.32, .5, 40), (4.25, .25, 60)))
    click = filt(rng.standard_normal(len(t)), "highpass", 3000) * np.exp(-t * 300)
    return 0.7 * x + 0.4 * click


def click():
    return filt(rng.standard_normal(int(0.03 * SR)), "bandpass", [2000, 6000]) * env(0.03, 0.0005, 0.006)


def power_down():
    t = t_arr(0.9)
    f = 420 * np.exp(-t * 4) + 35
    saw = 2 * ((np.cumsum(f) / SR) % 1) - 1
    return filt(saw, "lowpass", 1800) * env(0.9, 0.005, 0.45)


def whoosh(dur=1.2):
    t = t_arr(dur)
    n = filt(rng.standard_normal(len(t)), "bandpass", [300, 2500])
    return n * np.sin(np.pi * t / dur) ** 2


# ------------------------------------------------------------------ score
def main():
    music = np.zeros((2, N))
    sfx = np.zeros((2, N))
    beat = T.BEAT
    bars = int(np.ceil(T.DURATION / (4 * beat)))
    prog = [[53, 57, 60, 64], [52, 55, 59, 62], [50, 53, 57, 60], [48, 52, 55, 59]]   # Fmaj7 Em7 Dm7 Cmaj7
    end = T.b(T.POWER_DOWN)                       # drums drop out when the panels power down
    for bar in range(bars):
        t0 = bar * 4 * beat
        put(music, keys(prog[bar % 4], 4 * beat), t0, 0.32, 0.0)
        for k in range(8):                        # swung 8th hats
            tk = t0 + k * beat / 2 + (0.06 * beat if k % 2 else 0)
            if tk < end:
                put(music, hat(open_=(k == 7)), tk, 0.10 if k % 2 else 0.16, 0.3)
        for k, inst in ((0, kick), (1, snare), (2, kick), (2.5, kick), (3, snare)):
            tk = t0 + k * beat
            if tk < end:
                put(music, inst(), tk, 0.55 if inst is kick else 0.35)
    # vinyl crackle
    for _ in range(int(T.DURATION * 9)):
        put(music, click() * rng.uniform(.1, .4), rng.uniform(0, T.DURATION), 0.25, rng.uniform(-1, 1))

    pent = [72, 74, 76, 79, 81, 84]              # each press plays the next note up
    for i, (t, name) in enumerate(T.presses()):
        put(sfx, glock(pent[i % len(pent)]), t, 0.35, 0.2)
        put(sfx, click(), t, 0.5)
    for (a, b_, tgt) in T.HOPS:
        put(sfx, boing(), T.b(a), 0.30, -0.1)
        put(sfx, glass_knock(), T.b(b_), 0.38, 0.1)
    falling = [p for p in T.PANELS if p != T.KEEP_PANEL]
    for i, _ in enumerate(falling):
        put(sfx, power_down(), T.b(T.POWER_DOWN) + 0.1 * i, 0.18, (i / max(1, len(falling) - 1)) * 1.6 - 0.8)
        put(sfx, whoosh(), T.b(T.FALL_START) + i * T.b(T.FALL_STAGGER), 0.10, 0.0)
    put(sfx, glock(84), T.b(T.FALL_START) + 1.5, 0.3)          # final sparkle
    put(sfx, glock(88), T.b(T.FALL_START) + 1.5 + beat / 2, 0.25)

    music = filt(music, "lowpass", 8500)          # lo-fi: dull the top end
    mix = music + sfx
    try:
        from pedalboard import Pedalboard, Reverb, Compressor, Limiter
        board = Pedalboard([Reverb(room_size=0.35, wet_level=0.14, dry_level=0.9),
                            Compressor(threshold_db=-16, ratio=3, attack_ms=8, release_ms=120),
                            Limiter(threshold_db=-1.0)])
        mix = board(mix.astype(np.float32), SR)
    except ImportError:
        print("pedalboard not installed: skipping reverb/compression")
    fade = int(0.6 * SR)
    mix[:, -fade:] *= np.linspace(1, 0, fade) ** 2
    mix[:, :int(0.01 * SR)] *= np.linspace(0, 1, int(0.01 * SR))
    mix = mix[:, :N]
    peak = np.max(np.abs(mix)) or 1.0
    mix = mix / peak * 0.89
    wavfile.write(os.path.join(HERE, "sound.wav"), SR, (mix.T * 32767).astype(np.int16))
    print(f"sound.wav: {N / SR:.3f}s, {len(T.HOPS)} hops, {len(T.presses())} presses")


if __name__ == "__main__":
    main()
