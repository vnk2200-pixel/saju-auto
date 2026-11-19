# -*- coding: utf-8 -*-
"""
유튜브 쇼츠에 직접 올릴 때 쓸 제목·설명을 out/youtube.txt 로 만듭니다.
(유튜브는 개인 프로그램으로 자동 업로드하면 '비공개'로 잠기므로, 영상은 대표님이 폰 앱으로 올립니다)

매일 아래 주소에서 최신 내용을 볼 수 있습니다.
  글:   https://raw.githubusercontent.com/vnk2200-pixel/saju-auto/daily-output/youtube.txt
  영상: https://raw.githubusercontent.com/vnk2200-pixel/saju-auto/daily-output/video.mp4
"""

import os
import json

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "out")

with open(os.path.join(OUT, "post.json"), encoding="utf-8") as f:
    post = json.load(f)

hook = post.get("hook", "").strip()
title = (hook + " #shorts")[:100]

caption = post.get("caption", "").strip()
tags = [t for t in post.get("hashtags", []) if t and t != "#shorts"][:8]
description = (caption + "\n\n" + " ".join(["#shorts"] + tags)).strip()[:4800]

text = (
    "■ 오늘 날짜: %s\n\n"
    "■ 제목 (그대로 복사)\n%s\n\n"
    "■ 설명 (그대로 복사)\n%s\n\n"
    "■ 올리는 방법\n"
    "1. 위 '영상' 주소에서 video.mp4 를 폰에 저장\n"
    "2. 유튜브 앱 + 버튼 > 쇼츠 > 저장한 영상 선택\n"
    "3. 제목·설명 붙여 넣고 업로드\n"
    "※ 일주일에 2~3번은 브루(Vrew)로 대표님 목소리 한마디를 얹으면 더 좋아요.\n"
) % (post.get("date", ""), title, description)

with open(os.path.join(OUT, "youtube.txt"), "w", encoding="utf-8") as f:
    f.write(text)
print(text)
