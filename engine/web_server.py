"""帆软数字员工 Web 服务"""
import http.server
import json, os, sys, cgi, tempfile, shutil, re

sys.path.insert(0, r'os.path.dirname(os.path.abspath(__file__))')
from agent import DigitalEmployee

WEB_PORT = 8899
WEB_ROOT = r'os.path.dirname(os.path.abspath(__file__))\web'
os.makedirs(WEB_ROOT, exist_ok=True)

# 全局 Agent 实例（保持会话状态）
agent = DigitalEmployee()


class AgentAPIHandler(http.server.SimpleHTTPRequestHandler):
    """处理 API 请求 + 静态文件"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_ROOT, **kwargs)

    def do_POST(self):
        if self.path == '/api/chat':
            self._handle_chat()
        elif self.path == '/api/upload':
            self._handle_upload()
        else:
            self.send_error(404)

    def do_GET(self):
        if self.path == '/' or self.path == '':
            self.path = '/index.html'
        if self.path == '/api/outputs':
            self._handle_list_outputs()
        elif self.path == '/api/reset':
            agent.pending = None
            self._send_json({"ok": True, "msg": "会话已重置"})
        else:
            super().do_GET()

    def _handle_chat(self):
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length))
        user_input = body.get('message', '').strip()
        if not user_input:
            self._send_json({"error": "empty message"})
            return

        result = agent.process(user_input)
        self._send_json(result)

    def _handle_upload(self):
        content_type = self.headers.get('Content-Type', '')
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)

        # Parse multipart
        boundary = content_type.split('boundary=')[1].encode()
        parts = body.split(b'--' + boundary)
        for part in parts:
            if b'filename=' in part:
                header, content = part.split(b'\r\n\r\n', 1)
                content = content.rsplit(b'\r\n--', 1)[0]
                filename = re.search(rb'filename="(.*?)"', header)
                fname = filename.group(1).decode() if filename else 'upload'
                ext = os.path.splitext(fname)[1].lower()
                tmp = os.path.join(tempfile.gettempdir(), fname)
                with open(tmp, 'wb') as f:
                    f.write(content)
                result = agent.process(tmp)
                result['upload_name'] = fname
                os.remove(tmp)
                self._send_json(result)
                return
        self._send_json({"error": "no file found"})

    def _handle_list_outputs(self):
        out_dir = r'os.path.dirname(os.path.abspath(__file__))\output'
        files = []
        if os.path.isdir(out_dir):
            for f in sorted(os.listdir(out_dir), reverse=True):
                if f.endswith(('.cpt', '.json')):
                    fp = os.path.join(out_dir, f)
                    files.append({
                        "name": f,
                        "size": os.path.getsize(fp),
                        "time": os.path.getmtime(fp)
                    })
        self._send_json({"files": files[:20]})

    def _send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'))

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {args[0]}")


if __name__ == '__main__':
    print(f"帆软数字员工 Web 服务")
    print(f"访问: http://localhost:{WEB_PORT}")
    http.server.HTTPServer(('0.0.0.0', WEB_PORT), AgentAPIHandler).serve_forever()
