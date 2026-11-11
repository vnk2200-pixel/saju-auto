# -*- coding: utf-8 -*-
"""
잔잔한 배경 음악을 직접 만들어 저장합니다 (저작권 걱정 없는 자체 제작 음원).
한 번만 실행해서 daily/music/*.m4a 를 만들어 두면 됩니다.
"""

import os
import subprocess
import numpy as np

SR = 44100
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "music")

A4 = 440.0


def hz(n):  # MIDI 번호 -> 주파수
    return A4 * 2 ** ((n - 69) / 12.0)


def pad(freq, dur, rnd):
    t = np.arange(int(SR * dur)) / SR
    detune = 1 + rnd.uniform(-0.002, 0.002)
    w = (np.sin(2 * np.pi * freq * t) * 0.6 +
         np.sin(2 * np.pi * freq * 2.0 * detune * t) * 0.18 +
         np.sin(2 * np.pi * freq * 0.5 * t) * 0.25)
    w *= 1 + 0.08 * np.sin(2 * np.pi * rnd.uniform(0.15, 0.35) * t)  # 천천히 숨 쉬는 느낌
    att, rel = min(1.6, dur / 3), min(2.2, dur / 2)
    env = np.ones_like(t)
    a = int(SR * att)
    r = int(SR * rel)
    env[:a] = np.linspace(0, 1, a) ** 2
    env[-r:] = np.linspace(1, 0, r) ** 2
    return w * env


def bell(freq, dur):
    t = np.arange(int(SR * dur)) / SR
    w = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(2 * np.pi * freq * 3.01 * t)
    return w * np.exp(-t * 2.2) * 0.35


def reverb(x):
    y = x.copy()
    for d, g in [(0.113, 0.35), (0.197, 0.28), (0.293, 0.22), (0.41, 0.16), (0.57, 0.11), (0.79, 0.07)]:
        n = int(SR * d)
        y[n:] += x[:-n] * g
    return y


# 조성별 4화음 진행 (MIDI 근음 + 화음 구성음)
PROGRESSIONS = [
    [(57, [0, 3, 7]), (53, [0, 4, 7]), (48, [0, 4, 7]), (55, [0, 4, 7])],   # Am F C G
    [(48, [0, 4, 7, 11]), (57, [0, 3, 7]), (53, [0, 4, 7, 11]), (55, [0, 4, 7])],  # Cmaj7 Am Fmaj7 G
    [(50, [0, 3, 7]), (46, [0, 4, 7]), (53, [0, 4, 7]), (48, [0, 4, 7])],   # Dm Bb F C
    [(52, [0, 3, 7]), (48, [0, 4, 7]), (55, [0, 4, 7]), (50, [0, 4, 7])],   # Em C G D
    [(53, [0, 4, 7, 11]), (55, [0, 4, 7]), (52, [0, 3, 7]), (57, [0, 3, 7])],  # Fmaj7 G Em Am
    [(55, [0, 4, 7]), (52, [0, 3, 7]), (48, [0, 4, 7]), (50, [0, 4, 7])],   # G Em C D
    [(45, [0, 3, 7, 10]), (50, [0, 3, 7]), (55, [0, 4, 7]), (48, [0, 4, 7, 11])],  # Am7 Dm G Cmaj7
    [(51, [0, 4, 7]), (48, [0, 3, 7]), (56, [0, 4, 7]), (58, [0, 4, 7])],   # Eb Cm Ab Bb
]


def track(i, length=40.0):
    rnd = np.random.RandomState(100 + i)
    prog = PROGRESSIONS[i % len(PROGRESSIONS)]
    chord_dur = 5.0
    out = np.zeros(int(SR * (length + 4)))
    pos, k = 0.0, 0
    while pos < length:
        root, iv = prog[k % len(prog)]
        for j, s in enumerate(iv):
            note = pad(hz(root + s), chord_dur + 1.5, rnd) * (0.22 if j else 0.3)
            a = int(SR * pos)
            out[a:a + len(note)] += note[: len(out) - a]
        # 가끔 맑은 종소리 멜로디
        for b in range(2):
            if rnd.rand() < 0.7:
                n = root + 12 + rnd.choice(iv) + (12 if rnd.rand() < 0.4 else 0)
                bpos = pos + rnd.uniform(0.5, chord_dur - 1)
                bl = bell(hz(n), 3.0)
                a = int(SR * bpos)
                out[a:a + len(bl)] += bl[: len(out) - a]
        pos += chord_dur
        k += 1
    out = reverb(out)[: int(SR * length)]
    fade = int(SR * 2.5)
    out[:int(SR * 1.0)] *= np.linspace(0, 1, int(SR * 1.0))
    out[-fade:] *= np.linspace(1, 0, fade)
    out = out / (np.max(np.abs(out)) + 1e-9) * 0.5
    return out


def save(x, path):
    pcm = (x * 32767).astype("<i2").tobytes()
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "s16le", "-ar", str(SR), "-ac", "1", "-i", "-",
                    "-c:a", "aac", "-b:a", "96k", path], input=pcm, check=True)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for i in range(len(PROGRESSIONS)):
        p = os.path.join(OUT, "calm_%02d.m4a" % (i + 1))
        save(track(i), p)
        print("saved", p)
