from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import json

class SajuHandler(BaseHTTPRequestHandler):
        def do_GET(self):
        with open('index.html', 'rb') as file:
            content = file.read()
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(content)
        def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        
        name = data.get('name', '고객')
        birth = data.get('birth', '')
        tier = data.get('tier', '990') # 990, 30000, 70000, 300000 등 요금제
        
        # 가격대별 사주 풀이 분기 처리
        if tier == '990':
            result = f"{name}님의 990원 핵심 인연운 요약: 올해 좋은 기운이 들어옵니다."
        elif tier == '30000':
            result = f"{name}님의 3만 원 2027년 월별 상세 운세 리포트입니다."
        elif tier == '70000':
            result = f"{name}님의 7만 원 심층 궁합 및 주의사항 분석입니다."
        elif tier == '300000':
            result = f"{name}님의 30만 원 평생 사주 프리미엄 대용량 리포트입니다."
        else:
            result = f"{name}님의 기본 사주 분석 결과입니다."
            
        response_data = {"status": "success", "analysis": result}
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(response_data, ensure_ascii=False).encode('utf-8'))

def run():
    server_address = ('0.0.0.0', 8000)
    httpd = HTTPServer(server_address, SajuHandler)
    print("사주 자동화 서버가 8000번 포트에서 실행 중입니다...")
    httpd.serve_forever()

if __name__ == '__main__':
    run()
