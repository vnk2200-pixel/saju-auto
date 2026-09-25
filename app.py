from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import json

PORT = int(os.environ.get("PORT", 8000))

# PayPal information stored in Render Environment
PAYPAL_CLIENT_ID = os.environ.get("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.environ.get("PAYPAL_CLIENT_SECRET", "")

# US product price: fixed at $20 USD
US_PRICE = "20.00"
US_CURRENCY = "USD"


class SajuHandler(BaseHTTPRequestHandler):

    def send_html(self, filename):
        try:
            with open(filename, "rb") as f:
                content = f.read()

            self.send_response(200)
            self.send_header(
                "Content-Type",
                "text/html; charset=utf-8"
            )
            self.send_header(
                "Content-Length",
                str(len(content))
            )
            self.end_headers()
            self.wfile.write(content)

        except FileNotFoundError:
            self.send_response(404)
            self.send_header(
                "Content-Type",
                "text/plain; charset=utf-8"
            )
            self.end_headers()
            self.wfile.write(b"Page not found")

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
        self.send_header(
            "Cache-Control",
            "no-store"
        )
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):

        # US page
        if self.path in ("/us", "/us/", "/index-us.html"):
            self.send_html("index-us.html")
            return

        # Korean page
        if self.path in ("/", "/index.html"):
            self.send_html("index.html")
            return

        # PayPal configuration
        if self.path == "/api/paypal-config":

            if not PAYPAL_CLIENT_ID:
                self.send_json(
                    {
                        "status": "error",
                        "message": "PAYPAL_CLIENT_ID is not configured"
                    },
                    500
                )
                return

            self.send_json(
                {
                    "status": "success",
                    "client_id": PAYPAL_CLIENT_ID,
                    "price": US_PRICE,
                    "currency": US_CURRENCY
                }
            )
            return

        # Server health check
        if self.path == "/api/health":
            self.send_json(
                {
                    "status": "success",
                    "price": US_PRICE,
                    "currency": US_CURRENCY
                }
            )
            return

        self.send_response(404)
        self.send_header(
            "Content-Type",
            "text/plain; charset=utf-8"
        )
        self.end_headers()
        self.wfile.write(b"Page not found")

    def do_POST(self):

        length = int(
            self.headers.get("Content-Length", 0)
        )

        raw_data = self.rfile.read(length)

        try:
            data = json.loads(
                raw_data.decode("utf-8")
            )
        except Exception:
            self.send_json(
                {
                    "status": "error",
                    "message": "Invalid request"
                },
                400
            )
            return

        birth = data.get("birth", "").strip()
        birth_time = data.get("time", "").strip()
        place = data.get("place", "").strip()

        if not birth:
            self.send_json(
                {
                    "status": "error",
                    "message": "Date of birth is required."
                },
                400
            )
            return

        if not place:
            self.send_json(
                {
                    "status": "error",
                    "message": "Place of birth is required."
                },
                400
            )
            return

        self.send_json(
            {
                "status": "success",
                "birth": birth,
                "time": birth_time,
                "place": place,
                "price": US_PRICE,
                "currency": US_CURRENCY
            }
        )


def run():
    server = HTTPServer(
        ("0.0.0.0", PORT),
        SajuHandler
    )

    print("Saju server running on port", PORT)
    server.serve_forever()


if __name__ == "__main__":
    run()
