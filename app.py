from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import json

PORT = int(os.environ.get("PORT", 8000))

# Render Environment에 저장한 PayPal 정보
PAYPAL_CLIENT_ID = os.environ.get("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.environ.get("PAYPAL_CLIENT_SECRET", "")


class SajuHandler(BaseHTTPRequestHandler):

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
        response = json.dumps(
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
            str(len(response))
        )
        self.end_headers()
        self.wfile.write(response)


    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()


    def do_GET(self):

        # 미국판
        if self.path in [
            "/index-us.html",
            "/us",
            "/us/"
        ]:
            self.send_html("index-us.html")
            return

        # 한국판
        if self.path in [
            "/",
            "/index.html"
        ]:
            self.send_html("index.html")
            return

        # PayPal Client ID 확인용
        # Secret은 절대로 브라우저에 보내지 않음
        if self.path == "/api/paypal-config":
            if not PAYPAL_CLIENT_ID:
                self.send_json({
                    "status": "error",
                    "message": "PAYPAL_CLIENT_ID is not configured"
                }, 500)
                return

            self.send_json({
                "status": "success",
                "client_id": PAYPAL_CLIENT_ID
            })
            return

        self.send_response(404)
        self.send_header(
            "Content-Type",
            "text/plain; charset=utf-8"
        )
        self.end_headers()
        self.wfile.write(b"Page not found")


    def do_POST(self):

        content_length = int(
            self.headers.get("Content-Length", 0)
        )

        post_data = self.rfile.read(content_length)

        try:
            data = json.loads(
                post_data.decode("utf-8")
            )
        except:
            self.send_json({
                "status": "error",
                "message": "Invalid request"
            }, 400)
            return

        birth = data.get("birth", "")
        time = data.get("time", "")
        place = data.get("place", "")

        response_data = {
            "status": "success",
            "birth": birth,
            "time": time,
            "place": place
        }

        self.send_json(response_data)


def run():

    server_address = (
        "0.0.0.0",
        PORT
    )

    httpd = HTTPServer(
        server_address,
        SajuHandler
    )

    print(
        f"Saju server running on port {PORT}"
    )

    httpd.serve_forever()


if __name__ == "__main__":
    run()
