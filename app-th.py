from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import json
from urllib.parse import urlparse

# ==========================================
# LOVE ORACLE THAILAND
# Thailand-only server
# 기존 한국판/미국판과 완전히 분리
# ==========================================

PORT = int(os.environ.get("PORT", "8000"))

TH_PRODUCT_NAME = "LOVE ORACLE THAILAND"
TH_CURRENCY = "THB"

# AppotaPay에서 실제 태국 가격을 확정한 뒤
# Render 환경변수 TH_PRICE로 설정합니다.
TH_PRICE = os.environ.get("TH_PRICE", "")

# 실제 AppotaPay 가맹점/API 정보가 발급되기 전에는
# 반드시 false 상태로 둡니다.
TH_PAYMENT_LIVE = (
    os.environ.get("TH_PAYMENT_LIVE", "false").lower() == "true"
)


class ThailandHandler(BaseHTTPRequestHandler):

    def no_cache(self):
        self.send_header(
            "Cache-Control",
            "no-store, no-cache, must-revalidate, max-age=0"
        )
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")

    def send_text(self, text, status=200):
        body = text.encode("utf-8")

        self.send_response(status)
        self.send_header(
            "Content-Type",
            "text/plain; charset=utf-8"
        )
        self.send_header(
            "Content-Length",
            str(len(body))
        )
        self.no_cache()
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, data, status=200):
        body = json.dumps(
            data,
            ensure_ascii=False
        ).encode("utf-8")

        self.send_response(status)
        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8"
        )
        self.send_header(
            "Content-Length",
            str(len(body))
        )
        self.no_cache()
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, filename):
        try:
            with open(filename, "rb") as f:
                body = f.read()

            self.send_response(200)
            self.send_header(
                "Content-Type",
                "text/html; charset=utf-8"
            )
            self.send_header(
                "Content-Length",
                str(len(body))
            )
            self.no_cache()
            self.end_headers()
            self.wfile.write(body)

        except FileNotFoundError:
            self.send_text(
                "Thailand page not found.",
                404
            )

    def do_HEAD(self):
        self.send_response(200)
        self.no_cache()
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path

        # Render 상태 확인
        if path == "/health":
            self.send_json({
                "ok": True,
                "service": "love-oracle-thailand",
                "currency": TH_CURRENCY,
                "payment_live": TH_PAYMENT_LIVE
            })
            return

        # 태국판 메인 페이지
        if path in ("/", "/th", "/th/", "/index-th.html"):
            self.send_html("index-th.html")
            return

        # 결제 설정 상태
        if path == "/api/th/payment-status":
            self.send_json({
                "country": "TH",
                "product": TH_PRODUCT_NAME,
                "currency": TH_CURRENCY,
                "price": TH_PRICE,
                "payment_live": TH_PAYMENT_LIVE
            })
            return

        self.send_text("Not found", 404)

    def do_POST(self):
        path = urlparse(self.path).path

        # ------------------------------------------
        # 결제 생성
        # ------------------------------------------
        if path == "/api/th/create-payment":

            # 실제 AppotaPay API 연결 전에는
            # 결제를 절대로 성공 처리하지 않습니다.
            if not TH_PAYMENT_LIVE:
                self.send_json({
                    "ok": False,
                    "paid": False,
                    "code": "PAYMENT_NOT_ACTIVATED",
                    "message":
                    "Thailand payment is waiting for "
                    "AppotaPay merchant/API activation."
                }, 503)
                return

            # 중요:
            # AppotaPay에서 공식 API 문서와
            # Merchant/API Key가 발급된 후
            # 여기에 실제 결제 생성 API를 연결합니다.
            self.send_json({
                "ok": False,
                "paid": False,
                "code": "API_CONFIGURATION_REQUIRED"
            }, 503)
            return

        # ------------------------------------------
        # AppotaPay IPN 전용 주소
        # ------------------------------------------
        if path == "/api/th/appotapay/ipn":

            # 서명 검증 코드가 없는 상태에서는
            # 어떤 요청도 결제 성공으로 인정하지 않습니다.
            if not TH_PAYMENT_LIVE:
                self.send_json({
                    "ok": False,
                    "paid": False,
                    "code": "IPN_NOT_ACTIVATED"
                }, 503)
                return

            # 실제 AppotaPay 공식 문서의
            # 서명 검증 방식이 확인된 후 구현합니다.
            self.send_json({
                "ok": False,
                "paid": False,
                "code": "SIGNATURE_VERIFICATION_REQUIRED"
            }, 503)
            return

        self.send_json({
            "ok": False,
            "error": "Not found"
        }, 404)


if __name__ == "__main__":
    server = HTTPServer(
        ("0.0.0.0", PORT),
        ThailandHandler
    )

    print(
        "LOVE ORACLE THAILAND server started "
        f"on port {PORT}"
    )

    server.serve_forever()
