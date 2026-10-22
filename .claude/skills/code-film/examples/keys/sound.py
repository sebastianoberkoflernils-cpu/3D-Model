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


# ------------------------------------------------------------------ piano + band
NOTE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def midi(name):
    return 12 * (int(name[1]) + 1) + NOTE[name[0]]


def piano(m, dur=1.6, vel=1.0):
    """Additive piano: slightly inharmonic partials, highs decay faster, hammer thump."""
    t = t_arr(dur)
    f0 = hz(m)
    B = 0.0004                                            # string stiffness -> inharmonicity
    x = np.zeros_like(t)
    for n in range(1, 11):
        fn = n * f0 * np.sqrt(1 + B * n * n)
        if fn > SR / 2.2:
            break
        x += (0.9 ** n) / n ** 0.6 * np.sin(2 * np.pi * fn * t) * np.exp(-t * (1.6 + 0.9 * n))
    hammer = filt(rng.standard_normal(len(t)), "bandpass", [800, 3000]) * np.exp(-t * 90) * 0.25
    return (x + hammer) * np.minimum(1, t / 0.003) * vel


def tap():
    """Key-tap transient (the character's feet on glass): 2-4 kHz, what check.py listens for."""
    n = filt(rng.standard_normal(int(0.04 * SR)), "bandpass", [2200, 3800])
    return n * env(0.04, 0.0005, 0.008)


def pad(notes, dur):
    t = t_arr(dur)
    x = sum(np.sin(2 * np.pi * hz(m) * t + 0.3 * np.sin(2 * np.pi * 0.2 * t)) for m in notes)
    e = np.minimum(1, t / 0.4) * np.minimum(1, (dur - t) / 0.4).clip(0)
    return x * e / len(notes)


def bass(m, dur):
    t = t_arr(dur)
    return (np.sin(2 * np.pi * hz(m) * t) + 0.3 * np.sin(4 * np.pi * hz(m) * t)) * env(dur, 0.01, dur * 0.6)


def main():
    music = np.zeros((2, N))
    sfx = np.zeros((2, N))
    beat = T.BEAT
    melody_end = T.b(T.MELODY[-1][0]) + 2 * beat
    # harmony per 4-beat bar under the melody (bar 0 = count-in)
    chords = [(48, [60, 64, 67]), (48, [60, 64, 67]), (43, [59, 62, 67]), (48, [60, 64, 67]),
              (43, [59, 62, 67])]
    for i, (root, ch) in enumerate(chords):
        t0 = i * 4 * beat
        put(music, pad(ch, 4 * beat), t0, 0.10)
        if i == 0:
            continue
        put(music, bass(root, 2 * beat), t0, 0.30)
        put(music, bass(root + 7, 2 * beat), t0 + 2 * beat, 0.24)
        for k in range(4):
            put(music, kick() if k % 2 == 0 else snare() * 0.5, t0 + k * beat, 0.35 if k % 2 == 0 else 0.22)
        for k in range(8):
            put(music, hat(), t0 + k * beat / 2 + (0.05 * beat if k % 2 else 0), 0.05, 0.4)

    # melody: every landing is a note (same list the animation uses)
    for (t, name) in T.presses():
        put(sfx, piano(midi(name)), t, 0.55, (midi(name) - 64) / 12)
        put(sfx, tap(), t, 0.22)
    # takeoff: a tiny soft whoosh so hops read with eyes closed
    for (a, b_, tgt) in T.HOPS:
        put(sfx, filt(whoosh(0.18), "lowpass", 1500), T.b(a), 0.05)

    # finale: landing tap, glissando across all 15 white keys in sync with the light wave, big chord
    g0, gl = T.b(T.GLISS[0]), T.b(T.GLISS[1])
    put(sfx, tap(), T.b(T.FINALE_LAND), 0.3)
    whites = [n + o for o in "456" for n in "CDEFGAB"][:15]
    for i, name in enumerate(whites):
        put(sfx, piano(midi(name), 1.2, 0.6), g0 + gl * i / 15, 0.35, i / 7 - 1)
    for m in (48, 60, 64, 67, 72):
        put(sfx, piano(m, 3.5, 0.9), g0 + gl, 0.32)
    put(music, pad([60, 64, 67, 71], T.DURATION - g0), g0, 0.12)

    mix = filt(music, "lowpass", 9000) + sfx
    try:
        from pedalboard import Pedalboard, Reverb, Compressor, Limiter
        board = Pedalboard([Reverb(room_size=0.45, wet_level=0.18, dry_level=0.85),
                            Compressor(threshold_db=-18, ratio=2.5, attack_ms=10, release_ms=150),
                            Limiter(threshold_db=-1.0)])
        mix = board(mix.astype(np.float32), SR)
    except ImportError:
        print("pedalboard not installed: skipping reverb/compression")
    fade = int(0.8 * SR)
    mix[:, -fade:] *= np.linspace(1, 0, fade) ** 2
    mix = mix[:, :N]
    mix = mix / (np.max(np.abs(mix)) or 1.0) * 0.89
    wavfile.write(os.path.join(HERE, "sound.wav"), SR, (mix.T * 32767).astype(np.int16))
    print(f"sound.wav: {N / SR:.3f}s, {len(T.presses())} notes + glissando")


if __name__ == "__main__":
    main()
