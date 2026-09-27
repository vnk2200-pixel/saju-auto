from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import json
import base64
import urllib.request
import urllib.error
from urllib.parse import urlparse


# ============================================================
# BASIC SETTINGS
# ============================================================

PORT = int(os.environ.get("PORT", "8000"))

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
# HTTP SERVER
# ============================================================

class SajuHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        print(
            "%s - %s"
            % (
                self.address_string(),
                format % args,
            )
        )

    def send_no_cache_headers(self):
        self.send_header(
            "Cache-Control",
            "no-store, no-cache, must-revalidate, max-age=0",
        )
        self.send_header(
            "Pragma",
            "no-cache"
        )
        self.send_header(
            "Expires",
            "0"
        )

    def send_html(self, filename):
        try:
            with open(filename, "rb") as file:
                content = file.read()

            self.send_response(200)
            self.send_header(
                "Content-Type",
                "text/html; charset=utf-8"
            )
            self.send_header(
                "Content-Length",
                str(len(content))
            )
            self.send_no_cache_headers()
            self.end_headers()
            self.wfile.write(content)

        except FileNotFoundError:
            self.send_text(
                "Page not found",
                404
            )

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
        self.send_no_cache_headers()
        self.end_headers()
        self.wfile.write(body)

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
        self.send_no_cache_headers()
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(
            self.headers.get(
                "Content-Length",
                "0"
            )
        )

        if length <= 0:
            return {}

        raw_data = self.rfile.read(length)

        if not raw_data:
            return {}

        return json.loads(
            raw_data.decode("utf-8")
        )

    def do_HEAD(self):
        self.send_response(200)
        self.send_no_cache_headers()
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path

        # ----------------------------------------------------
        # US PAGE
        # ----------------------------------------------------

        if path in (
            "/us",
            "/us/",
            "/index-us.html",
        ):
            self.send_html(
                "index-us.html"
            )
            return

        # ----------------------------------------------------
        # KOREAN PAGE
        # Do not modify index.html.
        # ----------------------------------------------------

        if path in (
            "/",
            "/index.html",
        ):
            self.send_html(
                "index.html"
            )
            return

        # ----------------------------------------------------
        # PAYPAL CONFIG
        # ----------------------------------------------------

        if path == "/api/paypal-config":
            if not PAYPAL_CLIENT_ID:
                self.send_json(
                    {
                        "status": "error",
                        "message":
                            "PAYPAL_CLIENT_ID is not configured.",
                    },
                    500,
                )
                return

            self.send_json(
                {
                    "status": "success",
                    "client_id":
                        PAYPAL_CLIENT_ID,
                    "price":
                        US_PRICE,
                    "currency":
                        US_CURRENCY,
                    "mode":
                        PAYPAL_MODE,
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
                    "us_price": US_PRICE,
                    "currency": US_CURRENCY,
                    "paypal_mode": PAYPAL_MODE,
                    "paypal_configured": bool(
                        PAYPAL_CLIENT_ID
                        and PAYPAL_CLIENT_SECRET
                    ),
                }
            )
            return

        self.send_text(
            "Page not found",
            404
        )

    def do_POST(self):
        path = urlparse(self.path).path

        try:
            data = self.read_json()

        except Exception:
            self.send_json(
                {
                    "status": "error",
                    "message": "Invalid JSON request.",
                },
                400,
            )
            return

        # ----------------------------------------------------
        # CREATE PAYPAL ORDER
        # ----------------------------------------------------

        if path == "/api/paypal/create-order":
            try:
                order = create_paypal_order()

                order_id = order.get("id")

                if not order_id:
                    raise RuntimeError(
                        "PayPal did not return an order ID."
                    )

                self.send_json(
                    {
                        "status": "success",
                        "order_id": order_id,
                        "paypal_status":
                            order.get("status"),
                    }
                )

            except Exception as error:
                print(
                    "CREATE ORDER ERROR:",
                    str(error)
                )

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
            order_id = str(
                data.get(
                    "order_id",
                    ""
                )
            ).strip()

            if not order_id:
                self.send_json(
                    {
                        "status": "error",
                        "message":
                            "PayPal order ID is required.",
                    },
                    400,
                )
                return

            try:
                capture_result = (
                    capture_paypal_order(
                        order_id
                    )
                )

                paid = verify_capture(
                    capture_result
                )

                if not paid:
                    self.send_json(
                        {
                            "status": "error",
                            "paid": False,
                            "message":
                                "Payment could not be verified.",
                        },
                        400,
                    )
                    return

                capture_id = ""

                try:
                    capture_id = (
                        capture_result[
                            "purchase_units"
                        ][0][
                            "payments"
                        ][
                            "captures"
                        ][0].get(
                            "id",
                            ""
                        )
                    )
                except Exception:
                    capture_id = ""

                self.send_json(
                    {
                        "status": "success",
                        "paid": True,
                        "order_id": order_id,
                        "capture_id":
                            capture_id,
                        "price":
                            US_PRICE,
                        "currency":
                            US_CURRENCY,
                        "message":
                            "Payment verified successfully.",
                    }
                )

            except Exception as error:
                print(
                    "CAPTURE ERROR:",
                    str(error)
                )

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
            birth = str(
                data.get(
                    "birth",
                    ""
                )
            ).strip()

            birth_time = str(
                data.get(
                    "time",
                    ""
                )
            ).strip()

            place = str(
                data.get(
                    "place",
                    ""
                )
            ).strip()

            payment_verified = (
                data.get(
                    "payment_verified"
                )
                is True
            )

            if not birth:
                self.send_json(
                    {
                        "status": "error",
                        "message":
                            "Date of birth is required.",
                    },
                    400,
                )
                return

            if not place:
                self.send_json(
                    {
                        "status": "error",
                        "message":
                            "Place of birth is required.",
                    },
                    400,
                )
                return

            if not payment_verified:
                self.send_json(
                    {
                        "status": "error",
                        "message":
                            "Verified payment is required.",
                    },
                    403,
                )
                return

            self.send_json(
                {
                    "status": "success",
                    "birth": birth,
                    "time": birth_time,
                    "place": place,
                    "price": US_PRICE,
                    "currency":
                        US_CURRENCY,
                }
            )
            return

        self.send_json(
            {
                "status": "error",
                "message":
                    "API endpoint not found.",
            },
            404,
        )


# ============================================================
# START SERVER
# ============================================================

def run():
    server = HTTPServer(
        ("0.0.0.0", PORT),
        SajuHandler
    )

    print(
        "Saju server running on port",
        PORT
    )

    print(
        "US page: /us"
    )

    print(
        "PayPal mode:",
        PAYPAL_MODE
    )

    server.serve_forever()


if __name__ == "__main__":
    run()
