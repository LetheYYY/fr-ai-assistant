"""帆软数字员工 Web 服务 v2 — 访问 http://localhost:8899"""
import http.server
import json, os, sys, tempfile

WEB_ROOT = r'os.path.dirname(os.path.abspath(__file__))\web'
sys.path.insert(0, r'os.path.dirname(os.path.abspath(__file__))')
from agent import DigitalEmployee
agent = DigitalEmployee()

class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=WEB_ROOT, **kw)

    def do_GET(self):
        if self.path == '/':
            self.path = '/index.html'
        if self.path == '/api/outputs':
            self._list_outputs()
            return
        if self.path == '/api/reset':
            agent.pending = None
            self._json({"ok": True})
            return
        super().do_GET()

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length)) if length > 0 else {}
        msg = body.get('message', '').strip()
        if not msg:
            self._json({"error": "empty"})
            return
        result = agent.process(msg)
        self._json(result)

    def _list_outputs(self):
        d = r'os.path.dirname(os.path.abspath(__file__))\output'
        files = []
        if os.path.isdir(d):
            for f in sorted(os.listdir(d), reverse=True):
                fp = os.path.join(d, f)
                if f.endswith(('.cpt','.json')):
                    files.append({"name":f,"size":os.path.getsize(fp)})
        self._json({"files": files[:20]})

    def _json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {args[0]}")

if __name__ == '__main__':
    print(f"帆软数字员工 Web 服务: http://localhost:8899")
    http.server.HTTPServer(('0.0.0.0', 8899), H).serve_forever()
