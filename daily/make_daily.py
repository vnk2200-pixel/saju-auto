# -*- coding: utf-8 -*-
"""
매일 자동 홍보 글 만들기 (러브 오라클)

1) 오늘(한국 날짜)의 일진·월운을 사주 엔진(saju.py)으로 계산합니다.
2) 그 계산 결과만 근거로 Claude(Anthropic API)가 궁금증을 부르는 짧은 맛보기 글을 씁니다.
   - ANTHROPIC_API_KEY 가 없거나 오류가 나면, 미리 준비한 문장으로 대신 만들어 멈추지 않습니다.
3) 지난 글(daily/history.json)과 비교해 비슷하면 버리고 다시 씁니다.

결과: out/post.json
"""

import os
import re
import sys
import json
import random
import difflib
import datetime
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import saju  # noqa: E402

HISTORY_FILE = os.path.join(HERE, "history.json")
OUT_DIR = os.path.join(ROOT, "out")

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5").strip()
CTA = "프로필 링크에서 내 사주 무료로 확인"

S_K = saju.STEMS_K
B_K = saju.BRANCH_K
ANIMALS = saju.ANIMALS
EL = saju.EL_NAME

# ------------------------------------------------------------------
# 오늘의 기운 계산
# ------------------------------------------------------------------

REL_MEAN = {
    "합": "서로 끌어당기는 합(合) - 도움과 인연이 붙기 쉬운 날",
    "삼합": "같은 편이 되는 삼합(三合) - 일이 손발 맞듯 풀리기 쉬운 날",
    "같음": "같은 기운이 겹치는 날 - 내 색깔이 강하게 드러나는 날",
    "충": "부딪치는 충(沖) - 변화와 이동, 말실수 조심이 필요한 날",
    "원진": "서운함이 생기기 쉬운 원진(怨嗔) - 감정 표현을 아끼면 좋은 날",
    "형": "긴장이 생기는 형(刑) - 서두르지 말고 확인이 필요한 날",
    "": "무난하게 흘러가는 날",
}

GOD_MEAN = {
    "비겁": "친구·경쟁자의 기운. 사람은 모이지만 지출과 자존심 싸움 주의",
    "식상": "표현·매력의 기운. 말과 행동이 눈에 띄고 연애 표현에 유리",
    "재성": "재물·현실의 기운. 돈 흐름과 실속을 챙기기 좋은 날",
    "관성": "명예·인연의 기운. 일에서는 책임, 연애에서는 진지한 인연의 신호",
    "인성": "도움·문서의 기운. 윗사람·조언·계약 서류에 힘이 실리는 날",
}

# 월지 순서: 인월(양력 2월 초)부터
MONTH_LABEL = {2: "2월생", 3: "3월생", 4: "4월생", 5: "5월생", 6: "6월생", 7: "7월생",
               8: "8월생", 9: "9월생", 10: "10월생", 11: "11월생", 0: "12월생", 1: "1월생"}
# 지지 -> 대략적인 양력 생일 범위 (절기 기준)
BRANCH_BIRTH = {2: "2/4~3/5", 3: "3/6~4/4", 4: "4/5~5/5", 5: "5/6~6/5", 6: "6/6~7/6",
                7: "7/7~8/7", 8: "8/8~9/7", 9: "9/8~10/7", 10: "10/8~11/6",
                11: "11/7~12/6", 0: "12/7~1/5", 1: "1/6~2/3"}


def kst_today():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).date()


def day_facts(day):
    a = saju.compute(day)
    p = a["pillars"]
    ys, yb = p["year"]
    ms, mb = p["month"]
    ds, db = p["day"]

    animals = []
    for b in range(12):
        rel = saju.branch_relation(b, db)
        animals.append({
            "띠": ANIMALS[b] + "띠",
            "오늘 일진과의 관계": rel or "보통",
            "뜻": REL_MEAN[rel],
        })

    months = []
    for b in [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 0, 1]:
        rel = saju.branch_relation(b, db)
        months.append({
            "태어난 달(절기 기준)": "%s월 기운(%s, 양력 약 %s 출생)" % (B_K[b], ANIMALS[b], BRANCH_BIRTH[b]),
            "오늘 일진과의 관계": rel or "보통",
            "뜻": REL_MEAN[rel],
        })

    stems = []
    for s in range(10):
        god = saju.ten_god(s, ds)
        group = saju.GROUPS[god // 2]
        stems.append({
            "일간(태어난 날의 천간)": "%s%s(%s)" % (S_K[s], EL[saju.STEM_EL[s]], saju.STEMS_H[s]),
            "오늘 들어오는 기운": "%s(%s)" % (saju.TEN_GODS[god], group),
            "뜻": GOD_MEAN[group],
        })

    return {
        "날짜": "%d년 %d월 %d일" % (day.year, day.month, day.day),
        "요일": "월화수목금토일"[day.weekday()] + "요일",
        "오늘 일진": "%s%s일(%s%s日) - %s의 날, 천간 %s 지지 %s" % (
            S_K[ds], B_K[db], saju.STEMS_H[ds], saju.BRANCH_H[db], ANIMALS[db],
            EL[saju.STEM_EL[ds]], EL[saju.BRANCH_EL[db]]),
        "이번 달 월운": "%s%s월(%s의 달)" % (S_K[ms], B_K[mb], ANIMALS[mb]),
        "올해 세운": "%s%s년(%s띠 해)" % (S_K[ys], B_K[yb], ANIMALS[yb]),
        "띠별": animals,
        "태어난 달별": months,
        "일간별": stems,
        "_day_animal": ANIMALS[db],
        "_day_name": S_K[ds] + B_K[db] + "일",
        "_day_el": saju.STEM_EL[ds],
    }


# ------------------------------------------------------------------
# 오늘의 형식·주제 (날마다 돌아가며 바뀜)
# ------------------------------------------------------------------

FORMATS = [
    ("띠별", "년생(띠)별: 오늘 일진과 합이 드는 띠와 충이 드는 띠를 골라 말해 주기"),
    ("태어난 달별", "태어난 달(월생)별: 오늘 기운이 좋은 달생과 조심할 달생 골라 말해 주기"),
    ("일간별", "태어난 날의 기운(일간)별: 오늘 들어오는 십신으로 말해 주기. 대부분 자기 일간을 모르니 '내 일간은 무료로 확인'으로 궁금증 유발"),
    ("띠별", "띠별 TOP3: 오늘 운이 열리는 띠 3개와 한 마디씩"),
]
THEMES = ["연애운", "금전운", "연애운", "인간관계·연락운", "금전운", "새해(2027년) 앞두고 연애·재물 흐름", "일·직장운"]
STYLES = [
    "다정한 언니가 속삭이듯",
    "차분한 명리 선생님이 짧게 짚어 주듯",
    "질문을 던지며 시작하는 방식(예: 혹시 요즘 ~하지 않으세요?)",
    "반전이 있는 방식(좋은 줄 알았는데 한 가지만 조심)",
    "숫자로 정리하는 방식(오늘 기억할 3가지)",
    "친구에게 카톡 보내듯 가볍게",
]


def pick_plan(day, history):
    n = day.toordinal()
    rnd = random.Random(n)
    fmt = FORMATS[n % len(FORMATS)]
    theme = THEMES[(n // 2) % len(THEMES)]
    recent_styles = [h.get("style") for h in history[-3:]]
    styles = [s for s in STYLES if s not in recent_styles] or STYLES
    return {"format": fmt[0], "format_rule": fmt[1], "theme": theme, "style": rnd.choice(styles)}


# ------------------------------------------------------------------
# 겹침 점검
# ------------------------------------------------------------------

def norm(text):
    return re.sub(r"[^가-힣a-zA-Z0-9]", "", text or "")


def similarity(post, old):
    a = norm(post.get("hook", "") + "".join(post.get("slides", [])))
    b = norm(old.get("hook", "") + "".join(old.get("slides", [])))
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def too_similar(post, history):
    hook = norm(post.get("hook", ""))
    for old in history[-90:]:
        if hook and hook == norm(old.get("hook", "")):
            return "제목이 예전 글(%s)과 똑같음" % old.get("date")
        if similarity(post, old) >= 0.55:
            return "내용이 예전 글(%s)과 너무 비슷함" % old.get("date")
    return ""


BANNED = ["무조건", "100%", "반드시 당첨", "확실히 돈", "댓글", "DM", "디엠", "가격", "990원", "9,900", "9900",
          "주식", "코인", "로또", "질병", "병원", "수술", "사망", "사고 조심"]


def check_rules(post):
    text = post.get("hook", "") + " ".join(post.get("slides", [])) + " " + post.get("caption", "")
    for w in BANNED:
        if w in text:
            return "금지 표현 포함: " + w
    if not (4 <= len(post.get("slides", [])) <= 8):
        return "화면 문장 개수가 맞지 않음"
    for s in post.get("slides", []):
        if len(s) > 34:
            return "화면 문장이 너무 김: " + s
    if len(post.get("hook", "")) > 26:
        return "제목이 너무 김"
    return ""


# ------------------------------------------------------------------
# Claude 로 글쓰기
# ------------------------------------------------------------------

SYSTEM = """당신은 인스타그램·페이스북·스레드에 올릴 '사주 맛보기' 짧은 영상 문구를 쓰는 한국 명리학 콘텐츠 작가입니다.
반드시 지킬 것:
- 사용자가 준 [오늘의 사주 계산 결과]에 있는 사실(일진, 합·충·원진·형, 십신)만 근거로 씁니다. 없는 계산을 지어내지 않습니다.
- 끝까지 다 알려 주지 않고 '나는 어떨까?' 궁금하게 만들어, 마지막은 '프로필 링크에서 내 사주 무료로 확인'으로 자연스럽게 이어지게 합니다.
- 겁주기, 단정·보장 표현(무조건, 100%, 반드시), 건강·질병·사고, 투자(주식·코인·로또) 조언, 가격 언급, '댓글/DM 남겨 주세요' 같은 응대 유도는 쓰지 않습니다.
- 성인(만 19세 이상) 대상, 따뜻하고 품위 있는 말투. AI가 쓴 티(이모지 남발, 과장된 감탄, 번역투)가 나지 않게 사람이 쓴 것처럼.
- 제목(hook)은 영상 내내 위쪽에 떠 있으므로, 화면 문장(slides)에서 제목을 되풀이하지 말 것.
- 영상 화면 문장(slides)은 한 줄에 34자 이내, 5~7줄. 첫 줄은 제목 다음 이야기로 바로 들어갈 것.
- 해시태그는 한국어 8~12개, 실제로 많이 쓰는 말(예: #사주 #오늘의운세 #띠별운세 #연애운).
출력은 JSON 하나만, 설명 없이:
{"hook": "26자 이내 제목", "slides": ["...", "..."], "caption": "게시글 본문 3~6문장. 마지막 문장은 프로필 링크 안내", "hashtags": ["#사주", "..."]}"""


def ask_claude(facts, plan, avoid, feedback=""):
    public = {k: v for k, v in facts.items() if not k.startswith("_")}
    user = (
        "[오늘의 사주 계산 결과]\n" + json.dumps(public, ensure_ascii=False, indent=1) +
        "\n\n[오늘 글의 형식] " + plan["format_rule"] +
        "\n[오늘의 주제] " + plan["theme"] +
        "\n[말투] " + plan["style"] +
        "\n[최근에 이미 쓴 제목들 - 비슷하게 쓰지 말 것]\n" + "\n".join("- " + h for h in avoid) +
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
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("JSON 없음")
    post = json.loads(m.group(0))
    post["slides"] = [str(s).strip() for s in post.get("slides", []) if str(s).strip()]
    post["hashtags"] = [("#" + str(h).lstrip("#")).replace(" ", "") for h in post.get("hashtags", [])][:12]
    usage = data.get("usage", {})
    return post, usage


# ------------------------------------------------------------------
# AI 가 안 될 때 쓰는 예비 문장 (멈추지 않게)
# ------------------------------------------------------------------

def fallback_post(facts, plan, history):
    rnd = random.Random(facts["날짜"] + str(len(history)))
    good = [a["띠"] for a in facts["띠별"] if a["오늘 일진과의 관계"] in ("합", "삼합")]
    bad = [a["띠"] for a in facts["띠별"] if a["오늘 일진과의 관계"] == "충"]
    rnd.shuffle(good)
    theme = plan["theme"].split("(")[0]
    hooks = [
        "오늘 %s, 이 띠는 문이 열립니다" % theme,
        "%s, 합이 드는 띠가 따로 있어요" % facts["_day_name"],
        "오늘 %s의 날, 내 띠는?" % facts["_day_animal"],
    ]
    slides = [
        "오늘은 %s, %s의 날입니다" % (facts["_day_name"], facts["_day_animal"]),
        "%s에게 합이 들어와요" % ", ".join(good[:3]) if good else "오늘은 조용히 흐르는 날이에요",
        "기다리던 소식이 붙기 쉬운 흐름",
        ("%s는 말 한마디만 아껴 주세요" % bad[0]) if bad else "서두르지 않으면 실속이 남아요",
        "그런데 같은 띠라도 태어난 날에 따라 달라요",
        "내 사주는 어떤지, " + CTA,
    ]
    caption = "오늘은 %s입니다. %s와 합이 드는 띠는 %s. %s. 같은 띠라도 태어난 달과 날에 따라 흐름이 달라지니, %s하세요." % (
        facts["_day_name"], facts["_day_animal"], ", ".join(good) or "많지 않아요",
        ("%s는 오늘 충이 드니 말과 이동을 조심하면 좋아요" % bad[0]) if bad else "무난한 하루예요",
        CTA)
    return {"hook": rnd.choice(hooks), "slides": slides, "caption": caption,
            "hashtags": ["#사주", "#오늘의운세", "#띠별운세", "#" + theme.replace(" ", "").replace("·", ""),
                         "#명리학", "#일진", "#운세", "#사주풀이"]}


# ------------------------------------------------------------------

def load_history():
    try:
        with open(HISTORY_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def main():
    day = kst_today()
    if len(sys.argv) > 1:
        day = datetime.date.fromisoformat(sys.argv[1])
    history = load_history()
    facts = day_facts(day)
    plan = pick_plan(day, history)
    avoid = [h.get("hook", "") for h in history[-30:]]

    post, source, feedback, tries = None, "fallback", "", []
    if API_KEY:
        for attempt in range(4):
            try:
                cand, usage = ask_claude(facts, plan, avoid, feedback)
            except Exception as e:  # 네트워크·잔액 부족 등
                tries.append("AI 오류: %r" % (e,))
                print("AI ERROR:", repr(e))
                break
            problem = check_rules(cand) or too_similar(cand, history)
            tries.append(problem or "통과")
            print("try", attempt + 1, cand.get("hook"), "->", problem or "OK", usage)
            if not problem:
                post, source = cand, "claude"
                break
            feedback = problem + ". 완전히 다른 첫 문장과 다른 표현으로 다시 쓰세요."
            avoid.append(cand.get("hook", ""))
    else:
        tries.append("ANTHROPIC_API_KEY 없음 - 예비 문장 사용")

    if post is None:
        post = fallback_post(facts, plan, history)
        source = "fallback"

    if "프로필" not in post["slides"][-1]:
        post["slides"].append(CTA)

    post.update({
        "date": day.isoformat(),
        "day_name": facts["_day_name"],
        "day_animal": facts["_day_animal"],
        "day_element": facts["_day_el"],
        "format": plan["format"],
        "theme": plan["theme"],
        "style": plan["style"],
        "source": source,
        "checks": tries,
    })
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "post.json"), "w", encoding="utf-8") as f:
        json.dump(post, f, ensure_ascii=False, indent=2)
    print(json.dumps(post, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
