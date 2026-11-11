# -*- coding: utf-8 -*-
"""오늘 만든 글을 daily/history.json 에 기록합니다 (다음 날 겹침 점검용)."""

import os
import json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HISTORY = os.path.join(HERE, "history.json")

with open(os.path.join(ROOT, "out", "post.json"), encoding="utf-8") as f:
    post = json.load(f)

try:
    with open(HISTORY, encoding="utf-8") as f:
        history = json.load(f)
except Exception:
    history = []

history = [h for h in history if h.get("date") != post["date"]]
history.append({k: post.get(k) for k in ("date", "hook", "slides", "format", "theme", "style", "source", "day_name")})
history = history[-200:]

with open(HISTORY, "w", encoding="utf-8") as f:
    json.dump(history, f, ensure_ascii=False, indent=1)
print("history:", len(history), "posts")
