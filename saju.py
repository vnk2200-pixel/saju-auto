# -*- coding: utf-8 -*-
"""
러브 오라클 사주 계산 엔진 (외부 설치 없이 파이썬 기본 기능만 사용)

- 년주·월주: 태양 황경으로 계산한 실제 절기(입춘·경칩 ...) 기준
- 일주: 율리우스일 기준 60갑자
- 시주: 서울(동경 127도) 지방평균시 기준. 자시는 약 23:32부터 시작
- 음력 생일은 lunar.py(한국천문연구원 데이터)로 양력 변환
"""

import math
import datetime

from lunar import KoreanLunarCalendar

STEMS_H = "甲乙丙丁戊己庚辛壬癸"
STEMS_K = ["갑", "을", "병", "정", "무", "기", "경", "신", "임", "계"]
BRANCH_H = "子丑寅卯辰巳午未申酉戌亥"
BRANCH_K = ["자", "축", "인", "묘", "진", "사", "오", "미", "신", "유", "술", "해"]
ANIMALS = ["쥐", "소", "호랑이", "토끼", "용", "뱀", "말", "양", "원숭이", "닭", "개", "돼지"]

# 오행: 0 목, 1 화, 2 토, 3 금, 4 수
EL_NAME = ["목", "화", "토", "금", "수"]
EL_HANJA = ["木", "火", "土", "金", "水"]
STEM_EL = [0, 0, 1, 1, 2, 2, 3, 3, 4, 4]
BRANCH_EL = [4, 2, 0, 0, 2, 1, 1, 2, 3, 3, 2, 4]
# 지지의 본기(대표 지장간)
BRANCH_MAIN_STEM = [9, 5, 0, 1, 4, 2, 3, 5, 6, 7, 4, 8]

TEN_GODS = ["비견", "겁재", "식신", "상관", "편재", "정재", "편관", "정관", "편인", "정인"]
GROUPS = ["비겁", "식상", "재성", "관성", "인성"]

SEOUL_LONGITUDE = 127.0


# ------------------------------------------------------------------
# 천문 계산
# ------------------------------------------------------------------

def julian_day(y, m, d, hour=0.0):
    """그레고리력 날짜(UT) → 율리우스일"""
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + hour / 24.0 + b - 1524.5


def sun_longitude(jd):
    """태양 겉보기 황경(도). 오차 약 0.01도(절기 시각 기준 약 15분 이내)"""
    t = (jd - 2451545.0) / 36525.0
    l0 = 280.46646 + 36000.76983 * t + 0.0003032 * t * t
    m = math.radians(357.52911 + 35999.05029 * t - 0.0001537 * t * t)
    c = ((1.914602 - 0.004817 * t - 0.000014 * t * t) * math.sin(m)
         + (0.019993 - 0.000101 * t) * math.sin(2 * m)
         + 0.000289 * math.sin(3 * m))
    omega = math.radians(125.04 - 1934.136 * t)
    lam = l0 + c - 0.00569 - 0.00478 * math.sin(omega)
    return lam % 360.0


def korea_utc_offset(dt):
    """한국 표준시(시간). 1954-03-21 ~ 1961-08-09 는 UTC+8:30, 1987·1988 여름시간 반영"""
    d = dt.date()
    offset = 9.0
    if datetime.date(1954, 3, 21) <= d < datetime.date(1961, 8, 10):
        offset = 8.5
    if datetime.date(1987, 5, 10) <= d < datetime.date(1987, 10, 11):
        offset += 1
    if datetime.date(1988, 5, 8) <= d < datetime.date(1988, 10, 9):
        offset += 1
    return offset


# ------------------------------------------------------------------
# 입력 처리
# ------------------------------------------------------------------

class InputError(ValueError):
    pass


def to_solar(cal, y, m, d, leap=False):
    """cal: 'solar' 또는 'lunar'. 양력 date 반환"""
    if cal == "lunar":
        c = KoreanLunarCalendar()
        ok = c.setLunarDate(y, m, d, bool(leap))
        if not ok:
            raise InputError("음력 날짜를 확인해 주세요. (윤달 여부 포함)")
        return datetime.date(c.solarYear, c.solarMonth, c.solarDay)
    try:
        return datetime.date(y, m, d)
    except ValueError:
        raise InputError("생년월일을 확인해 주세요.")


# ------------------------------------------------------------------
# 사주 계산
# ------------------------------------------------------------------

def ten_god(day_stem, other_stem):
    d = (STEM_EL[other_stem] - STEM_EL[day_stem]) % 5
    base = [0, 2, 4, 6, 8][d]
    same = (day_stem % 2) == (other_stem % 2)
    return base if same else base + 1


def ganji_name(stem, branch):
    return STEMS_K[stem] + BRANCH_K[branch]


def compute(solar_date, hour=None, minute=0):
    """
    solar_date: 양력 date
    hour/minute: 한국 시계 기준 출생시각. 모르면 hour=None
    """
    y, m, d = solar_date.year, solar_date.month, solar_date.day
    if not (1900 <= y <= 2049):
        raise InputError("1900년~2049년 사이 출생만 계산할 수 있습니다.")

    known_time = hour is not None
    h = hour if known_time else 12
    mi = minute if known_time else 0

    civil = datetime.datetime(y, m, d, h, mi)
    offset = korea_utc_offset(civil)
    ut = civil - datetime.timedelta(hours=offset)
    jd = julian_day(ut.year, ut.month, ut.day, ut.hour + ut.minute / 60.0)
    lam = sun_longitude(jd)

    # 월지: 입춘(315도)부터 30도마다 인·묘·진...
    month_idx = int(((lam - 315.0) % 360.0) // 30.0)  # 0=인월
    month_branch = (month_idx + 2) % 12

    year = y
    if m <= 2 and month_idx >= 10:  # 입춘 이전의 자·축월
        year -= 1
    year_stem = (year - 4) % 10
    year_branch = (year - 4) % 12
    month_stem = ((year_stem % 5) * 2 + 2 + month_idx) % 10

    # 서울 지방평균시
    lmt = ut + datetime.timedelta(hours=SEOUL_LONGITUDE / 15.0)
    day_date = lmt.date()
    if known_time and lmt.hour >= 23:  # 자시부터 다음 날로 봄
        day_date = day_date + datetime.timedelta(days=1)
    if not known_time:
        day_date = solar_date
    n = (day_date - datetime.date(2000, 1, 1)).days  # 2000-01-01 = 戊午일
    day_stem = (4 + n) % 10
    day_branch = (6 + n) % 12

    pillars = {
        "year": (year_stem, year_branch),
        "month": (month_stem, month_branch),
        "day": (day_stem, day_branch),
        "hour": None,
    }
    if known_time:
        hb = ((lmt.hour + 1) // 2) % 12
        hs = ((day_stem % 5) * 2 + hb) % 10
        pillars["hour"] = (hs, hb)

    return analyze(pillars, known_time)


def analyze(pillars, known_time):
    ds = pillars["day"][0]
    count = [0.0] * 5
    groups = [0.0] * 5
    gods = {}
    weights = {"year": (1, 1), "month": (1, 2.0), "day": (0, 1.2), "hour": (1, 1)}

    for key, p in pillars.items():
        if not p:
            continue
        s, b = p
        ws, wb = weights[key]
        count[STEM_EL[s]] += 1
        count[BRANCH_EL[b]] += 1
        stem_god = None if key == "day" else ten_god(ds, s)
        branch_god = ten_god(ds, BRANCH_MAIN_STEM[b])
        gods[key] = (stem_god, branch_god)
        if stem_god is not None:
            groups[stem_god // 2] += ws
        groups[branch_god // 2] += wb

    support = groups[0] + groups[4]
    total = sum(groups) or 1
    ratio = support / total
    if ratio >= 0.55:
        strength = "강"
    elif ratio <= 0.38:
        strength = "약"
    else:
        strength = "중"

    dm_el = STEM_EL[ds]
    if strength == "약":
        favorable = [(dm_el + 4) % 5, dm_el]           # 인성, 비겁
    elif strength == "강":
        favorable = [(dm_el + 1) % 5, (dm_el + 2) % 5, (dm_el + 3) % 5]  # 식상, 재, 관
    else:
        favorable = [0, 1, 2, 3, 4]
    lucky = min(favorable, key=lambda e: (count[e], e))
    weakest = min(range(5), key=lambda e: (count[e], e))
    strongest = max(range(5), key=lambda e: (count[e], -e))
    dominant = max(range(5), key=lambda g: (groups[g], -g))

    yb, db = pillars["year"][1], pillars["day"][1]
    return {
        "pillars": pillars,
        "known_time": known_time,
        "day_stem": ds,
        "day_branch": db,
        "dm_el": dm_el,
        "count": count,
        "groups": groups,
        "gods": gods,
        "strength": strength,
        "lucky": lucky,
        "weakest": weakest,
        "strongest": strongest,
        "dominant": dominant,
        "dohwa": has_star(pillars, DOHWA, yb, db),
        "yeokma": has_star(pillars, YEOKMA, yb, db),
        "spouse_god": gods["day"][1],
        "animal": ANIMALS[yb],
        "year_branch": yb,
    }


# 삼합 그룹 기준 도화·역마
def _trio(b):
    return {8: 0, 0: 0, 4: 0, 2: 1, 6: 1, 10: 1, 5: 2, 9: 2, 1: 2, 11: 3, 3: 3, 7: 3}[b]


DOHWA = [9, 3, 6, 0]   # 신자진→유, 인오술→묘, 사유축→오, 해묘미→자
YEOKMA = [2, 8, 11, 5]  # 신자진→인, 인오술→신, 사유축→해, 해묘미→사


def has_star(pillars, table, yb, db):
    targets = {table[_trio(yb)], table[_trio(db)]}
    for key, p in pillars.items():
        if p and p[1] in targets and key != "day":
            return True
        if p and key == "day" and p[1] == table[_trio(yb)]:
            return True
    return False


# ------------------------------------------------------------------
# 지지 관계
# ------------------------------------------------------------------

SIX_HAP = {frozenset(x) for x in [(0, 1), (2, 11), (3, 10), (4, 9), (5, 8), (6, 7)]}
CHUNG = {frozenset((i, (i + 6) % 12)) for i in range(12)}
WONJIN = {frozenset(x) for x in [(0, 7), (1, 6), (2, 9), (3, 8), (4, 11), (5, 10)]}
HYEONG = {frozenset(x) for x in [(2, 5), (5, 8), (2, 8), (1, 10), (10, 7), (1, 7), (0, 3)]}
STEM_HAP = {frozenset(x) for x in [(0, 5), (1, 6), (2, 7), (3, 8), (4, 9)]}


def branch_relation(a, b):
    pair = frozenset((a, b))
    if a == b:
        return "같음"
    if pair in SIX_HAP:
        return "합"
    if _trio(a) == _trio(b):
        return "삼합"
    if pair in CHUNG:
        return "충"
    if pair in WONJIN:
        return "원진"
    if pair in HYEONG:
        return "형"
    return ""


def year_pillar_of(year):
    return ((year - 4) % 10, (year - 4) % 12)


def month_pillars_of_year(year):
    """해당 해 인월(2월)부터 축월(다음 해 1월)까지 12개 월주와 대략적 양력 시작일"""
    ys = (year - 4) % 10
    starts = ["2월 4일경", "3월 6일경", "4월 5일경", "5월 6일경", "6월 6일경", "7월 7일경",
              "8월 8일경", "9월 8일경", "10월 8일경", "11월 7일경", "12월 7일경", "1월 6일경"]
    labels = ["2월", "3월", "4월", "5월", "6월", "7월", "8월", "9월", "10월", "11월", "12월", "1월"]
    out = []
    for i in range(12):
        stem = ((ys % 5) * 2 + 2 + i) % 10
        branch = (i + 2) % 12
        out.append({"label": labels[i], "start": starts[i], "stem": stem, "branch": branch})
    return out


def chart_view(a):
    """화면 표시용 명식 데이터"""
    rows = []
    for key, label in (("hour", "시주"), ("day", "일주"), ("month", "월주"), ("year", "년주")):
        p = a["pillars"][key]
        if p:
            sg, bg = a["gods"][key]
            rows.append({
                "label": label,
                "stem": STEMS_H[p[0]], "stem_k": STEMS_K[p[0]], "stem_el": STEM_EL[p[0]],
                "branch": BRANCH_H[p[1]], "branch_k": BRANCH_K[p[1]], "branch_el": BRANCH_EL[p[1]],
                "stem_god": "일간(나)" if key == "day" else TEN_GODS[sg],
                "branch_god": TEN_GODS[bg],
            })
        else:
            rows.append({"label": label, "unknown": True})
    return {
        "rows": rows,
        "elements": [round(c, 1) for c in a["count"]],
        "strength": a["strength"],
    }
