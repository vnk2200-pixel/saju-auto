# -*- coding: utf-8 -*-
"""
오늘 만든 영상(out/video.mp4)을 페이스북 페이지와 인스타그램(릴스)에 자동으로 올립니다.

필요한 것 (GitHub 금고):
  META_TOKEN : 비즈니스 설정 > 시스템 사용자(saju-bot)에서 만든 '만료 없음' 토큰
환경변수:
  VIDEO_URL  : 누구나 받을 수 있는 영상 주소 (워크플로가 daily-output 공간 주소를 넣어 줌)

- 같은 날 이미 올렸으면(daily/posted.json 기록) 다시 올리지 않습니다.
- 한 곳이 실패해도 다른 곳은 계속 올립니다. 결과는 out/posted.json 에 남깁니다.
- 토큰이나 고유번호는 화면 기록(로그)에 출력하지 않습니다.
"""

import os
import sys
import json
import time
import urllib.parse
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "out")
POSTED = os.path.join(HERE, "posted.json")

TOKEN = os.environ.get("META_TOKEN", "").strip()
VIDEO_URL = os.environ.get("VIDEO_URL", "").strip()
GRAPH = "https://graph.facebook.com/v23.0"
PAGE_NAME = os.environ.get("META_PAGE_NAME", "연애와 돈의 행복")


class MetaError(Exception):
    pass


def call(method, path, params=None, token=None, base=GRAPH, timeout=120):
    params = dict(params or {})
    params["access_token"] = token or TOKEN
    url = base + path
    data = None
    if method == "GET":
        url += "?" + urllib.parse.urlencode(params)
    else:
        data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            err = json.loads(body).get("error", {})
            msg = "%s (code %s/%s)" % (err.get("message", ""), err.get("code"), err.get("error_subcode"))
        except Exception:
            msg = body[:200]
        raise MetaError("HTTP %s: %s" % (e.code, msg))


def find_page():
    pages = call("GET", "/me/accounts", {"fields": "id,name,access_token,instagram_business_account"}).get("data", [])
    if not pages:
        raise MetaError("토큰으로 볼 수 있는 페이스북 페이지가 없습니다 (시스템 사용자에 페이지 할당 확인)")
    page = next((p for p in pages if p.get("name") == PAGE_NAME), pages[0])
    ig = (page.get("instagram_business_account") or {}).get("id")
    if not ig:
        info = call("GET", "/" + page["id"], {"fields": "instagram_business_account"}, token=page.get("access_token"))
        ig = (info.get("instagram_business_account") or {}).get("id")
    print("page:", page.get("name"), "| instagram linked:", bool(ig))
    return page, ig


def caption_of(post):
    tags = " ".join(post.get("hashtags", []))
    return (post.get("caption", "").strip() + "\n\n" + tags).strip()[:2100]


def post_facebook(page, post):
    res = call("POST", "/%s/videos" % page["id"], {
        "file_url": VIDEO_URL,
        "title": post.get("hook", "")[:90],
        "description": caption_of(post),
        "published": "true",
    }, token=page.get("access_token") or TOKEN, base="https://graph-video.facebook.com/v23.0", timeout=300)
    return res.get("id")


def post_instagram(ig, post):
    create = call("POST", "/%s/media" % ig, {
        "media_type": "REELS",
        "video_url": VIDEO_URL,
        "caption": caption_of(post),
        "share_to_feed": "true",
    })
    cid = create.get("id")
    if not cid:
        raise MetaError("인스타 업로드 준비 실패")
    status = ""
    for _ in range(40):  # 최대 약 10분 기다림
        time.sleep(15)
        info = call("GET", "/" + cid, {"fields": "status_code,status"})
        status = info.get("status_code", "")
        print("instagram processing:", status)
        if status == "FINISHED":
            break
        if status in ("ERROR", "EXPIRED"):
            raise MetaError("인스타 영상 처리 실패: %s" % info.get("status", status))
    if status != "FINISHED":
        raise MetaError("인스타 영상 처리 시간이 너무 오래 걸림")
    pub = call("POST", "/%s/media_publish" % ig, {"creation_id": cid})
    return pub.get("id")


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def main():
    post = load(os.path.join(OUT, "post.json"), None)
    if not post:
        print("post.json 없음 - 건너뜀")
        return 0
    if not TOKEN:
        print("META_TOKEN 없음 - 자동 올리기 건너뜀")
        return 0
    if not VIDEO_URL:
        print("VIDEO_URL 없음 - 건너뜀")
        return 0

    posted = load(POSTED, {})
    today = posted.get(post["date"], {})
    result = {"date": post["date"], "facebook": today.get("facebook"), "instagram": today.get("instagram"), "errors": []}

    try:
        page, ig = find_page()
    except MetaError as e:
        result["errors"].append("페이지 찾기: %s" % e)
        print("ERROR", result["errors"][-1])
        page, ig = None, None

    if page and not result["facebook"]:
        try:
            result["facebook"] = post_facebook(page, post) or "ok"
            print("facebook: posted")
        except MetaError as e:
            result["errors"].append("페이스북: %s" % e)
            print("ERROR", result["errors"][-1])
    elif result["facebook"]:
        print("facebook: already posted today")

    if ig and not result["instagram"]:
        try:
            result["instagram"] = post_instagram(ig, post) or "ok"
            print("instagram: posted")
        except MetaError as e:
            result["errors"].append("인스타그램: %s" % e)
            print("ERROR", result["errors"][-1])
    elif result["instagram"]:
        print("instagram: already posted today")
    elif page and not ig:
        result["errors"].append("인스타그램 계정이 페이지에 연결되어 있지 않음")

    posted[post["date"]] = {"facebook": result["facebook"], "instagram": result["instagram"]}
    keep = sorted(posted)[-60:]
    with open(POSTED, "w", encoding="utf-8") as f:
        json.dump({k: posted[k] for k in keep}, f, ensure_ascii=False, indent=1)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "posted.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)

    # 둘 다 실패하면 실패로 표시 → GitHub 이 대표님 이메일로 알림
    if not result["facebook"] and not result["instagram"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
