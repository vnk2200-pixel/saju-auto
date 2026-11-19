# -*- coding: utf-8 -*-
"""
오늘의 사주 이야기를 스레드(Threads, saju.oneul)에 '사람이 쓴 글'처럼 자동으로 올립니다.

- 페이스북·인스타용 문구(out/post.json)를 그대로 쓰지 않고,
  스레드용으로 따로 짧게 씁니다. 말투: 조금 서툴고 어눌해도 진심이 묻어나는 혼잣말.
- 프로필 링크 안내는 사흘에 한 번만 넣습니다 (매번 넣으면 광고처럼 보여 노출이 줄어듦).
- 같은 날 이미 올렸으면 다시 올리지 않습니다 (daily/threads_posted.json 기록).
- 예전 글과 너무 비슷하면 다시 쓰게 합니다.

필요한 것 (GitHub 금고 Secrets):
  THREADS_TOKEN     : Meta 개발자 > Threads API 액세스 > 설정 > 사용자 토큰 생성기에서 만든 토큰
  ANTHROPIC_API_KEY : 글쓰기용 (이미 등록돼 있음). 없거나 오류면 예비 문장으로 올립니다.

토큰이나 고유번호는 화면 기록(로그)에 출력하지 않습니다.
"""

import os
import re
import sys
import json
import time
import random
import difflib
import datetime
import urllib.parse
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "out")
RECORD = os.path.join(HERE, "threads_posted.json")

SEED = os.environ.get("THREADS_TOKEN", "").strip()  # 금고에 넣은 처음 토큰 (암호 열쇠로도 씀)
TOKEN = SEED
TOKEN_FILE = os.path.join(HERE, "threads_token.json")  # 연장된 토큰을 암호화해서 보관
REFRESH_DAYS = 7
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5").strip()
THREADS = "https://graph.threads.net/v1.0"
LINK_LINE = "내 사주가 궁금하면 프로필 링크 한번 들러 주세요."
MAX_LEN = 480  # 스레드 글자 제한 500자, 여유를 둠

BANNED = ["무조건", "100%", "반드시", "확실히", "댓글", "DM", "디엠", "가격", "990", "9,900", "9900",
          "주식", "코인", "로또", "질병", "병원", "수술", "사망", "사고", "AI", "인공지능", "#"]

SYSTEM = """당신은 스레드(Threads)에 사주 이야기를 올리는 50대 한국 사람입니다. 명리학을 오래 공부했지만 글솜씨는 그리 매끄럽지 않습니다.
글쓰기 규칙:
- 조금 서툴고 어눌해도 진심이 가득한 말투. 잘 다듬은 광고 문구나 블로그 글처럼 쓰지 않습니다.
- 혼잣말이나 이웃에게 털어놓듯이. 짧은 문장, 줄바꿈 많이. 5~8줄, 전체 250자 안팎.
- 가끔 '~더라고요', '~거든요', '저도 그랬고요', 'ㅎㅎ' 같은 입말. 단, 매번 같은 말버릇을 반복하지 않습니다.
- 이모지는 쓰지 않거나 많아야 하나. 해시태그, 따옴표 강조, 번역투, 과장된 감탄은 쓰지 않습니다.
- 주어진 [오늘의 사주 정보]에서 한 가지만 골라 자연스럽게 녹입니다. 계산 결과에 없는 내용은 지어내지 않습니다.
- 겁주기, 단정·보장 표현(무조건, 100%, 반드시), 건강·질병·사고, 투자(주식·코인·로또), 가격, '댓글/DM 남겨 주세요' 같은 말은 쓰지 않습니다.
- 위로와 응원으로 끝나도 좋고, 담담하게 끝나도 좋습니다. 가르치려 들지 않습니다.
- 링크·사이트·프로필 이야기는 쓰지 않습니다(필요하면 따로 붙입니다).
출력은 글 본문만. 설명, 제목, 따옴표 없이."""


class ThreadsError(Exception):
    pass


def kst_today():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).date()


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


# ------------------------------------------------------------------
# 글쓰기
# ------------------------------------------------------------------

def norm(text):
    return re.sub(r"[^가-힣a-zA-Z0-9]", "", text or "")


def check(text, old_texts):
    if not text or len(text) < 60:
        return "글이 너무 짧음"
    if len(text) > 400:
        return "글이 너무 김 (250자 안팎으로)"
    for w in BANNED:
        if w in text:
            return "쓰면 안 되는 말이 들어감: " + w
    a = norm(text)
    first = norm(text.splitlines()[0])
    for old in old_texts[-60:]:
        if first and first == norm(old.splitlines()[0] if old else ""):
            return "첫 줄이 예전 글과 똑같음"
        if difflib.SequenceMatcher(None, a, norm(old)).ratio() >= 0.5:
            return "예전 글과 너무 비슷함"
    return ""


def ask_claude(post, old_texts, feedback=""):
    info = {k: post.get(k) for k in ("date", "day_name", "day_animal", "theme", "format", "hook", "caption") if post.get(k)}
    user = (
        "[오늘의 사주 정보]\n" + json.dumps(info, ensure_ascii=False, indent=1) +
        "\n\n[최근에 이미 올린 글 - 비슷한 첫 줄, 비슷한 흐름으로 쓰지 말 것]\n" +
        "\n---\n".join(old_texts[-5:]) +
        ("\n\n[다시 써야 하는 이유] " + feedback if feedback else "")
    )
    body = json.dumps({
        "model": MODEL,
        "max_tokens": 1500,
        "temperature": 1.0,
        "system": SYSTEM,
        "messages": [{"role": "user", "content": user}],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body, method="POST",
        headers={"x-api-key": API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read().decode("utf-8"))
    text = "".join(c.get("text", "") for c in data.get("content", []) if c.get("type") == "text")
    text = text.strip().strip('"').strip()
    lines = [ln.rstrip() for ln in text.splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


FALLBACK = [
    "오늘은 {day}이에요.\n사주 들여다보면 늘 느끼는 건데요\n좋은 날이 따로 있다기보다\n내가 마음을 어디 두느냐가\n더 크더라고요.\n오늘 하루 너무 애쓰지 마세요.",
    "{day}, {animal}의 날이네요.\n괜히 마음이 바쁜 날 있잖아요.\n저는 그런 날엔\n하나만 끝내자 하고 말아요.\n그게 생각보다 도움이 되더라고요.",
    "요즘 {theme} 궁금해하시는 분들 많더라고요.\n저도 사주 보면서 알게 된 게\n안 될 때는 다 이유가 있고\n될 때는 또 술술 풀린다는 거예요.\n오늘 {day}, 조금만 더 버텨 봐요.",
    "오늘 {day}이에요.\n별거 아닌 말 한마디에\n마음이 풀리는 날도 있잖아요.\n오늘은 내가 먼저\n그 한마디 건네 보면 어떨까 싶어요.",
]


def fallback_text(post, n):
    tpl = FALLBACK[n % len(FALLBACK)]
    theme = (post.get("theme") or "운세").split("(")[0].replace("새해", "새해 운")
    return tpl.format(day=post.get("day_name", "오늘"), animal=post.get("day_animal", ""), theme=theme)


def write_text(post, record):
    old_texts = [v.get("text", "") for k, v in sorted(record.items()) if isinstance(v, dict)]
    tries, feedback = [], ""
    if API_KEY:
        for attempt in range(4):
            try:
                text = ask_claude(post, old_texts, feedback)
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", "replace")[:200]
                tries.append("AI 오류 %s: %s" % (e.code, body))
                if e.code in (400, 401, 403, 404):
                    break
                continue
            except Exception as e:
                tries.append("AI 오류: %r" % (e,))
                continue
            problem = check(text, old_texts)
            tries.append(problem or "통과")
            print("try", attempt + 1, "->", problem or "OK")
            if not problem:
                return text, "claude", tries
            feedback = problem + ". 완전히 다른 첫 문장, 다른 이야기로 다시 쓰세요."
    else:
        tries.append("ANTHROPIC_API_KEY 없음 - 예비 문장 사용")
    return fallback_text(post, len(record)), "fallback", tries


# ------------------------------------------------------------------
# 스레드에 올리기
# ------------------------------------------------------------------

def call(method, path, params, base=THREADS):
    params = dict(params)
    params["access_token"] = TOKEN
    url = base + path
    data = None
    if method == "GET":
        url += "?" + urllib.parse.urlencode(params)
    else:
        data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            err = json.loads(body).get("error", {})
            msg = "%s (code %s/%s)" % (err.get("message", ""), err.get("code"), err.get("error_subcode"))
        except Exception:
            msg = body[:200]
        if e.code in (400, 401) and ("token" in msg.lower() or "190" in msg):
            msg += " → 토큰이 만료됐을 수 있어요. Meta 개발자에서 새 토큰을 만들어 GitHub 금고 THREADS_TOKEN을 바꿔 주세요."
        raise ThreadsError("HTTP %s: %s" % (e.code, msg))


def publish(text):
    create = call("POST", "/me/threads", {"media_type": "TEXT", "text": text})
    cid = create.get("id")
    if not cid:
        raise ThreadsError("글 준비 실패")
    time.sleep(10)  # 메타 권장: 준비 후 잠깐 기다렸다가 발행
    for attempt in range(3):
        try:
            pub = call("POST", "/me/threads_publish", {"creation_id": cid})
            return pub.get("id") or "ok"
        except ThreadsError:
            if attempt == 2:
                raise
            time.sleep(20)


# ------------------------------------------------------------------
# 토큰 자동 연장 (60일짜리 토큰을 일주일마다 새것으로 바꿔 만료되지 않게 함)
# 새 토큰은 금고 토큰으로 만든 열쇠로 암호화해서 저장 → 저장소에 보여도 읽을 수 없음
# 대표님이 금고 토큰을 새로 바꾸면, 예전 파일은 못 열리므로 자동으로 새 금고 토큰을 씀
# ------------------------------------------------------------------

def _fernet():
    import base64
    import hashlib
    from cryptography.fernet import Fernet
    key = base64.urlsafe_b64encode(hashlib.sha256(("saju-threads:" + SEED).encode("utf-8")).digest())
    return Fernet(key)


def load_token():
    global TOKEN
    info = load(TOKEN_FILE, {})
    if info.get("data"):
        try:
            TOKEN = _fernet().decrypt(info["data"].encode("ascii")).decode("utf-8")
            print("threads token: 연장된 토큰 사용 (마지막 연장 %s)" % info.get("refreshed"))
        except Exception:
            TOKEN = SEED
            print("threads token: 금고 토큰 사용 (보관 토큰을 열 수 없음)")
    return info


def refresh_token(info):
    global TOKEN
    last = info.get("refreshed")
    today = kst_today()
    if last and (today - datetime.date.fromisoformat(last)).days < REFRESH_DAYS:
        return
    try:
        res = call("GET", "/refresh_access_token", {"grant_type": "th_refresh_token"}, base="https://graph.threads.net")
    except ThreadsError as e:
        print("threads token: 연장 건너뜀 (%s)" % str(e)[:80])
        return
    new = (res.get("access_token") or "").strip()
    if not new:
        return
    TOKEN = new
    days = int(res.get("expires_in", 0)) // 86400
    data = _fernet().encrypt(new.encode("utf-8")).decode("ascii")
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump({"refreshed": today.isoformat(), "valid_days": days, "data": data}, f, ensure_ascii=False, indent=1)
    print("threads token: 연장 완료 (앞으로 약 %d일)" % days)


def main():
    post = load(os.path.join(OUT, "post.json"), None) or {}
    day = post.get("date") or kst_today().isoformat()
    if not TOKEN:
        print("THREADS_TOKEN 없음 - 스레드 올리기 건너뜀")
        return 0

    refresh_token(load_token())

    record = load(RECORD, {})
    if (record.get(day) or {}).get("id"):
        print("threads: already posted today")
        return 0

    text, source, tries = write_text(post, record)
    n = datetime.date.fromisoformat(day).toordinal()
    with_link = (n % 3 == 0)
    if with_link:
        text = text.rstrip() + "\n\n" + LINK_LINE
    text = text[:MAX_LEN]

    result = {"text": text, "source": source, "link": with_link, "checks": tries, "id": None, "error": None}
    try:
        result["id"] = publish(text)
        print("threads: posted (%s, link=%s)" % (source, with_link))
    except ThreadsError as e:
        result["error"] = str(e)
        print("ERROR threads:", e)

    record[day] = result
    keep = sorted(record)[-90:]
    with open(RECORD, "w", encoding="utf-8") as f:
        json.dump({k: record[k] for k in keep}, f, ensure_ascii=False, indent=1)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "threads.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(text)
    return 0 if result["id"] else 1


if __name__ == "__main__":
    sys.exit(main())
