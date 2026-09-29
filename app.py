from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import os
import re
import json
import time
import zlib
import hmac
import base64
import hashlib
import secrets
import datetime
import urllib.request
import urllib.error
import urllib.parse
from urllib.parse import urlparse

import saju
import readings


# ============================================================
# BASIC SETTINGS
# 모든 비밀 값은 Render > Environment(환경변수)에 넣습니다.
# ============================================================

PORT = int(os.environ.get("PORT", "8000"))

# ---------- 한국판: 토스페이먼츠 ----------
# 토스페이먼츠 개발자센터 > API 키 > "API 개별 연동 키"
#   TOSS_CLIENT_KEY : test_ck_... 또는 live_ck_...
#   TOSS_SECRET_KEY : test_sk_... 또는 live_sk_...
TOSS_CLIENT_KEY = os.environ.get("TOSS_CLIENT_KEY", "").strip()
TOSS_SECRET_KEY = os.environ.get("TOSS_SECRET_KEY", "").strip()
TOSS_API_BASE = os.environ.get("TOSS_API_BASE", "https://api.tosspayments.com").strip().rstrip("/")

# ---------- 한국판: 카카오페이 (카카오페이 키가 있으면 카카오페이를 우선 사용) ----------
# 카카오페이 개발자센터 > 내 애플리케이션 > 앱 키
#   KAKAO_SECRET_KEY : 테스트는 "Secret key(dev)", 실제 판매는 "Secret key"
#   KAKAO_CID        : 테스트는 TC0ONETIME, 실제 판매는 계약 후 받은 가맹점 코드
KAKAO_SECRET_KEY = os.environ.get("KAKAO_SECRET_KEY", "").strip()
KAKAO_CID = os.environ.get("KAKAO_CID", "TC0ONETIME").strip()
KAKAO_API_BASE = os.environ.get("KAKAO_API_BASE", "https://open-api.kakaopay.com").strip().rstrip("/")

if KAKAO_SECRET_KEY:
    PAY_PROVIDER = "kakao"
    PAY_TEST_MODE = KAKAO_CID.startswith("TC")
elif TOSS_CLIENT_KEY and TOSS_SECRET_KEY:
    PAY_PROVIDER = "toss"
    PAY_TEST_MODE = TOSS_CLIENT_KEY.startswith("test_")
else:
    PAY_PROVIDER = ""
    PAY_TEST_MODE = False

# 결과 링크 암호화용 비밀 문자열 (아무 긴 문자열. 한번 정하면 바꾸지 마세요)
APP_SECRET = os.environ.get("APP_SECRET", "").strip()
if not APP_SECRET:
    APP_SECRET = KAKAO_SECRET_KEY or TOSS_SECRET_KEY or secrets.token_hex(32)
    print("WARNING: APP_SECRET is not set. Result links may stop working after restart.")

# 사장님 전용 무료 미리보기 비밀번호 (비워 두면 미리보기 기능 꺼짐)
ADMIN_KEY = os.environ.get("ADMIN_KEY", "").strip()

# PayPal credentials - store these in Render Environment Variables
PAYPAL_CLIENT_ID = os.environ.get("PAYPAL_CLIENT_ID", "").strip()
PAYPAL_CLIENT_SECRET = os.environ.get("PAYPAL_CLIENT_SECRET", "").strip()

# live = real payment / sandbox = test payment
PAYPAL_MODE = os.environ.get("PAYPAL_MODE", "live").strip().lower()

# US product
US_PRICE = "20.00"
US_CURRENCY = "USD"
US_PRODUCT_NAME = "Korean Four Pillars Personalized Life Reading"

if PAYPAL_MODE == "sandbox":
    PAYPAL_API_BASE = "https://api-m.sandbox.paypal.com"
else:
    PAYPAL_API_BASE = "https://api-m.paypal.com"


# ============================================================
# PAYPAL FUNCTIONS
# ============================================================

def paypal_access_token():
    if not PAYPAL_CLIENT_ID or not PAYPAL_CLIENT_SECRET:
        raise RuntimeError(
            "PAYPAL_CLIENT_ID or PAYPAL_CLIENT_SECRET is not configured."
        )

    credentials = (
        PAYPAL_CLIENT_ID + ":" + PAYPAL_CLIENT_SECRET
    ).encode("utf-8")

    auth = base64.b64encode(credentials).decode("ascii")

    request = urllib.request.Request(
        PAYPAL_API_BASE + "/v1/oauth2/token",
        data=b"grant_type=client_credentials",
        method="POST",
        headers={
            "Authorization": "Basic " + auth,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(
            response.read().decode("utf-8")
        )

    token = result.get("access_token")

    if not token:
        raise RuntimeError(
            "PayPal access token was not returned."
        )

    return token


def paypal_request(path, method="GET", data=None):
    token = paypal_access_token()

    body = None

    if data is not None:
        body = json.dumps(data).encode("utf-8")

    request = urllib.request.Request(
        PAYPAL_API_BASE + path,
        data=body,
        method=method,
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=30
        ) as response:

            text = response.read().decode("utf-8")

            if not text:
                return {}

            return json.loads(text)

    except urllib.error.HTTPError as error:
        error_text = error.read().decode(
            "utf-8",
            errors="replace"
        )

        raise RuntimeError(
            "PayPal API error "
            + str(error.code)
            + ": "
            + error_text
        )


def create_paypal_order():
    order_data = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "description": US_PRODUCT_NAME,
                "amount": {
                    "currency_code": US_CURRENCY,
                    "value": US_PRICE,
                },
            }
        ],
    }

    return paypal_request(
        "/v2/checkout/orders",
        method="POST",
        data=order_data,
    )


def capture_paypal_order(order_id):
    if not order_id:
        raise RuntimeError(
            "PayPal order ID is missing."
        )

    return paypal_request(
        "/v2/checkout/orders/"
        + order_id
        + "/capture",
        method="POST",
        data={},
    )


def verify_capture(capture_result):
    if capture_result.get("status") != "COMPLETED":
        return False

    purchase_units = capture_result.get(
        "purchase_units",
        []
    )

    if not purchase_units:
        return False

    captures = (
        purchase_units[0]
        .get("payments", {})
        .get("captures", [])
    )

    if not captures:
        return False

    capture = captures[0]

    if capture.get("status") != "COMPLETED":
        return False

    amount = capture.get("amount", {})

    if amount.get("currency_code") != US_CURRENCY:
        return False

    if amount.get("value") != US_PRICE:
        return False

    return True


# ============================================================
# 한국판: 암호화된 주문·결과 링크
# (서버에 파일을 저장하지 않아도 결과를 다시 볼 수 있게 함)
# ============================================================

def _key(label):
    return hashlib.sha256((label + ":" + APP_SECRET).encode("utf-8")).digest()


def _stream(key, nonce, length):
    out = bytearray()
    counter = 0
    while len(out) < length:
        out += hashlib.sha256(key + nonce + counter.to_bytes(4, "big")).digest()
        counter += 1
    return bytes(out[:length])


def seal(obj):
    raw = zlib.compress(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), 9)
    nonce = os.urandom(12)
    ct = bytes(a ^ b for a, b in zip(raw, _stream(_key("enc"), nonce, len(raw))))
    tag = hmac.new(_key("mac"), b"v1" + nonce + ct, hashlib.sha256).digest()[:16]
    return base64.urlsafe_b64encode(nonce + ct + tag).decode("ascii").rstrip("=")


def unseal(token):
    try:
        data = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    except Exception:
        return None
    if len(data) < 12 + 16 + 1:
        return None
    nonce, ct, tag = data[:12], data[12:-16], data[-16:]
    good = hmac.new(_key("mac"), b"v1" + nonce + ct, hashlib.sha256).digest()[:16]
    if not hmac.compare_digest(tag, good):
        return None
    raw = bytes(a ^ b for a, b in zip(ct, _stream(_key("enc"), nonce, len(ct))))
    try:
        return json.loads(zlib.decompress(raw).decode("utf-8"))
    except Exception:
        return None


# ============================================================
# 한국판: 입력 확인
# ============================================================

class BadInput(ValueError):
    pass


def parse_date(text):
    digits = re.sub(r"[^0-9]", " ", str(text or "")).split()
    if len(digits) == 1 and len(digits[0]) == 8:
        s = digits[0]
        digits = [s[:4], s[4:6], s[6:]]
    if len(digits) != 3:
        raise BadInput("생년월일을 예: 1970-10-01 형식으로 입력해 주세요.")
    y, m, d = (int(x) for x in digits)
    if y < 100:
        y += 1900 if y > 30 else 2000
    return y, m, d


def parse_time(text):
    t = str(text or "").strip()
    if not t or t in ("모름", "unknown"):
        return None, 0
    nums = re.findall(r"\d+", t)
    if not nums:
        raise BadInput("출생시간을 예: 14:30 형식으로 입력하거나 '모름'을 선택해 주세요.")
    if len(nums) == 1 and len(nums[0]) in (3, 4):
        nums = [nums[0][:-2], nums[0][-2:]]
    h = int(nums[0])
    mi = int(nums[1]) if len(nums) > 1 else 0
    if "오후" in t and h < 12:
        h += 12
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        raise BadInput("출생시간을 확인해 주세요.")
    return h, mi


def clean_person(raw, label):
    if not isinstance(raw, dict):
        raise BadInput(label + " 정보를 입력해 주세요.")
    name = re.sub(r"\s+", " ", str(raw.get("name", ""))).strip()[:20]
    gender = str(raw.get("gender", "")).strip()
    cal = "lunar" if str(raw.get("cal", "")).strip() in ("lunar", "음력") else "solar"
    leap = bool(raw.get("leap"))
    if not name:
        raise BadInput(label + " 성함을 입력해 주세요.")
    if gender not in ("남성", "여성"):
        raise BadInput(label + " 성별을 선택해 주세요.")
    y, m, d = parse_date(raw.get("birth"))
    hour, minute = parse_time(raw.get("time"))
    try:
        solar = saju.to_solar(cal, y, m, d, leap)
        saju.compute(solar, hour, minute)
    except (saju.InputError, ValueError) as error:
        raise BadInput(label + " " + str(error))
    return {
        "name": name,
        "gender": gender,
        "cal": cal,
        "leap": leap and cal == "lunar",
        "input_date": "%04d-%02d-%02d" % (y, m, d),
        "solar": solar.isoformat(),
        "hour": hour,
        "minute": minute,
    }


def clean_order(data):
    product = readings.PRODUCT_BY_ID.get(str(data.get("product", "")))
    if not product:
        raise BadInput("상품을 선택해 주세요.")
    if data.get("agree") is not True:
        raise BadInput("이용조건 및 취소·환불 안내에 동의해 주세요.")
    person_a = clean_person(data.get("person"), "본인")
    person_b = clean_person(data.get("partner"), "상대방") if product["partner"] else None
    return product, person_a, person_b


# ============================================================
# 한국판: 토스페이먼츠
# ============================================================

def toss_request(path, method="GET", data=None):
    if not TOSS_SECRET_KEY:
        raise RuntimeError("TOSS_SECRET_KEY is not configured.")
    auth = base64.b64encode((TOSS_SECRET_KEY + ":").encode("utf-8")).decode("ascii")
    body = json.dumps(data).encode("utf-8") if data is not None else None
    request = urllib.request.Request(
        TOSS_API_BASE + path,
        data=body,
        method=method,
        headers={"Authorization": "Basic " + auth, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as error:
        try:
            return error.code, json.loads(error.read().decode("utf-8") or "{}")
        except Exception:
            return error.code, {"code": "HTTP_" + str(error.code), "message": "결제사 응답 오류"}


def payment_ok(payment, order_id, amount):
    return (
        payment.get("status") == "DONE"
        and payment.get("orderId") == order_id
        and int(payment.get("totalAmount", -1)) == int(amount)
    )


# ============================================================
# 한국판: 카카오페이 온라인 단건 결제
# ============================================================

def kakao_request(path, data):
    if not KAKAO_SECRET_KEY:
        raise RuntimeError("KAKAO_SECRET_KEY is not configured.")
    request = urllib.request.Request(
        KAKAO_API_BASE + path,
        data=json.dumps(data).encode("utf-8"),
        method="POST",
        headers={"Authorization": "SECRET_KEY " + KAKAO_SECRET_KEY, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as error:
        try:
            return error.code, json.loads(error.read().decode("utf-8") or "{}")
        except Exception:
            return error.code, {"error_code": error.code, "error_message": "결제사 응답 오류"}


def kakao_message(payment, default):
    extras = payment.get("extras") or {}
    return extras.get("method_result_message") or payment.get("error_message") or payment.get("msg") or default


def kakao_paid_ok(info, order_id, amount):
    total = (info.get("amount") or {}).get("total")
    if total is None:
        total = (info.get("cancel_available_amount") or {}).get("total")
    return info.get("partner_order_id") == order_id and total is not None and int(total) == int(amount)


# 결제 준비 때 받은 tid 를 잠시 기억 (서버가 재시작되면 브라우저가 보관한 값을 사용)
_kakao_tids = {}


def remember_tid(order_id, tid):
    now = time.time()
    for key in [k for k, v in _kakao_tids.items() if now - v[0] > 3600]:
        _kakao_tids.pop(key, None)
    _kakao_tids[order_id] = (now, tid)


_status_cache = {}


def payment_still_valid(payment_key):
    """결과를 다시 볼 때 환불·취소된 결제인지 확인 (10분 캐시, 결제사 오류 시에는 허용)"""
    now = time.time()
    hit = _status_cache.get(payment_key)
    if hit and now - hit[0] < 600:
        return hit[1]
    valid = True
    try:
        if payment_key.startswith("kakao:"):
            _, cid, tid = payment_key.split(":", 2)
            status, info = kakao_request("/online/v1/payment/order", {"cid": cid, "tid": tid})
            if status == 200 and info.get("status") in ("CANCEL_PAYMENT", "PART_CANCEL_PAYMENT"):
                valid = False
        else:
            status, payment = toss_request("/v1/payments/" + urllib.parse.quote(payment_key, safe=""))
            if status == 200 and payment.get("status") in ("CANCELED", "PARTIAL_CANCELED", "ABORTED", "EXPIRED"):
                valid = False
    except Exception as error:
        print("PAYMENT STATUS CHECK ERROR:", str(error))
    _status_cache[payment_key] = (now, valid)
    return valid


def make_result(sealed_order, payment_key="", preview=False):
    result_token = seal({
        "t": "result",
        "pid": sealed_order["pid"],
        "oid": sealed_order.get("oid", ""),
        "amt": sealed_order.get("amt", 0),
        "pk": payment_key,
        "preview": preview,
        "A": sealed_order["A"],
        "B": sealed_order.get("B"),
    })
    reading = readings.generate(sealed_order["pid"], sealed_order["A"], sealed_order.get("B"))
    reading["order_id"] = sealed_order.get("oid", "")
    reading["preview"] = preview
    return result_token, reading


# ============================================================
# HTTP SERVER
# ============================================================

KR_PAGES = ("/kr/success/", "/kr/r/", "/kr/kakao/ok/")


class SajuHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        # 결과 링크(암호문)는 로그에 남기지 않습니다.
        path = urlparse(self.path).path
        if path.startswith(KR_PAGES):
            path = path.split("/")[1] + "/" + path.split("/")[2] + "/…"
        print("%s %s %s" % (self.command, path, args[1] if len(args) > 1 else ""))

    def send_no_cache_headers(self):
        self.send_header(
            "Cache-Control",
            "no-store, no-cache, must-revalidate, max-age=0",
        )
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")

    def send_security_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")

    def send_html(self, filename):
        try:
            with open(filename, "rb") as file:
                content = file.read()

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_no_cache_headers()
            self.send_security_headers()
            self.end_headers()
            self.wfile.write(content)

        except FileNotFoundError:
            self.send_text("Page not found", 404)

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_no_cache_headers()
        self.send_security_headers()
        self.end_headers()
        self.wfile.write(body)

    def send_text(self, text, status=200):
        body = text.encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_no_cache_headers()
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))

        if length <= 0:
            return {}

        if length > 50000:
            raise ValueError("Request too large")

        raw_data = self.rfile.read(length)

        if not raw_data:
            return {}

        return json.loads(raw_data.decode("utf-8"))

    def do_HEAD(self):
        self.send_response(200)
        self.send_no_cache_headers()
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path

        # ----------------------------------------------------
        # US PAGE
        # ----------------------------------------------------

        if path in ("/us", "/us/", "/index-us.html"):
            self.send_html("index-us.html")
            return

        # ----------------------------------------------------
        # KOREAN PAGES
        # ----------------------------------------------------

        if path in ("/", "/index.html"):
            self.send_html("index.html")
            return

        if path.startswith(KR_PAGES) or path == "/kr/fail":
            self.send_html("result.html")
            return

        if path == "/api/kr/config":
            self.send_json({
                "status": "success",
                "ready": bool(PAY_PROVIDER),
                "provider": PAY_PROVIDER,
                "test_mode": PAY_TEST_MODE,
                "client_key": TOSS_CLIENT_KEY if PAY_PROVIDER == "toss" else "",
                "preview": bool(ADMIN_KEY),
                "products": readings.PRODUCTS,
            })
            return

        # ----------------------------------------------------
        # PAYPAL CONFIG
        # ----------------------------------------------------

        if path == "/api/paypal-config":
            if not PAYPAL_CLIENT_ID:
                self.send_json(
                    {
                        "status": "error",
                        "message": "PAYPAL_CLIENT_ID is not configured.",
                    },
                    500,
                )
                return

            self.send_json(
                {
                    "status": "success",
                    "client_id": PAYPAL_CLIENT_ID,
                    "price": US_PRICE,
                    "currency": US_CURRENCY,
                    "mode": PAYPAL_MODE,
                }
            )
            return

        # ----------------------------------------------------
        # HEALTH CHECK
        # ----------------------------------------------------

        if path == "/api/health":
            self.send_json(
                {
                    "status": "success",
                    "service": "saju-auto",
                    "kr_payment_provider": PAY_PROVIDER or "none",
                    "kr_test_mode": PAY_TEST_MODE,
                    "app_secret_set": bool(os.environ.get("APP_SECRET", "").strip()),
                    "us_price": US_PRICE,
                    "currency": US_CURRENCY,
                    "paypal_mode": PAYPAL_MODE,
                    "paypal_configured": bool(PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET),
                }
            )
            return

        self.send_text("Page not found", 404)

    def do_POST(self):
        path = urlparse(self.path).path

        try:
            data = self.read_json()
            if not isinstance(data, dict):
                raise ValueError("not an object")

        except Exception:
            self.send_json(
                {
                    "status": "error",
                    "message": "Invalid JSON request.",
                },
                400,
            )
            return

        if path.startswith("/api/kr/"):
            self.handle_kr(path, data)
            return

        # ----------------------------------------------------
        # CREATE PAYPAL ORDER
        # ----------------------------------------------------

        if path == "/api/paypal/create-order":
            try:
                order = create_paypal_order()

                order_id = order.get("id")

                if not order_id:
                    raise RuntimeError("PayPal did not return an order ID.")

                self.send_json(
                    {
                        "status": "success",
                        "order_id": order_id,
                        "paypal_status": order.get("status"),
                    }
                )

            except Exception as error:
                print("CREATE ORDER ERROR:", str(error))

                self.send_json(
                    {
                        "status": "error",
                        "message": str(error),
                    },
                    500,
                )

            return

        # ----------------------------------------------------
        # CAPTURE + VERIFY PAYPAL PAYMENT
        # ----------------------------------------------------

        if path == "/api/paypal/capture-order":
            order_id = str(data.get("order_id", "")).strip()

            if not order_id:
                self.send_json(
                    {
                        "status": "error",
                        "message": "PayPal order ID is required.",
                    },
                    400,
                )
                return

            try:
                capture_result = capture_paypal_order(order_id)

                paid = verify_capture(capture_result)

                if not paid:
                    self.send_json(
                        {
                            "status": "error",
                            "paid": False,
                            "message": "Payment could not be verified.",
                        },
                        400,
                    )
                    return

                capture_id = ""

                try:
                    capture_id = (
                        capture_result["purchase_units"][0]["payments"]["captures"][0].get("id", "")
                    )
                except Exception:
                    capture_id = ""

                self.send_json(
                    {
                        "status": "success",
                        "paid": True,
                        "order_id": order_id,
                        "capture_id": capture_id,
                        "price": US_PRICE,
                        "currency": US_CURRENCY,
                        "message": "Payment verified successfully.",
                    }
                )

            except Exception as error:
                print("CAPTURE ERROR:", str(error))

                self.send_json(
                    {
                        "status": "error",
                        "paid": False,
                        "message": str(error),
                    },
                    500,
                )

            return

        # ----------------------------------------------------
        # US CUSTOMER DATA VALIDATION
        # ----------------------------------------------------

        if path == "/api/us-reading":
            birth = str(data.get("birth", "")).strip()
            birth_time = str(data.get("time", "")).strip()
            place = str(data.get("place", "")).strip()
            payment_verified = data.get("payment_verified") is True

            if not birth:
                self.send_json({"status": "error", "message": "Date of birth is required."}, 400)
                return

            if not place:
                self.send_json({"status": "error", "message": "Place of birth is required."}, 400)
                return

            if not payment_verified:
                self.send_json({"status": "error", "message": "Verified payment is required."}, 403)
                return

            self.send_json(
                {
                    "status": "success",
                    "birth": birth,
                    "time": birth_time,
                    "place": place,
                    "price": US_PRICE,
                    "currency": US_CURRENCY,
                }
            )
            return

        self.send_json(
            {
                "status": "error",
                "message": "API endpoint not found.",
            },
            404,
        )

    # --------------------------------------------------------
    # 한국판 API
    # --------------------------------------------------------

    def kr_error(self, message, status=400, code=""):
        self.send_json({"status": "error", "message": message, "code": code}, status)

    def handle_kr(self, path, data):
        try:
            if path == "/api/kr/order":
                self.kr_order(data)
            elif path == "/api/kr/confirm":
                self.kr_confirm(data)
            elif path == "/api/kr/result":
                self.kr_result(data)
            elif path == "/api/kr/kakao-approve":
                self.kr_kakao_approve(data)
            elif path == "/api/kr/preview":
                self.kr_preview(data)
            else:
                self.kr_error("API endpoint not found.", 404)
        except BadInput as error:
            self.kr_error(str(error), 400, "BAD_INPUT")
        except Exception as error:
            print("KR ERROR:", path, repr(error))
            self.kr_error("일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.", 500, "SERVER_ERROR")

    def site_origin(self, data):
        """결제 후 돌아올 주소. 브라우저가 알려 준 주소가 실제 접속 주소와 같을 때만 사용"""
        host = (self.headers.get("X-Forwarded-Host") or self.headers.get("Host") or "").strip()
        given = str(data.get("origin", "")).strip().rstrip("/")
        parsed = urlparse(given)
        if parsed.scheme in ("http", "https") and parsed.netloc == host:
            return parsed.scheme + "://" + parsed.netloc
        proto = (self.headers.get("X-Forwarded-Proto") or "https").split(",")[0].strip()
        return proto + "://" + host

    def kr_order(self, data):
        if not PAY_PROVIDER:
            self.kr_error("현재 결제 서비스 준비 중입니다. 잠시 후 다시 이용해 주세요.", 503, "NOT_READY")
            return
        product, person_a, person_b = clean_order(data)
        order_id = "LO" + datetime.datetime.utcnow().strftime("%y%m%d%H%M%S") + secrets.token_hex(5)
        token = seal({
            "t": "order",
            "oid": order_id,
            "pid": product["id"],
            "amt": product["price"],
            "A": person_a,
            "B": person_b,
            "ts": int(time.time()),
        })

        if PAY_PROVIDER == "kakao":
            origin = self.site_origin(data)
            status, ready = kakao_request("/online/v1/payment/ready", {
                "cid": KAKAO_CID,
                "partner_order_id": order_id,
                "partner_user_id": "guest",
                "item_name": product["name"],
                "quantity": 1,
                "total_amount": product["price"],
                "tax_free_amount": 0,
                "approval_url": origin + "/kr/kakao/ok/" + token,
                "cancel_url": origin + "/kr/fail?code=USER_CANCEL&orderId=" + order_id,
                "fail_url": origin + "/kr/fail?code=KAKAO_FAIL&orderId=" + order_id,
            })
            if status != 200 or not ready.get("tid"):
                print("KAKAO READY FAIL:", order_id, status, ready.get("error_code"), ready.get("error_message"))
                self.kr_error("카카오페이 결제를 시작하지 못했습니다. 잠시 후 다시 시도해 주세요.", 502, "READY_FAILED")
                return
            remember_tid(order_id, ready["tid"])
            self.send_json({
                "status": "success",
                "provider": "kakao",
                "order_id": order_id,
                "amount": product["price"],
                "tid": ready["tid"],
                "redirect_pc": ready.get("next_redirect_pc_url", ""),
                "redirect_mobile": ready.get("next_redirect_mobile_url", ""),
            })
            return

        self.send_json({
            "provider": "toss",
            "status": "success",
            "order_id": order_id,
            "amount": product["price"],
            "order_name": product["name"],
            "customer_key": "guest_" + secrets.token_hex(8),
            "token": token,
        })

    def kr_confirm(self, data):
        order = unseal(str(data.get("token", "")))
        payment_key = str(data.get("paymentKey", "")).strip()
        order_id = str(data.get("orderId", "")).strip()
        try:
            amount = int(str(data.get("amount", "")).strip())
        except ValueError:
            amount = -1

        if not order or order.get("t") != "order":
            self.kr_error("주문 정보를 확인할 수 없습니다. 고객센터로 문의해 주세요.", 400, "BAD_TOKEN")
            return
        product = readings.PRODUCT_BY_ID.get(order["pid"])
        if (not product or order["oid"] != order_id or order["amt"] != amount
                or product["price"] != amount or not payment_key):
            self.kr_error("결제 금액 또는 주문 정보가 일치하지 않습니다.", 400, "MISMATCH")
            return

        status, payment = toss_request(
            "/v1/payments/confirm", "POST",
            {"paymentKey": payment_key, "orderId": order_id, "amount": amount},
        )
        if status != 200:
            code = payment.get("code", "")
            if code in ("ALREADY_PROCESSED_PAYMENT", "PROVIDER_ERROR", "FAILED_INTERNAL_SYSTEM_PROCESSING"):
                status, payment = toss_request("/v1/payments/" + urllib.parse.quote(payment_key, safe=""))
            if status != 200 or not payment_ok(payment, order_id, amount):
                print("CONFIRM FAIL:", order_id, code)
                self.kr_error(payment.get("message") or "결제 승인에 실패했습니다.", 400, code or "CONFIRM_FAILED")
                return

        if not payment_ok(payment, order_id, amount):
            self.kr_error("결제가 완료되지 않았습니다.", 400, "NOT_DONE")
            return

        result_token, reading = make_result(order, payment_key)
        receipt = (payment.get("receipt") or {}).get("url", "")
        print("PAID:", order_id, product["id"], amount, payment.get("method", ""))
        self.send_json({"status": "success", "token": result_token, "result": reading, "receipt_url": receipt})

    def kr_kakao_approve(self, data):
        order = unseal(str(data.get("token", "")))
        pg_token = str(data.get("pg_token", "")).strip()
        if not order or order.get("t") != "order":
            self.kr_error("주문 정보를 확인할 수 없습니다. 고객센터로 문의해 주세요.", 400, "BAD_TOKEN")
            return
        product = readings.PRODUCT_BY_ID.get(order["pid"])
        order_id, amount = order["oid"], order["amt"]
        if not product or product["price"] != amount:
            self.kr_error("결제 금액 또는 주문 정보가 일치하지 않습니다.", 400, "MISMATCH")
            return
        saved = _kakao_tids.get(order_id)
        tid = saved[1] if saved else str(data.get("tid", "")).strip()
        if not tid or not pg_token:
            self.kr_error("결제 정보를 찾을 수 없습니다. 고객센터로 주문번호를 알려 주세요.", 400, "NO_TID")
            return

        status, info = kakao_request("/online/v1/payment/approve", {
            "cid": KAKAO_CID,
            "tid": tid,
            "partner_order_id": order_id,
            "partner_user_id": "guest",
            "pg_token": pg_token,
        })
        if status != 200:
            # 새로고침 등으로 이미 승인된 경우: 주문 조회로 확인
            status2, info2 = kakao_request("/online/v1/payment/order", {"cid": KAKAO_CID, "tid": tid})
            if status2 == 200 and info2.get("status") == "SUCCESS_PAYMENT" and kakao_paid_ok(info2, order_id, amount):
                info = info2
            else:
                print("KAKAO APPROVE FAIL:", order_id, status, info.get("error_code"))
                self.kr_error(kakao_message(info, "결제 승인에 실패했습니다."), 400, "APPROVE_FAILED")
                return
        elif not kakao_paid_ok(info, order_id, amount):
            print("KAKAO AMOUNT MISMATCH:", order_id)
            self.kr_error("결제 금액이 주문과 일치하지 않습니다. 고객센터로 문의해 주세요.", 400, "MISMATCH")
            return

        result_token, reading = make_result(order, "kakao:" + KAKAO_CID + ":" + tid)
        print("PAID:", order_id, product["id"], amount, "kakaopay", info.get("payment_method_type", ""))
        self.send_json({"status": "success", "token": result_token, "result": reading, "receipt_url": ""})

    def kr_result(self, data):
        sealed = unseal(str(data.get("token", "")))
        if not sealed or sealed.get("t") != "result":
            self.kr_error("결과 링크가 올바르지 않습니다. 링크 전체를 복사했는지 확인해 주세요.", 400, "BAD_TOKEN")
            return
        if sealed.get("pk") and not payment_still_valid(sealed["pk"]):
            self.kr_error("취소 또는 환불된 주문의 결과는 볼 수 없습니다.", 403, "CANCELED")
            return
        reading = readings.generate(sealed["pid"], sealed["A"], sealed.get("B"))
        reading["order_id"] = sealed.get("oid", "")
        reading["preview"] = bool(sealed.get("preview"))
        self.send_json({"status": "success", "result": reading})

    def kr_preview(self, data):
        given = str(data.get("admin_key", ""))
        if not ADMIN_KEY or not hmac.compare_digest(given, ADMIN_KEY):
            time.sleep(1)
            self.kr_error("관리자 비밀번호가 맞지 않습니다.", 403, "FORBIDDEN")
            return
        product, person_a, person_b = clean_order(data)
        order = {"pid": product["id"], "oid": "PREVIEW", "amt": 0, "A": person_a, "B": person_b}
        result_token, reading = make_result(order, "", preview=True)
        self.send_json({"status": "success", "token": result_token, "result": reading})


# ============================================================
# START SERVER
# ============================================================

def run():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), SajuHandler)

    print("Saju server running on port", PORT)
    print("KR payment:", PAY_PROVIDER or "not configured", "(test mode)" if PAY_TEST_MODE else "")
    print("US page: /us")
    print("PayPal mode:", PAYPAL_MODE)

    server.serve_forever()


if __name__ == "__main__":
    run()
