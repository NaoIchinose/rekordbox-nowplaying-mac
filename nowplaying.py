#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rekordbox 7 NOW PLAYING (macOS版) v1
仕様:
- 曲情報: Rekordboxの画面要素を macOS アクセシビリティ(osascript) で取得
- MIDI: コントローラーから 再生/停止・CHフェーダー・クロスフェーダーを取得
        (midi_maps/ 内の機種別プロファイル + mido が必要。DDJ-1000 / DDJ-FLX4 など
         接続中の機種を自動判別し、抜き差しすると自動で再接続する)
- オンエア判定: フェーダー位置と再生状態から計算 (MIDIが無い場合は時間表示の進行で判定)
- 配信: ローカル http://localhost:8765/ と /api
        + config.json の relay_url を設定すると、状態JSONをオンライン中継サーバーへ push する
- NEXT: オンエアでない方のデッキにロードされている曲を「NEXT」として配信
依存: 標準ライブラリのみ (MIDIを使う場合のみ mido / python-rtmidi)
"""
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE, "config.json")
MIDI_MAP_PATH = os.path.join(BASE, "midi_map.json")
MIDI_MAPS_DIR = os.path.join(BASE, "midi_maps")

DEFAULTS = {
    "port": 8765,
    "poll_seconds": 2.0,
    "deck_band_ratio": 0.5,
    "relay_url": "",        # 例: https://example.com/push  (空ならpushしない)
    "relay_token": "",      # relay.py と共有する合言葉
    "push_seconds": 1.0,
    "midi_port_hint": "DDJ-1000",
    "room": "",             # 複数DJで使う場合の部屋名 (半角英数) 例: "nao"。空なら既定の部屋
    "itunes_lookup": True,   # ジャケット未取得時に iTunes Search API で補完する
}

def load_config():
    cfg = dict(DEFAULTS)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception as e:
            print(f"[warn] config.json 読込失敗: {e}", file=sys.stderr)
    return cfg

CFG = load_config()

# ---------- Rekordbox 画面読み取り ----------

FETCH_SCRIPT = r'''
tell application "System Events"
	if not (exists process "rekordbox") then return "NORUN"
	tell process "rekordbox"
		if (count of windows) is 0 then return "NOWIN"
		-- ツールチップ等の小窓を掴まないよう、一番面積の大きいウィンドウを選ぶ (元ツールの知見)
		set bestWin to missing value
		set bestArea to -1
		repeat with w in windows
			try
				set s to size of w
				set a to (item 1 of s) * (item 2 of s)
				if a > bestArea then
					set bestArea to a
					set bestWin to w
				end if
			end try
		end repeat
		if bestWin is missing value then return "NOWIN"
		set winPos to position of bestWin
		set winSize to size of bestWin
		set out to "WIN\t" & (item 1 of winPos) & "\t" & (item 2 of winPos) & "\t" & (item 1 of winSize) & "\t" & (item 2 of winSize)
		set elems to entire contents of bestWin
		repeat with el in elems
			try
				set r to role of el
			on error
				set r to ""
			end try
			if r is "AXStaticText" or r is "AXTextField" or r is "AXTextArea" or r is "AXButton" then
				try
					set n to name of el
				on error
					set n to ""
				end try
				try
					set v to value of el
				on error
					set v to ""
				end try
				if n is missing value then set n to ""
				if v is missing value then set v to ""
				if n is not "" or v is not "" then
					try
						set p to position of el
						set px to item 1 of p
						set py to item 2 of p
					on error
						set px to -1
						set py to -1
					end try
					set out to out & linefeed & r & "\t" & n & "\t" & v & "\t" & px & "\t" & py
				end if
			end if
		end repeat
		return out
	end tell
end tell
'''

TIME_RE = re.compile(r"^-?\d{1,2}:\d{2}(\.\d)?$")
BPM_RE = re.compile(r"^(\d{2,3}\.\d{2})$")


def time_to_seconds(t):
    """'01:23.4' / '-02:57.9' を秒(float)に。符号は呼び出し側で扱う"""
    sign = -1.0 if t.startswith("-") else 1.0
    body = t.lstrip("+-")
    try:
        m, s = body.split(":")
        return sign * (int(m) * 60 + float(s))
    except Exception:
        return None


def parse_times(times):
    """時間表示の組から 経過/残り/長さ/進捗 を作る。
    Rekordboxは 経過(+側) と 残り(-側) を出すので、長さ = 経過 + |残り|"""
    elapsed, remain = None, None
    for t in times:
        v = time_to_seconds(t)
        if v is None:
            continue
        if t.startswith("-"):
            remain = abs(v)
        elif elapsed is None:
            elapsed = v
    duration = None
    if elapsed is not None and remain is not None:
        duration = elapsed + remain
    progress = None
    if duration and duration > 0 and elapsed is not None:
        progress = round(elapsed / duration, 4)
    return {"position_sec": elapsed, "remaining_sec": remain,
            "duration_sec": duration, "progress": progress}

state = {
    "status": "starting",
    "updated_at": None,
    "decks": {1: None, 2: None},
    "on_air": None,
    "next": None,
    "faders": {"ch1": None, "ch2": None, "cross": None},
    "midi_connected": False,
}
state_lock = threading.Lock()
_prev_times = {1: set(), 2: set()}
_time_playing = {1: False, 2: False}
_time_known = {1: False, 2: False}
_last_good = {}          # deck -> (deck_info, timestamp) 部分的に欠けた取得の保持用
_enrich = {}             # (title, artist) -> {"work":..., "artwork":...}  # 時間表示を2回連続で読めたか（読めたときは時間判定を優先）
_midi_playing = {1: None, 2: None}   # MIDIのPLAYボタンで得た状態 (None=未取得)
_faders = {"ch1": None, "ch2": None, "cross": None}


def fetch_elements():
    p = subprocess.run(["osascript", "-e", FETCH_SCRIPT],
                       capture_output=True, text=True, timeout=20)
    out = (p.stdout or "").strip()
    if not out or out == "NORUN":
        return None, "rekordbox-not-running"
    if out == "NOWIN":
        return None, "no-window"
    win, items = None, []
    for ln in out.splitlines():
        parts = ln.split("\t")
        if parts[0] == "WIN" and len(parts) == 5:
            win = tuple(int(float(x)) for x in parts[1:5])
        elif len(parts) == 5:
            role, name, value, xs, ys = parts
            try:
                x, y = int(float(xs)), int(float(ys))
            except ValueError:
                x, y = -1, -1
            text = (value or name or "").strip()
            if text:
                items.append({"role": role, "text": text, "x": x, "y": y})
    if win is None:
        return None, "parse-error"
    return (win, items), None


def parse_decks(win, items):
    wx, wy, ww, wh = win
    band_bottom = wy + wh * float(CFG["deck_band_ratio"])
    # BEAT SYNCボタン等のアンカーが2つ取れたら、その中点をデッキ境界にする (元ツールの幾何アンカー方式)
    anchors = sorted(
        [it for it in items if it["role"] == "AXButton" and "SYNC" in it["text"].upper()],
        key=lambda it: it["x"])
    if len(anchors) >= 2:
        mid_x = (anchors[0]["x"] + anchors[-1]["x"]) / 2
    else:
        mid_x = wx + ww / 2
    texts_only = [it for it in items if it["role"] != "AXButton"]
    decks = {}
    for deck_no, in_zone in ((1, lambda x: x < mid_x), (2, lambda x: x >= mid_x)):
        zone = [it for it in texts_only
                if wy <= it["y"] <= band_bottom and it["x"] >= wx and in_zone(it["x"])]
        times, bpms, texts = [], [], []
        for it in zone:
            t = it["text"]
            if TIME_RE.match(t):
                times.append(t)
            elif BPM_RE.match(t) and 50.0 <= float(t) <= 220.0:
                bpms.append(t)
            elif len(t) >= 2:
                texts.append(it)
        texts.sort(key=lambda it: (it["y"], it["x"]))
        deck_info = {
            "title": texts[0]["text"] if texts else None,
            "artist": texts[1]["text"] if len(texts) > 1 else None,
            "bpm": bpms[0] if bpms else None,
            "times": times,
        }
        deck_info.update(parse_times(times))
        decks[deck_no] = deck_info
    return decks


def compute_on_air(decks):
    """再生状態とフェーダーからオンエアデッキとNEXTを決める。
    時間表示が読めているデッキは時間の進行を優先する（MIDIのPLAYは
    押すたび反転で追うため、Rekordbox側で直接再生/停止するとズレる）。
    時間表示が読めないときだけMIDIのPLAY状態を使う。"""
    playing = {}
    for d in (1, 2):
        if _time_known[d]:
            playing[d] = _time_playing[d]
        elif _midi_playing[d] is not None:
            playing[d] = _midi_playing[d]
        else:
            playing[d] = _time_playing[d]
        if decks.get(d):
            decks[d]["playing"] = playing[d]
    f = _faders
    cur = state.get("on_air")
    if f["cross"] is not None and f["ch1"] is not None and f["ch2"] is not None:
        x = f["cross"] / 127.0
        gain = {
            1: (f["ch1"] / 127.0) * min(1.0, (1.0 - x) * 2),
            2: (f["ch2"] / 127.0) * min(1.0, x * 2),
        }
        # ヒステリシス: 今のオンエアデッキのフェーダーが上がっている間は表示を切り替えない。
        # ミックス中に両方上がっていてもチラつかず、下げ切った時点で切り替わる (元ツールの現場知見)
        if cur in (1, 2) and playing[cur] and gain[cur] > 0.05:
            on_air = cur
        else:
            candidates = [d for d in (1, 2) if playing[d] and gain[d] > 0.05]
            on_air = max(candidates, key=lambda d: gain[d]) if candidates else cur
    else:
        candidates = [d for d in (1, 2) if playing[d]]
        on_air = candidates[0] if len(candidates) == 1 else state.get("on_air")
        if on_air not in (1, 2) and candidates:
            on_air = candidates[0]
    nxt = None
    if on_air in (1, 2):
        other = 2 if on_air == 1 else 1
        if decks.get(other) and decks[other]["title"]:
            nxt = {"deck": other, **{k: decks[other].get(k) for k in ("title", "artist", "bpm", "duration_sec", "work", "artwork")}}
    return on_air, nxt


def poll_loop():
    while True:
        try:
            got, err = fetch_elements()
            if err:
                with state_lock:
                    state["status"] = err
                    state["updated_at"] = time.time()
            else:
                win, items = got
                decks = parse_decks(win, items)
                now_ts = time.time()
                for d in (1, 2):
                    # 部分的に欠けた取得は「情報なし」として、前回の正常値を少しだけ保持する
                    if decks[d]["title"]:
                        _last_good[d] = (dict(decks[d]), now_ts)
                    elif d in _last_good and now_ts - _last_good[d][1] < 10:
                        kept = _last_good[d][0]
                        for k in ("title", "artist", "bpm", "duration_sec"):
                            decks[d][k] = kept.get(k)
                    enr = _enrich.get(_key(decks[d]["title"], decks[d]["artist"])) or {}
                    decks[d]["work"] = enr.get("work")
                    decks[d]["artwork"] = enr.get("artwork")
                for d in (1, 2):
                    cur = set(decks[d]["times"])
                    _time_known[d] = bool(cur and _prev_times[d])
                    _time_playing[d] = bool(_time_known[d] and cur != _prev_times[d])
                    _prev_times[d] = cur
                on_air, nxt = compute_on_air(decks)
                with state_lock:
                    state["status"] = "ok"
                    state["decks"] = decks
                    state["on_air"] = on_air
                    state["next"] = nxt
                    state["faders"] = dict(_faders)
                    state["updated_at"] = time.time()
        except subprocess.TimeoutExpired:
            with state_lock:
                state["status"] = "fetch-timeout"
        except Exception as e:
            with state_lock:
                state["status"] = f"error:{e}"
        time.sleep(float(CFG["poll_seconds"]))


# ---------- 楽曲メタデータ補完 (作品名・ジャケット) ----------

def _norm(s):
    return re.sub(r"\s+", "", (s or "")).lower()


def _key(title, artist):
    return (_norm(title), _norm(artist))


_catalog = {}
_itunes_cache = {}
_CACHE_PATH = os.path.join(BASE, "artwork_cache.json")


def _load_enrich_sources():
    import csv
    path = os.path.join(BASE, "catalog.csv")
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    _catalog[_key(row.get("title"), row.get("artist"))] = {
                        "work": (row.get("work") or None),
                        "artwork": (row.get("artwork") or None),
                    }
        except Exception as e:
            print(f"[enrich] catalog.csv 読込失敗: {e}", file=sys.stderr)
    if os.path.exists(_CACHE_PATH):
        try:
            with open(_CACHE_PATH, encoding="utf-8") as f:
                for k, v in json.load(f).items():
                    t, a = k.split("\t", 1)
                    _itunes_cache[(t, a)] = v
        except Exception:
            pass


def _itunes_lookup(title, artist):
    q = urllib.parse.urlencode({
        "term": f"{title} {artist}", "country": "JP",
        "media": "music", "entity": "song", "limit": 5})
    with urllib.request.urlopen(f"https://itunes.apple.com/search?{q}", timeout=6) as r:
        data = json.loads(r.read().decode("utf-8"))
    for item in data.get("results", []):
        # 正規化した完全一致系のみ。部分一致で誤ったジャケットを出さない (元ツールの方針)
        if _norm(item.get("trackName")) == _norm(title) and (
                _norm(artist) in _norm(item.get("artistName"))
                or _norm(item.get("artistName")) in _norm(artist)):
            art = (item.get("artworkUrl100") or "").replace("100x100bb.jpg", "600x600bb.jpg")
            return {"artwork": art or None}
    return {}


def enrich_loop():
    _load_enrich_sources()
    while True:
        try:
            with state_lock:
                decks = [dict(d) for d in state["decks"].values() if d]
            for d in decks:
                title, artist = d.get("title"), d.get("artist")
                if not title:
                    continue
                k = _key(title, artist)
                if k in _enrich:
                    continue
                entry = dict(_catalog.get(k) or _itunes_cache.get(k) or {})
                if not entry.get("artwork") and CFG.get("itunes_lookup", True):
                    try:
                        got = _itunes_lookup(title, artist)
                    except Exception:
                        got = None  # 通信失敗は未確定として次回再試行
                    if got is not None:
                        entry.update(got)
                        _itunes_cache[k] = entry
                        try:
                            with open(_CACHE_PATH, "w", encoding="utf-8") as f:
                                json.dump({"\t".join(kk): vv for kk, vv in _itunes_cache.items()},
                                          f, ensure_ascii=False)
                        except Exception:
                            pass
                _enrich[k] = entry
        except Exception:
            pass
        time.sleep(2.0)


# ---------- MIDI ----------

def load_midi_profiles():
    """学習済みプロファイルを [(ポート名の目印, map), ...] で返す。

    midi_maps/*.json (機種別) を優先し、旧形式の midi_map.json も読み込む。
    """
    profiles = []
    seen = set()

    def _add(port_hint, mmap):
        key = (port_hint or "").strip()
        if key and key not in seen:
            seen.add(key)
            profiles.append((key, mmap))

    if os.path.isdir(MIDI_MAPS_DIR):
        for fn in sorted(os.listdir(MIDI_MAPS_DIR)):
            if not fn.endswith(".json"):
                continue
            try:
                with open(os.path.join(MIDI_MAPS_DIR, fn), encoding="utf-8") as f:
                    mmap = json.load(f)
                _add(mmap.get("port") or fn[:-5], mmap)
            except Exception:
                pass
    if os.path.exists(MIDI_MAP_PATH):
        try:
            with open(MIDI_MAP_PATH, encoding="utf-8") as f:
                mmap = json.load(f)
            _add(mmap.get("port") or CFG.get("midi_port_hint", ""), mmap)
        except Exception:
            pass
    return profiles


def _match_profile(profiles, port_name):
    for hint, mmap in profiles:
        if hint and (hint in port_name or port_name in hint):
            return mmap
    return None


def _midi_session(mido, port_name, mmap):
    cc_map = {}
    for k, v in mmap.get("cc", {}).items():
        cc_map[v["cc"]] = (k, "msb")
        if v.get("cc_lsb") is not None:
            cc_map[v["cc_lsb"]] = (k, "lsb")
    note_map = {v["note"]: k for k, v in mmap.get("note", {}).items()}
    _raw = {}
    with mido.open_input(port_name) as port:
        for msg in port:
            if msg.type == "control_change" and msg.control in cc_map:
                key, part = cc_map[msg.control]
                if key in _faders:
                    raw = _raw.setdefault(key, {})
                    raw[part] = msg.value
                    if "msb" in raw and "lsb" in raw:
                        # 14bitフェーダー: MSB/LSBを合成して 0-127 スケールに戻す
                        _faders[key] = ((raw["msb"] << 7) | raw["lsb"]) / 16383.0 * 127.0
                    else:
                        _faders[key] = raw.get("msb", msg.value)
            elif msg.type == "note_on" and msg.velocity > 0 and msg.note in note_map:
                key = note_map[msg.note]
                if key == "play1":
                    _midi_playing[1] = not bool(_midi_playing[1])
                elif key == "play2":
                    _midi_playing[2] = not bool(_midi_playing[2])


def midi_loop():
    """接続中のコントローラーを自動判別し、抜き差しに追従する監視ループ。"""
    try:
        import mido
    except ImportError:
        print("[midi] mido が入っていません: pip3 install mido python-rtmidi")
        return
    announced_wait = False
    while True:
        profiles = load_midi_profiles()
        if not profiles:
            if not announced_wait:
                print("[midi] 学習済みプロファイルが無いため待機中。"
                      "先に midi_learn.py を実行してください (後から追加しても自動で拾います)。")
                announced_wait = True
            time.sleep(10)
            continue
        announced_wait = False
        try:
            names = mido.get_input_names()
        except Exception:
            names = []
        port_name, mmap = None, None
        for n in names:
            m = _match_profile(profiles, n)
            if m is not None:
                port_name, mmap = n, m
                break
        if port_name is None:
            time.sleep(5)
            continue
        print(f"[midi] 接続: {port_name}")
        with state_lock:
            state["midi_connected"] = True
        try:
            _midi_session(mido, port_name, mmap)
        except Exception as e:
            print(f"[midi] 切断されました ({e}) — 再接続を待ちます")
        with state_lock:
            state["midi_connected"] = False
        time.sleep(3)


# ---------- オンライン中継 (push) ----------

def push_loop():
    url = CFG.get("relay_url") or ""
    if not url:
        return
    room = (CFG.get("room") or "").strip()
    if room:
        # DJごとの部屋分け: relay_url に ?room=<dj名> を付けて送る
        url += ("&" if "?" in url else "?") + "room=" + urllib.parse.quote(room)
    while True:
        try:
            with state_lock:
                payload = json.dumps(state, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                url, data=payload, method="POST",
                headers={"Content-Type": "application/json",
                         "X-Token": CFG.get("relay_token", "")})
            urllib.request.urlopen(req, timeout=5).read()
        except Exception:
            pass  # 中継先に届かない間もローカル配信は続ける
        time.sleep(float(CFG["push_seconds"]))


# ---------- HTTP ----------

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/api"):
            with state_lock:
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
    threading.Thread(target=poll_loop, daemon=True).start()
    threading.Thread(target=midi_loop, daemon=True).start()
    threading.Thread(target=enrich_loop, daemon=True).start()
    threading.Thread(target=push_loop, daemon=True).start()
    port = int(CFG["port"])
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"NOW PLAYING server: http://localhost:{port}/")
    if CFG.get("relay_url"):
        print(f"オンライン中継: {CFG['relay_url']} へ push 中")
    print("停止: Ctrl+C")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
