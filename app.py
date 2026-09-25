from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import json

PORT = int(os.environ.get("PORT", 8000))


class SajuHandler(BaseHTTPRequestHandler):

    def send_html(self, filename):
        try:
            with open(filename, "rb") as file:
                content = file.read()

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        except FileNotFoundError:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Page not found")


    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()


    def do_GET(self):

        # 미국판
        if self.path in ["/index-us.html", "/us", "/us/"]:
            self.send_html("index-us.html")
            return

        # 한국판
        if self.path in ["/", "/index.html"]:
            self.send_html("index.html")
            return

        self.send_response(404)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Page not found")


    def do_POST(self):

        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)

        try:
            data = json.loads(post_data.decode("utf-8"))
        except:
            data = {}

        birth = data.get("birth", "")
        time = data.get("time", "")
        place = data.get("place", "")

        response_data = {
            "status": "success",
            "birth": birth,
            "time": time,
            "place": place
        }

        response = json.dumps(
            response_data,
            ensure_ascii=False
        ).encode("utf-8")

        self.send_response(200)
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


def run():

    server_address = ("0.0.0.0", PORT)

    httpd = HTTPServer(
        server_address,
        SajuHandler
    )

    print(f"Saju server running on port {PORT}")

    httpd.serve_forever()


if __name__ == "__main__":
    run()
