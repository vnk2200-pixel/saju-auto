# -*- coding: utf-8 -*-
"""상품별 풀이 자동 생성"""

import saju
import texts as T

PRODUCTS = [
    {"id": "love-first", "icon": "❤️", "name": "2027년 새해, 나의 인연은? (사주·명리)", "price": 990, "partner": False,
     "desc": "2027년 나의 인연 흐름과 인연이 들어오는 달을 사주·명리 관점에서 가볍게 살펴봅니다."},
    {"id": "love", "icon": "❤️", "name": "2027년 새해, 내 가슴을 뛰게 하는 인연은? (사주·명리)", "price": 30000, "partner": False,
     "desc": "2027년, 내 마음을 설레게 할 인연은 언제, 어떤 모습으로 올까? 나의 연애 성향과 인연의 흐름, 인연이 좋은 달을 자세히 살펴봅니다."},
    {"id": "match", "icon": "💞", "name": "현재 연인은 진심으로 나를 사랑할까? (사주·명리)", "price": 70000, "partner": True,
     "desc": "지금 만나고 있는 그 사람, 나를 진심으로 사랑하고 있을까? 두 사람의 생년월일시로 서로의 마음과 궁합, 2027년 인연의 흐름을 살펴봅니다."},
    {"id": "relation", "icon": "🏡", "name": "사실혼·동거 중인데, 계속 살아야 할까 헤어져야 할까? (사주·명리)", "price": 300000, "partner": True,
     "desc": "동거·사실혼 관계, 계속 함께 살아야 할지 헤어져야 할지 고민될 때. 두 사람의 사주로 함께 사는 생활의 궁합, 갈등의 원인, 앞으로의 흐름을 깊이 살펴봅니다. 최종 결정은 두 사람의 몫입니다."},
    {"id": "move", "icon": "🏠", "name": "이사·부동산운 (사주·명리)", "price": 50000, "partner": False,
     "desc": "생년월일시를 바탕으로 2027년 이사·이동 흐름과 부동산 매입·매도·계약 시기를 사주·명리 관점에서 살펴봅니다."},
    {"id": "business", "icon": "💼", "name": "사업·재물운 (사주·명리)", "price": 50000, "partner": False,
     "desc": "생년월일시를 바탕으로 사업 성향과 2027년 변화·확장·재물 흐름을 사주·명리 관점에서 살펴봅니다."},
    {"id": "study", "icon": "🎓", "name": "진로·학업운 (사주·명리)", "price": 50000, "partner": False,
     "desc": "타고난 적성과 공부 방식, 2027년 학업·진로 흐름을 사주·명리 관점에서 살펴봅니다."},
    {"id": "job", "icon": "👔", "name": "취업·직업운 (사주·명리)", "price": 50000, "partner": False,
     "desc": "나에게 맞는 일의 방식과 직업 분야, 2027년 취업·이직 흐름을 사주·명리 관점에서 살펴봅니다."},
]
PRODUCT_BY_ID = {p["id"]: p for p in PRODUCTS}

TARGET_YEAR = 2027
YEAR_STEM, YEAR_BRANCH = saju.year_pillar_of(TARGET_YEAR)  # 丁未


# ------------------------------------------------------------------
# 도우미
# ------------------------------------------------------------------

def S(title, paras=None, table=None, items=None):
    sec = {"title": title, "paras": [p for p in (paras or []) if p]}
    if table:
        sec["table"] = table
    if items:
        sec["items"] = items
    return sec


def nim(person):
    return person["name"] + "님"


def year_god(a):
    return saju.ten_god(a["day_stem"], YEAR_STEM)


def year_branch_texts(a):
    out = []
    seen = set()
    for label, b in (("일지(나 자신과 배우자 자리)", a["day_branch"]), ("띠(년지)", a["year_branch"])):
        rel = saju.branch_relation(YEAR_BRANCH, b)
        if rel and rel not in seen:
            seen.add(rel)
            out.append(T.YEAR_BRANCH[rel])
    if not out:
        out.append(T.YEAR_BRANCH[""])
    return out


def monthly(a, domain):
    rows = []
    level = T.MONTH_LEVEL[domain]
    for mp in saju.month_pillars_of_year(TARGET_YEAR):
        god = saju.ten_god(a["day_stem"], mp["stem"])
        rel = saju.branch_relation(mp["branch"], a["day_branch"])
        mark = "★ 좋음" if god in level["good"] else ("△ 조심" if god in level["care"] else "○ 보통")
        tip = T.MONTH_TIP[god][domain]
        if rel == "충":
            tip += " · 변동 많음"
            if mark == "★ 좋음":
                mark = "○ 보통"
        elif rel in ("합", "삼합") and mark == "○ 보통":
            mark = "★ 좋음"
        rows.append([mp["label"] + " (" + mp["start"] + "~)",
                     saju.STEMS_K[mp["stem"]] + saju.BRANCH_K[mp["branch"]] + "월",
                     mark, tip])
    return rows


def month_table(a, domain, title):
    return S(title,
             ["절기(양력 기준 날짜) 기준으로 달이 바뀝니다. ★ 표시가 있는 달에 중요한 일을 계획하고, △ 표시가 있는 달에는 한 번 더 확인하세요."],
             table={"head": ["시기", "월 간지", "흐름", "한 줄 조언"], "rows": monthly(a, domain)})


def best_months(a, domain, n=3):
    rows = monthly(a, domain)
    good = [r[0].split(" ")[0] for r in rows if r[2].startswith("★")]
    return good[:n]


def lucky_items(a):
    e = T.ELEMENT[a["lucky"]]
    return [
        "도움이 되는 기운: " + e["name"],
        "행운의 색: " + e["color"],
        "좋은 방향: " + e["direction"],
        "행운의 숫자: " + e["number"],
    ]


def person_header(p):
    a = p["a"]
    dm = T.DAY_MASTER[a["day_stem"]]
    return S(nim(p) + "의 타고난 기운", [
        dm["nature"],
        T.STRENGTH[a["strength"]],
        "사주 전체에서 가장 두드러진 기운은 " + T.GROUP[a["dominant"]]["name"] + "입니다. " + T.GROUP[a["dominant"]]["nature"],
        None if a["known_time"] else "※ 태어난 시간을 모르셔서 시주를 제외한 세 기둥으로 풀이했습니다. 시간을 알게 되면 더 정확해집니다.",
    ])


def element_section(p):
    a = p["a"]
    counts = a["count"]
    desc = ", ".join(T.ELEMENT[i]["name"] + " " + ("%g" % counts[i]) for i in range(5))
    paras = ["오행 분포: " + desc + "."]
    if counts[a["weakest"]] == 0:
        paras.append(T.ELEMENT[a["weakest"]]["lack"])
    else:
        paras.append("가장 약한 기운은 " + T.ELEMENT[a["weakest"]]["name"] + "입니다. " + T.ELEMENT[a["weakest"]]["lack"])
    if counts[a["strongest"]] >= 3:
        paras.append(T.ELEMENT[a["strongest"]]["much"])
    return S("오행의 균형", paras, items=lucky_items(a))


def love_star(p):
    a = p["a"]
    female = p.get("gender") == "여성"
    grp = 3 if female else 2
    star = "관성(남성 인연의 별)" if female else "재성(여성 인연의 별)"
    amount = a["groups"][grp]
    yg = year_god(a) // 2
    if amount >= 2.5:
        t = "사주에 " + star + "이 뚜렷해 인연의 기회가 자주 찾아오는 편입니다. 기회가 많은 만큼 나와 맞는 사람을 알아보는 기준을 세워 두면 좋습니다."
    elif amount > 0:
        t = "사주에 " + star + "이 적당히 자리하고 있어, 때가 되면 자연스럽게 인연이 이어지는 구조입니다."
    else:
        t = "사주 원국에 " + star + "이 드러나 있지 않습니다. 이런 사주는 운에서 인연의 기운이 들어오는 시기에 만남이 집중되므로, 좋은 달을 놓치지 않는 것이 중요합니다."
    if yg == grp:
        t += " 특히 2027년은 인연의 별이 해의 기운으로 직접 들어오는 해라 만남의 기회가 뚜렷합니다."
    return t


def year_section(p, domain, title):
    a = p["a"]
    yg = T.YEAR_GOD[year_god(a)]
    return S(title, [yg["overview"], yg[domain]] + year_branch_texts(a))


# ------------------------------------------------------------------
# 상품별 풀이
# ------------------------------------------------------------------

def r_love_first(A):
    a = A["a"]
    dm = T.DAY_MASTER[a["day_stem"]]
    yg = T.YEAR_GOD[year_god(a)]
    months = best_months(a, "love")
    return [
        S(nim(A) + "은 " + dm["title"], [dm["love"]]),
        S("2027년 정미년, 나의 인연 흐름", [
            "2027년은 " + yg["key"] + "입니다.",
            yg["love"],
            love_star(A),
        ]),
        S("인연의 기운이 좋은 달", [
            ("2027년에는 " + ", ".join(months) + "에 인연의 기운이 좋습니다. 이 시기에는 모임과 소개를 적극적으로 받아 보세요.")
            if months else "2027년에는 특정 달보다 꾸준한 만남 속에서 인연이 자랍니다.",
        ]),
        S("행운 포인트", [T.ELEMENT[a["lucky"]]["name"] + " 기운이 인연 운을 도와줍니다."], items=lucky_items(a)[1:]),
        S("더 깊이 알고 싶다면", ["인연운 전체 풀이에서는 배우자 자리, 도화·역마, 월별 인연 흐름까지 자세히 살펴봅니다."]),
    ]


def r_love(A):
    a = A["a"]
    dm = T.DAY_MASTER[a["day_stem"]]
    return [
        person_header(A),
        S("연애 성향", [dm["love"], T.GROUP[a["dominant"]]["love"]]),
        S("배우자 자리와 인연의 모습", [T.SPOUSE[a["spouse_god"]], love_star(A)]),
        S("도화와 역마", [T.DOHWA if a["dohwa"] else T.NO_DOHWA, T.YEOKMA if a["yeokma"] else T.NO_YEOKMA]),
        year_section(A, "love", "2027년 정미년 인연운"),
        month_table(a, "love", "2027년 월별 인연 흐름"),
        element_section(A),
        S("인연을 부르는 생활 조언", [
            dm["talk"],
            "인연의 기운이 좋은 달(" + (", ".join(best_months(a, "love")) or "꾸준한 만남 속") + ")에는 약속을 미루지 말고, 새로운 모임이나 소개를 가볍게 받아 보세요.",
            "행운의 색인 " + T.ELEMENT[a["lucky"]]["color"] + " 계열을 옷이나 소품에 더하면 마음가짐이 달라지고, 그 마음가짐이 인연을 부릅니다.",
        ]),
    ]


def compat_core(A, B):
    a, b = A["a"], B["a"]
    ea, eb = a["dm_el"], b["dm_el"]
    if frozenset((a["day_stem"], b["day_stem"])) in saju.STEM_HAP:
        stem_rel = "합"
    elif ea == eb:
        stem_rel = "같음"
    elif (ea + 1) % 5 == eb:
        stem_rel = "내가생"
    elif (eb + 1) % 5 == ea:
        stem_rel = "상대가생"
    elif (ea + 2) % 5 == eb:
        stem_rel = "내가극"
    else:
        stem_rel = "상대가극"
    day_rel = saju.branch_relation(a["day_branch"], b["day_branch"])
    year_rel = saju.branch_relation(a["year_branch"], b["year_branch"])

    score = 72
    score += {"합": 14, "같음": 4, "내가생": 8, "상대가생": 8, "내가극": -3, "상대가극": -3}[stem_rel]
    score += {"합": 8, "삼합": 6, "같음": 2, "": 0, "충": -8, "원진": -6, "형": -5}[day_rel]
    score += {"합": 4, "삼합": 3, "같음": 1, "": 0, "충": -4, "원진": -3, "형": -2}[year_rel]
    comp = []
    if b["count"][a["weakest"]] >= 2:
        score += 4
        comp.append(nim(B) + "의 사주에 " + nim(A) + "에게 부족한 " + T.ELEMENT[a["weakest"]]["name"] + " 기운이 넉넉해, 곁에 있으면 빈자리를 채워 줍니다.")
    if a["count"][b["weakest"]] >= 2:
        score += 4
        comp.append(nim(A) + "의 사주에 " + nim(B) + "에게 부족한 " + T.ELEMENT[b["weakest"]]["name"] + " 기운이 넉넉해, " + nim(B) + "에게 힘이 되어 줍니다.")
    if not comp:
        comp.append("두 사람은 서로 부족한 기운을 크게 채워 주는 구조는 아니므로, 각자의 부족한 부분을 함께 보완하는 생활 습관(행운의 색, 좋은 방향 등)을 만들어 가면 좋습니다.")
    score = max(58, min(97, score))
    if score >= 88:
        grade = "서로를 끌어당기고 채워 주는 매우 좋은 궁합입니다."
    elif score >= 78:
        grade = "조화가 좋은 궁합입니다. 작은 차이만 잘 다루면 오래 함께할 수 있습니다."
    elif score >= 68:
        grade = "좋은 점과 조율할 점이 함께 있는 궁합입니다. 노력한 만큼 깊어지는 관계입니다."
    else:
        grade = "서로 다른 점이 많은 궁합입니다. 다름을 이해하는 대화가 관계의 열쇠입니다."
    return {"score": score, "grade": grade, "stem": T.STEM_PAIR[stem_rel],
            "day": T.BRANCH_PAIR_DAY[day_rel], "year": T.BRANCH_PAIR_YEAR[year_rel], "comp": comp}


def couple_months(A, B):
    rows = []
    ra, rb = monthly(A["a"], "love"), monthly(B["a"], "love")
    for x, y in zip(ra, rb):
        if x[2].startswith("★") and y[2].startswith("★"):
            mark = "★ 함께 좋음"
            tip = "관계를 한 단계 진전시키기 좋은 달"
        elif x[2].startswith("△") and y[2].startswith("△"):
            mark = "△ 함께 조심"
            tip = "큰 결정은 미루고 대화 시간을 늘리기"
        elif x[2].startswith("△") or y[2].startswith("△"):
            mark = "○ 배려 필요"
            who = nim(A) if x[2].startswith("△") else nim(B)
            tip = who + "의 마음이 예민해지기 쉬운 달"
        else:
            mark = "○ 무난"
            tip = "일상을 함께 나누며 편안하게"
        rows.append([x[0], x[1], mark, tip])
    return S("2027년 두 사람의 월별 흐름",
             ["두 사람 각자의 월별 인연 흐름을 겹쳐 본 결과입니다."],
             table={"head": ["시기", "월 간지", "두 사람", "조언"], "rows": rows})


def r_match(A, B):
    c = compat_core(A, B)
    dA, dB = T.DAY_MASTER[A["a"]["day_stem"]], T.DAY_MASTER[B["a"]["day_stem"]]
    return [
        S("궁합 한눈에 보기", ["궁합 점수 " + str(c["score"]) + "점. " + c["grade"]]),
        S("두 사람의 기본 성향", [
            nim(A) + "은 " + dA["title"] + "입니다. " + dA["love"],
            nim(B) + "은 " + dB["title"] + "입니다. " + dB["love"],
        ]),
        S("마음의 궁합 (일간)", [c["stem"]]),
        S("생활의 궁합 (일지·배우자 자리)", [c["day"]]),
        S("띠 궁합", [c["year"]]),
        S("서로 채워 주는 기운", c["comp"]),
        S("2027년 두 사람의 인연 흐름", [
            nim(A) + ": " + T.YEAR_GOD[year_god(A["a"])]["love"],
            nim(B) + ": " + T.YEAR_GOD[year_god(B["a"])]["love"],
        ]),
        couple_months(A, B),
        S("관계를 위한 조언", [
            nim(A) + "에게: " + dA["talk"],
            nim(B) + "에게: " + dB["talk"],
        ]),
    ]


def r_relation(A, B):
    c = compat_core(A, B)
    a, b = A["a"], B["a"]
    dA, dB = T.DAY_MASTER[a["day_stem"]], T.DAY_MASTER[b["day_stem"]]
    gA, gB = T.GROUP[a["dominant"]], T.GROUP[b["dominant"]]
    diff = []
    if a["dominant"] == b["dominant"]:
        diff.append("두 사람 모두 " + gA["name"] + "이 두드러져 가치관이 비슷합니다. 같은 방향을 볼 때는 큰 힘이 되지만, 같은 약점이 겹칠 때는 서로를 탓하기 쉬우니 역할을 나눠 보세요.")
    else:
        diff.append(nim(A) + "은 " + gA["name"] + "이 두드러집니다. " + gA["nature"])
        diff.append(nim(B) + "은 " + gB["name"] + "이 두드러집니다. " + gB["nature"])
        diff.append("두 사람은 중요하게 여기는 것이 서로 다릅니다. 이 차이는 갈등의 원인이 되기도 하지만, 서로가 보지 못하는 부분을 대신 봐 주는 힘이 되기도 합니다.")
    return [
        S("관계 한눈에 보기", ["궁합 점수 " + str(c["score"]) + "점. " + c["grade"],
                          "이 풀이는 두 사람의 관계를 판단하거나 결정을 대신하지 않습니다. 서로를 더 잘 이해하기 위한 참고 자료로 활용해 주세요."]),
        person_header(A),
        S(nim(A) + "의 사랑 방식", [dA["love"], T.SPOUSE[a["spouse_god"]]]),
        person_header(B),
        S(nim(B) + "의 사랑 방식", [dB["love"], T.SPOUSE[b["spouse_god"]]]),
        S("마음의 궁합 (일간)", [c["stem"]]),
        S("함께 사는 생활의 궁합 (일지)", [c["day"]]),
        S("띠 궁합", [c["year"]]),
        S("서로 다른 성향", diff),
        S("서로 채워 주는 기운", c["comp"]),
        S("갈등이 생길 때", [
            nim(A) + ": " + T.EL_CONFLICT[a["dm_el"]],
            nim(B) + ": " + T.EL_CONFLICT[b["dm_el"]],
            "다툼이 생기면 '누가 옳은가'보다 '우리가 무엇을 원하는가'로 질문을 바꿔 보세요. 두 사람의 대화 방식이 다르다는 것을 아는 것만으로도 갈등의 절반이 줄어듭니다.",
        ]),
        S("2027년 두 사람의 흐름", [
            nim(A) + ": " + T.YEAR_GOD[year_god(a)]["love"],
            nim(B) + ": " + T.YEAR_GOD[year_god(b)]["love"],
        ] + year_branch_texts(a)[:1]),
        couple_months(A, B),
        S("관계를 이어 갈지 고민될 때 함께 살펴볼 질문", [
            "관계에 대한 결정은 두 사람의 몫입니다. 아래 질문을 각자 적어 보고 서로 나눠 보세요."
        ], items=[
            "함께 있을 때 나는 편안한가, 아니면 계속 긴장하고 있는가?",
            "서로의 가족·경제·생활 계획을 솔직하게 이야기해 본 적이 있는가?",
            "다툰 뒤 두 사람은 어떻게 화해해 왔는가? 그 방식이 두 사람 모두에게 괜찮은가?",
            "5년 뒤 함께 사는 모습을 떠올렸을 때 어떤 감정이 드는가?",
            "혼자 결정하기 어렵다면 믿을 수 있는 가족, 친구, 상담 전문가와 이야기해 보았는가?",
        ]),
        element_section(A),
        element_section(B),
    ]


def r_move(A):
    a = A["a"]
    yg = T.YEAR_GOD[year_god(a)]
    months = best_months(a, "move", 4)
    doc = a["groups"][4]
    return [
        person_header(A),
        S("타고난 이동·주거 기운", [
            T.YEOKMA if a["yeokma"] else T.NO_YEOKMA,
            ("사주에 문서와 집을 뜻하는 인성의 기운이 뚜렷해 계약·문서 운이 좋은 편입니다." if doc >= 2
             else "사주에 문서를 뜻하는 인성의 기운이 약한 편이라, 계약서와 등기 서류를 특히 꼼꼼히 확인하는 습관이 필요합니다."),
            T.DAY_MASTER[a["day_stem"]]["money"],
        ]),
        year_section(A, "move", "2027년 정미년 이사·부동산 흐름"),
        S("나에게 맞는 방향과 환경", [
            "도움이 되는 기운은 " + T.ELEMENT[a["lucky"]]["name"] + "이며, 좋은 방향은 " + T.ELEMENT[a["lucky"]]["direction"] + "입니다.",
            "방향은 지금 사는 곳을 기준으로 봅니다. 방향이 맞지 않더라도 생활 환경, 출퇴근, 예산이 더 중요한 판단 기준입니다.",
        ], items=lucky_items(a)),
        S("계약·이사 시기", [
            ("2027년에는 " + ", ".join(months) + "에 계약과 이동의 흐름이 좋습니다.") if months
            else "2027년에는 특별히 두드러진 달보다 준비가 된 시점이 가장 좋은 때입니다.",
            yg["move"],
        ]),
        month_table(a, "move", "2027년 월별 이사·계약 흐름"),
        S("계약 전 체크리스트", ["사주의 흐름과 별개로 아래 사항은 반드시 직접 확인하세요."], items=[
            "등기부등본의 소유자, 근저당, 압류 여부",
            "전입신고·확정일자 가능 여부와 보증금 보호 방법",
            "대출 조건과 매달 갚을 금액이 생활비에 부담되지 않는지",
            "주변 시세를 두 곳 이상에서 비교했는지",
            "중요한 계약은 공인중개사·법무사 등 전문가와 함께 확인했는지",
        ]),
    ]


def fields_for(a):
    e = [a["lucky"], a["dm_el"]]
    out = []
    for i in e:
        if T.ELEMENT[i]["fields"] not in out:
            out.append(T.ELEMENT[i]["fields"])
    return out


def r_business(A):
    a = A["a"]
    dm = T.DAY_MASTER[a["day_stem"]]
    g = T.GROUP[a["dominant"]]
    money_star = a["groups"][2]
    make_star = a["groups"][1]
    return [
        person_header(A),
        S("타고난 재물 성향", [dm["money"], g["money"],
                           ("재물을 뜻하는 재성이 뚜렷해 돈의 흐름을 읽는 감각이 있습니다." if money_star >= 2
                            else "재성이 두드러지지 않아 큰 한 방보다 꾸준한 구조를 만드는 편이 재물을 지킵니다."),
                           ("재능과 결과물을 만드는 식상의 기운이 있어 내 기술·콘텐츠로 버는 사업이 잘 맞습니다." if make_star >= 2
                            else "식상의 기운이 약한 편이라 직접 만드는 일보다 관리·유통·협업형 사업이 부담이 적습니다.")]),
        S("사업 적성", [dm["work"], g["work"]], items=["잘 맞는 분야: " + f for f in fields_for(a)]),
        year_section(A, "money", "2027년 정미년 재물 흐름"),
        S("2027년 사업·일의 흐름", [T.YEAR_GOD[year_god(a)]["work"]]),
        month_table(a, "money", "2027년 월별 재물 흐름"),
        element_section(A),
        S("재물을 지키는 원칙", ["사주 흐름과 별개로 아래 원칙은 사업과 재물을 지키는 기본입니다."], items=[
            "수입이 생기면 일정 비율을 먼저 떼어 두기",
            "동업·돈거래는 반드시 문서로 남기기",
            "큰 투자는 한 번에 결정하지 말고 나눠서 판단하기",
            "세금·법률 문제는 세무사·변호사 등 전문가와 상의하기",
        ]),
    ]


STUDY_STYLE = [
    "목(木) 일간은 큰 목표와 계획표가 있을 때 힘을 냅니다. 한 과목을 끝까지 파고드는 방식이 잘 맞습니다.",
    "화(火) 일간은 흥미가 생기면 폭발적으로 집중합니다. 짧게 여러 번, 설명하며 공부하는 방식이 좋습니다.",
    "토(土) 일간은 반복과 복습에 강합니다. 매일 같은 시간, 같은 장소에서 공부하는 습관이 결과를 만듭니다.",
    "금(金) 일간은 정리와 분석에 강합니다. 오답 노트와 요약 정리가 가장 큰 무기입니다.",
    "수(水) 일간은 이해력과 응용력이 좋습니다. 원리를 먼저 이해하고 문제를 넓게 풀어 보는 방식이 맞습니다.",
]


def r_study(A):
    a = A["a"]
    g = T.GROUP[a["dominant"]]
    return [
        person_header(A),
        S("타고난 공부 방식", [STUDY_STYLE[a["dm_el"]], g["study"]]),
        S("적성과 진로 방향", [T.DAY_MASTER[a["day_stem"]]["work"]], items=["잘 맞는 분야: " + f for f in fields_for(a)]),
        year_section(A, "study", "2027년 정미년 학업·진로 흐름"),
        month_table(a, "study", "2027년 월별 학업 흐름"),
        element_section(A),
        S("진로를 고를 때", ["사주는 타고난 경향을 보여 줄 뿐, 진로를 정해 주지 않습니다. 좋아하는 것, 잘하는 것, 오래 해도 지치지 않는 것을 함께 적어 보고, 풀이에서 나온 적성과 겹치는 부분을 먼저 시도해 보세요."]),
    ]


def r_job(A):
    a = A["a"]
    dm = T.DAY_MASTER[a["day_stem"]]
    g = T.GROUP[a["dominant"]]
    org = a["groups"][3]
    free = a["groups"][1]
    if org >= free + 1:
        style = "관성의 기운이 식상보다 강해 체계가 있는 조직, 직함과 역할이 분명한 자리에서 능력이 잘 드러나는 '조직형'입니다."
    elif free >= org + 1:
        style = "식상의 기운이 관성보다 강해 자율성과 재량이 있는 일, 내 이름과 결과물로 평가받는 일이 잘 맞는 '전문·자유형'입니다."
    else:
        style = "관성과 식상의 기운이 비슷해 조직 안에서 전문성을 발휘하는 자리, 예를 들어 전문직이나 기술직이 잘 맞습니다."
    return [
        person_header(A),
        S("나에게 맞는 일의 방식", [style, dm["work"], g["work"]]),
        S("잘 맞는 직업 분야", ["도움이 되는 기운과 타고난 기운을 함께 고려한 분야입니다."], items=fields_for(a)),
        year_section(A, "work", "2027년 정미년 취업·직업 흐름"),
        month_table(a, "work", "2027년 월별 취업·직업 흐름"),
        element_section(A),
        S("취업·이직 준비 조언", [
            ("2027년에는 " + ", ".join(best_months(a, "work", 4)) + "에 지원·면접 등 중요한 일정을 잡아 보세요.") if best_months(a, "work") else "",
            "지원서를 쓸 때는 풀이에 나온 나의 강점을 구체적인 경험과 연결해서 쓰면 설득력이 커집니다.",
        ]),
    ]


BUILDERS = {
    "love-first": r_love_first, "love": r_love, "match": r_match, "relation": r_relation,
    "move": r_move, "business": r_business, "study": r_study, "job": r_job,
}


def build_person(info):
    """info: 주문 시 저장한 정보(dict) → 계산 결과를 붙인 사람 정보"""
    import datetime
    solar = datetime.date.fromisoformat(info["solar"])
    hour = info.get("hour")
    minute = info.get("minute") or 0
    a = saju.compute(solar, hour, minute)
    return {"name": info["name"], "gender": info.get("gender", ""), "a": a, "info": info}


def birth_label(info):
    cal = info.get("cal", "solar")
    if cal == "lunar":
        s = "음력 " + info["input_date"] + (" (윤달)" if info.get("leap") else "") + " → 양력 " + info["solar"]
    else:
        s = "양력 " + info["solar"]
    if info.get("hour") is None:
        s += " · 시간 모름"
    else:
        s += " · %02d:%02d" % (info["hour"], info.get("minute") or 0)
    return s


def generate(product_id, person_a, person_b=None):
    product = PRODUCT_BY_ID[product_id]
    A = build_person(person_a)
    B = build_person(person_b) if product["partner"] and person_b else None
    if product["partner"] and not B:
        raise ValueError("상대방 정보가 필요합니다.")
    sections = BUILDERS[product_id](A, B) if B else BUILDERS[product_id](A)
    people = []
    for P in ([A, B] if B else [A]):
        people.append({
            "name": P["name"],
            "gender": P["gender"],
            "birth": birth_label(P["info"]),
            "animal": P["a"]["animal"] + "띠",
            "day_master": T.DAY_MASTER[P["a"]["day_stem"]]["title"],
            "chart": saju.chart_view(P["a"]),
        })
    return {
        "product": {"id": product["id"], "name": product["name"], "price": product["price"]},
        "people": people,
        "sections": sections,
        "disclaimer": T.DISCLAIMER,
    }
