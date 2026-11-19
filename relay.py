#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
オンライン中継サーバー (relay)
- Mac側 nowplaying.py が POST /push で状態JSONを送ってくる
- 視聴側は GET / (オーバーレイHTML) と GET /api (状態JSON) を開く
- VJ/PAのPCや、配信のOBSからこのURLを開けば、どこからでも NOW PLAYING が見える
- 合言葉 (X-Token ヘッダ) が一致しない push は受け付けない

使い方:
  RELAY_TOKEN=好きな合言葉 python3 relay.py [ポート番号(既定8765)]
配置先: VPS、レンタルサーバー、自宅の常時起動PCなど、URLで届く場所ならどこでも。
依存: Python 標準ライブラリのみ
"""
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = os.path.dirname(os.path.abspath(__file__))
TOKEN = os.environ.get("RELAY_TOKEN", "")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765

state = {"status": "waiting-for-push", "updated_at": None}
lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.path != "/push":
            self._send(404, "not found", "text/plain; charset=utf-8")
            return
        if TOKEN and self.headers.get("X-Token") != TOKEN:
            self._send(403, "bad token", "text/plain; charset=utf-8")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            self._send(400, "bad json", "text/plain; charset=utf-8")
            return
        with lock:
            state.clear()
            state.update(payload)
            state["relay_received_at"] = time.time()
        self._send(200, "ok", "text/plain; charset=utf-8")

    def do_GET(self):
        if self.path.startswith("/api"):
            with lock:
                payload = json.dumps(state, ensure_ascii=False)
            self._send(200, payload, "application/json; charset=utf-8")
        elif self.path == "/" or self.path.startswith("/overlay"):
            try:
                with open(os.path.join(BASE, "overlay.html"), encoding="utf-8") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            except FileNotFoundError:
                self._send(404, "overlay.html not found", "text/plain; charset=utf-8")
        else:
            self._send(404, "not found", "text/plain; charset=utf-8")


def main():
    if not TOKEN:
        print("[警告] RELAY_TOKEN 未設定: 誰でも push できてしまいます。環境変数で設定推奨。")
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"relay listening on :{PORT}  (overlay: /, api: /api, push: /push)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
