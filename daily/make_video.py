# -*- coding: utf-8 -*-
"""
out/post.json 을 읽어 세로 영상(1080x1920, 약 20~25초)과 표지 이미지를 만듭니다.
- 오늘 일진의 오행 색으로 배경을 칠하고, 은은한 빛이 천천히 움직입니다.
- 문장이 한 줄씩 부드럽게 나타났다 사라집니다.
- daily/music/ 의 자체 제작 잔잔한 음악을 날짜마다 바꿔 깝니다.
결과: out/video.mp4, out/cover.jpg
"""

import os
import sys
import json
import glob
import math
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "out")
W, H, FPS = 1080, 1920, 30

# 오행별 배경색 (위, 아래) - 목 화 토 금 수
PALETTES = [
    ((14, 46, 38), (6, 20, 18)),      # 목: 깊은 숲
    ((70, 18, 32), (24, 6, 14)),      # 화: 와인빛
    ((62, 44, 22), (22, 15, 8)),      # 토: 호박색
    ((40, 40, 58), (12, 12, 22)),     # 금: 은빛 남색
    ((14, 28, 64), (5, 9, 24)),       # 수: 밤바다
]
GLOW = [(120, 220, 170), (255, 150, 160), (240, 200, 120), (220, 220, 255), (130, 180, 255)]


def find_font(names, want="KR"):
    for pattern in names:
        for path in glob.glob(pattern):
            for idx in range(10):
                try:
                    f = ImageFont.truetype(path, 40, index=idx)
                except Exception:
                    break
                if want in " ".join(f.getname()):
                    return path, idx
    raise SystemExit("한글 글꼴을 찾지 못했습니다 (fonts-noto-cjk 설치 필요)")


SANS = find_font(["/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
                  "/usr/share/fonts/**/NotoSansCJK*Bold*.tt*"])
SERIF = find_font(["/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
                   "/usr/share/fonts/**/NotoSerifCJK*Bold*.tt*"])
LIGHT = find_font(["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                   "/usr/share/fonts/**/NotoSansCJK*Regular*.tt*"])


def font(spec, size):
    return ImageFont.truetype(spec[0], size, index=spec[1])


def wrap(draw, text, fnt, width):
    """한국어는 띄어쓰기 단위로 줄바꿈"""
    words, lines, cur = text.split(" "), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=fnt) <= width or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def text_layer(text, fnt, color, max_w, center_y, line_gap=1.35, shadow=True):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    lines = wrap(d, text, fnt, max_w)
    lh = int(fnt.size * line_gap)
    y = center_y - lh * len(lines) // 2
    if shadow:
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(sh)
        yy = y
        for ln in lines:
            x = (W - sd.textlength(ln, font=fnt)) / 2
            sd.text((x, yy + 4), ln, font=fnt, fill=(0, 0, 0, 170))
            yy += lh
        img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(8)))
        d = ImageDraw.Draw(img)
    for ln in lines:
        x = (W - d.textlength(ln, font=fnt)) / 2
        d.text((x, y), ln, font=fnt, fill=color)
        y += lh
    return np.asarray(img).astype(np.float32) / 255.0


def background(el):
    top, bot = PALETTES[el % 5]
    t = np.linspace(0, 1, H)[:, None]
    grad = np.zeros((H, W, 3), np.float32)
    for c in range(3):
        grad[:, :, c] = (top[c] * (1 - t) + bot[c] * t) / 255.0
    # 작은 별빛
    rnd = np.random.RandomState(7 + el)
    stars = Image.new("L", (W, H), 0)
    sd = ImageDraw.Draw(stars)
    for _ in range(160):
        x, y, r = rnd.randint(0, W), rnd.randint(0, H), rnd.choice([1, 1, 2, 2, 3])
        sd.ellipse((x - r, y - r, x + r, y + r), fill=int(rnd.randint(60, 200)))
    stars = np.asarray(stars.filter(ImageFilter.GaussianBlur(0.8))).astype(np.float32)[:, :, None] / 255.0
    return grad, stars


def glow_field(el, t):
    """천천히 움직이는 둥근 빛 3개 (작게 그려서 키움 - 빠름)"""
    sw, shh = W // 8, H // 8
    yy, xx = np.mgrid[0:shh, 0:sw].astype(np.float32)
    acc = np.zeros((shh, sw), np.float32)
    for i, (cx, cy, rad, sp) in enumerate([(0.25, 0.25, 0.35, 0.05), (0.8, 0.55, 0.4, 0.04), (0.4, 0.85, 0.3, 0.06)]):
        px = (cx + 0.08 * math.sin(t * sp * 6 + i)) * sw
        py = (cy + 0.06 * math.cos(t * sp * 5 + i * 2)) * shh
        r = rad * sw
        acc += np.exp(-(((xx - px) ** 2 + (yy - py) ** 2) / (2 * r * r)))
    acc = np.asarray(Image.fromarray((np.clip(acc, 0, 1) * 255).astype(np.uint8)).resize((W, H), Image.BILINEAR)).astype(np.float32) / 255.0
    col = np.array(GLOW[el % 5], np.float32) / 255.0
    return acc[:, :, None] * col * 0.22


def over(base, layer, alpha=1.0):
    if alpha <= 0:
        return base
    a = layer[:, :, 3:4] * alpha
    return base * (1 - a) + layer[:, :, :3] * a


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def main():
    with open(os.path.join(OUT, "post.json"), encoding="utf-8") as f:
        post = json.load(f)
    el = int(post.get("day_element", 4))
    y, m, d = [int(v) for v in post["date"].split("-")]
    import datetime
    wd = "월화수목금토일"[datetime.date(y, m, d).weekday()]

    grad, stars = background(el)
    label = text_layer("오늘의 사주  ·  %d월 %d일 (%s)  ·  %s" % (m, d, wd, post.get("day_name", "")),
                       font(LIGHT, 38), (235, 225, 210, 255), 980, 250, shadow=False)
    hook = text_layer(post["hook"], font(SERIF, 78), (255, 240, 215, 255), 920, 470)
    slides = [s for s in post["slides"]]
    cta_text = slides.pop() if ("프로필" in slides[-1] or "무료" in slides[-1]) else "프로필 링크에서 내 사주 무료로 확인"
    slide_layers = [text_layer(s, font(SANS, 66), (255, 255, 255, 255), 900, 1080) for s in slides]
    cta = text_layer(cta_text, font(SANS, 62), (255, 226, 160, 255), 900, 1080)
    cta_sub = text_layer("▼  프로필 링크", font(LIGHT, 44), (235, 225, 210, 255), 900, 1300, shadow=False)

    INTRO, PER, OUTRO, FADE = 2.4, 3.1, 3.6, 0.45
    total = INTRO + PER * len(slide_layers) + OUTRO
    n = int(total * FPS)

    # 음악: 날짜마다 다른 곡
    tracks = sorted(glob.glob(os.path.join(HERE, "music", "*.m4a")))
    track = tracks[(datetime.date(y, m, d).toordinal()) % len(tracks)] if tracks else None

    video = os.path.join(OUT, "video.mp4")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H),
           "-r", str(FPS), "-i", "-"]
    if track:
        cmd += ["-i", track, "-filter_complex",
                "[1:a]atrim=0:%.2f,afade=t=in:st=0:d=1,afade=t=out:st=%.2f:d=2.2,volume=0.9[a]" % (total, total - 2.2),
                "-map", "0:v", "-map", "[a]", "-c:a", "aac", "-b:a", "128k"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            "-t", "%.2f" % total, video]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    cover_frame = None
    for i in range(n):
        t = i / FPS
        frame = grad + glow_field(el, t)
        tw = 0.55 + 0.45 * math.sin(t * 1.3)
        frame = frame + stars * (0.35 + 0.25 * tw)
        frame = over(frame, label, ease(t / 0.8))
        frame = over(frame, hook, ease((t - 0.2) / 0.9))
        if t >= INTRO:
            k = int((t - INTRO) // PER)
            local = (t - INTRO) - k * PER
            if k < len(slide_layers):
                a = ease(local / FADE) * (1 - ease((local - (PER - FADE)) / FADE))
                frame = over(frame, slide_layers[k], a)
            else:
                lt = t - INTRO - PER * len(slide_layers)
                frame = over(frame, cta, ease(lt / FADE))
                frame = over(frame, cta_sub, ease((lt - 0.6) / FADE) * (0.75 + 0.25 * math.sin(lt * 4)))
        out = (np.clip(frame, 0, 1) * 255).astype(np.uint8)
        if abs(t - (INTRO + PER * 0.5)) < 0.5 / FPS:
            cover_frame = out
        proc.stdin.write(out.tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit("ffmpeg 실패")
    Image.fromarray(cover_frame if cover_frame is not None else out).save(os.path.join(OUT, "cover.jpg"), quality=90)
    print("video:", video, "%.1fs" % total, "music:", os.path.basename(track) if track else "none")


if __name__ == "__main__":
    main()
