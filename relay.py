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
import re
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = os.path.dirname(os.path.abspath(__file__))
TOKEN = os.environ.get("RELAY_TOKEN", "")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765

EMPTY = {"now": None, "next": None, "decks": {}, "faders": {}, "updated_at": 0}
ROOM_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
rooms = {}  # room名 -> {"state": payload, "ts": 受信時刻}
lock = threading.Lock()


def room_of(path):
    q = urllib.parse.parse_qs(urllib.parse.urlparse(path).query)
    r = (q.get("room") or ["main"])[0]
    return r if ROOM_RE.match(r) else None


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
        if not self.path.startswith("/push"):
            self._send(404, "not found", "text/plain; charset=utf-8")
            return
        if TOKEN and self.headers.get("X-Token") != TOKEN:
            self._send(403, "bad token", "text/plain; charset=utf-8")
            return
        room = room_of(self.path)
        if room is None:
            self._send(400, "bad room", "text/plain; charset=utf-8")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            self._send(400, "bad json", "text/plain; charset=utf-8")
            return
        with lock:
            rooms[room] = {"state": payload, "ts": time.time()}
        self._send(200, "ok", "text/plain; charset=utf-8")

    def do_GET(self):
        if self.path.startswith("/api"):
            room = room_of(self.path)
            if room is None:
                self._send(400, "bad room", "text/plain; charset=utf-8")
                return
            with lock:
                entry = rooms.get(room)
                payload = json.dumps(entry["state"] if entry else EMPTY,
                                     ensure_ascii=False)
            self._send(200, payload, "application/json; charset=utf-8")
        elif self.path.startswith("/rooms"):
            with lock:
                snapshot = list(rooms.items())
            out = []
            for name, entry in snapshot:
                s = entry["state"] or {}
                deck = (s.get("decks") or {}).get(str(s.get("on_air"))) if s.get("on_air") else None
                out.append({
                    "name": name,
                    "updated_at": int(entry["ts"]),
                    "live": bool(s.get("status") == "ok" and deck and deck.get("title")),
                    "title": deck.get("title") if deck else None,
                })
            out.sort(key=lambda x: -x["updated_at"])
            self._send(200, json.dumps(out, ensure_ascii=False),
                       "application/json; charset=utf-8")
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
