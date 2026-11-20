# -*- coding: utf-8 -*-
"""사주 사이트(Render)의 방문·무료사주·결제 숫자를 가져와 daily/site_stats.json 에 날짜별로 보관합니다.
(사이트가 다시 켜지면 숫자가 처음부터 세어지므로, 매일 여기에 모아 둡니다)"""
import os
import json
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
FILE = os.path.join(HERE, "site_stats.json")
URL = os.environ.get("SITE_URL", "https://saju-auto.onrender.com").rstrip("/") + "/api/kr/stats"

try:
    with urllib.request.urlopen(urllib.request.Request(URL, headers={"User-Agent": "saju-stats"}), timeout=60) as r:
        days = json.loads(r.read().decode("utf-8")).get("days", {})
except Exception as e:
    print("사이트 숫자 가져오기 실패:", e)
    raise SystemExit(0)

try:
    with open(FILE, encoding="utf-8") as f:
        saved = json.load(f)
except Exception:
    saved = {}

for day, d in days.items():
    old = saved.get(day, {})
    new = {}
    for k, v in d.items():
        if isinstance(v, dict):
            o = old.get(k, {})
            new[k] = {s: max(v.get(s, 0), o.get(s, 0)) for s in set(v) | set(o)}
        else:
            new[k] = max(v, old.get(k, 0))
    saved[day] = new

keep = sorted(saved)[-120:]
with open(FILE, "w", encoding="utf-8") as f:
    json.dump({k: saved[k] for k in keep}, f, ensure_ascii=False, indent=1)
for k in keep[-7:]:
    d = saved[k]
    print(k, "방문자 %s, 무료사주 %s, 결제시작 %s, 결제완료 %s, 들어온곳 %s" % (
        d.get("방문자", 0), d.get("무료사주", 0), d.get("결제시작", 0), d.get("결제완료", 0), d.get("들어온곳", {})))
