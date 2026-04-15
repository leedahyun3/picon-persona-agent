from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from picon_eval.runner import load_profile, run_demo


INDEX_HTML = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PICon Persona Eval</title>
  <style>
    :root {
      --bg: #f3efe7;
      --panel: rgba(255,255,255,0.78);
      --ink: #152321;
      --accent: #0b6e4f;
      --accent-soft: #d8efe5;
      --line: rgba(21,35,33,0.1);
    }
    body {
      margin: 0;
      font-family: Georgia, "Apple SD Gothic Neo", serif;
      background:
        radial-gradient(circle at top left, #fff7d6 0, transparent 38%),
        radial-gradient(circle at right center, #d3efe6 0, transparent 30%),
        linear-gradient(160deg, #f8f3ea, #eaf2ef 55%, #f3efe7);
      color: var(--ink);
      min-height: 100vh;
    }
    .wrap { max-width: 1024px; margin: 0 auto; padding: 48px 20px 64px; }
    .hero {
      display: grid;
      gap: 18px;
      margin-bottom: 24px;
    }
    h1 { margin: 0; font-size: clamp(2.2rem, 5vw, 4.8rem); line-height: 0.95; }
    p { font-size: 1.02rem; max-width: 760px; }
    .panel {
      background: var(--panel);
      backdrop-filter: blur(18px);
      border: 1px solid var(--line);
      border-radius: 24px;
      padding: 22px;
      box-shadow: 0 18px 50px rgba(22, 36, 34, 0.08);
    }
    .actions { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
    button {
      appearance: none;
      border: 0;
      background: var(--accent);
      color: white;
      border-radius: 999px;
      padding: 12px 18px;
      font-size: 0.98rem;
      cursor: pointer;
    }
    .scores { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-top: 18px; }
    .score { background: var(--accent-soft); border-radius: 18px; padding: 16px; }
    .score b { display: block; font-size: 1.8rem; margin-top: 8px; }
    pre {
      white-space: pre-wrap;
      background: rgba(255,255,255,0.65);
      border-radius: 18px;
      border: 1px solid var(--line);
      padding: 16px;
      overflow: auto;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <div class="panel">
        <h1>PICon<br>Persona Eval</h1>
        <p>명세서와 논문을 바탕으로 만든 오프라인 실행형 페르소나 AI 평가 앱입니다. 10턴 GtK, 40턴 Main Interrogation, 10턴 Retest를 수행하고 IC, EC, RC를 계산합니다.</p>
        <div class="actions">
          <button id="run">샘플 세션 실행</button>
          <span id="status">대기 중</span>
        </div>
        <div class="scores" id="scores"></div>
      </div>
      <div class="panel">
        <h2>세션 결과</h2>
        <pre id="output">버튼을 눌러 샘플 평가를 실행하세요.</pre>
      </div>
    </section>
  </div>
  <script>
    document.getElementById('run').addEventListener('click', async () => {
      const status = document.getElementById('status');
      const output = document.getElementById('output');
      const scores = document.getElementById('scores');
      status.textContent = '실행 중';
      output.textContent = '세션을 생성하고 있습니다...';
      scores.innerHTML = '';
      const res = await fetch('/api/run-demo', { method: 'POST' });
      const data = await res.json();
      status.textContent = '완료';
      output.textContent = JSON.stringify(data, null, 2);
      const items = ['IC', 'EC', 'RC', 'overall'];
      scores.innerHTML = items.map(key => `<div class="score"><span>${key}</span><b>${data.scores[key]}</b></div>`).join('');
    });
  </script>
</body>
</html>
"""


class AppHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            body = INDEX_HTML.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self):
        if self.path == "/api/run-demo":
            result = run_demo()
            body = json.dumps(result.to_dict(), ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def log_message(self, format, *args):
        return


def serve(host: str = "127.0.0.1", port: int = 8080) -> None:
    server = ThreadingHTTPServer((host, port), AppHandler)
    print(f"Serving on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
