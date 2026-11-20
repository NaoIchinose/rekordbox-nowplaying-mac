#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ハイブリッド補完モジュール (NOW PLAYING ツール用)

Rekordbox の master.db (SQLCipher) と ANLZ 解析ファイルから、
画面読みで得た曲名・アーティストをキーに以下を引く:
- アルバム名 / 正確な長さ / キー (DB上の値)
- 波形データ (ANLZ の PWV4 カラープレビュー優先、無ければ PWV2/PWV3)
- キュー位置 (ホットキュー・メモリーキューの InMsec)
- ジャケット画像 (share/artwork 内の実ファイル。大きければ sips で縮小)

前提: pyrekordbox (pip install pyrekordbox)。sqlcipher3 は wheel 同梱。
前提が無い / DB が開けない場合は available=False になり、
呼び出し側 (nowplaying.py) は従来動作 (画面読み + iTunes補完) を続ける。

安全策:
- master.db は Rekordbox が使用中のため、必ず一時コピー (-wal/-shm 含む) を開く。
  本体ファイルには一切書き込まない。
- 索引の再構築はバックグラウンドスレッドで行い、再生中の取得ループを止めない。
"""
import base64
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

WAVE_POINTS = 360          # 表示ページへ送る波形の点数
ARTWORK_MAX_BYTES = 45000  # これを超えるジャケットは送らない (iTunes補完に任せる)
INDEX_REFRESH_SEC = 1800   # 索引の再構築間隔
RETRY_SEC = 120            # 構築失敗時の再試行間隔


def _norm(s):
    return re.sub(r"\s+", "", (s or "")).lower()


class DbMeta:
    def __init__(self):
        self.available = False
        self._index = {}       # (norm_title, norm_artist) -> summary
        self._by_title = {}    # norm_title -> [summary, ...]
        self._cues = {}        # content_id -> [(msec, kind), ...]
        self._payload_cache = {}  # content_id -> payload dict
        self._lock = threading.Lock()
        self._built_at = 0.0
        self._last_try = 0.0
        self._building = False
        self._db_dir = None

    # ---------- 起動・索引構築 ----------

    def start(self):
        self._maybe_build()

    def _maybe_build(self):
        now = time.time()
        with self._lock:
            if self._building:
                return
            if self.available and now - self._built_at < INDEX_REFRESH_SEC:
                return
            if not self.available and now - self._last_try < RETRY_SEC:
                return
            self._building = True
            self._last_try = now
        threading.Thread(target=self._build_guarded, daemon=True).start()

    def _build_guarded(self):
        try:
            self._build()
        except Exception as e:
            print(f"[dbmeta] master.db を開けませんでした (従来動作を継続): {e}",
                  file=sys.stderr)
            with self._lock:
                self._building = False

    def _build(self):
        from pyrekordbox import MasterDatabase
        from pyrekordbox.config import get_config

        cfg = get_config("rekordbox7") or get_config("rekordbox6")
        src = (cfg or {}).get("db_path") or ""
        if not src or not os.path.exists(src):
            raise FileNotFoundError(f"master.db が見つかりません: {src!r}")
        db_dir = os.path.dirname(src)

        tmp = tempfile.mkdtemp(prefix="np-dbmeta-")
        try:
            dst = os.path.join(tmp, "master.db")
            shutil.copy2(src, dst)
            for suffix in ("-wal", "-shm"):
                if os.path.exists(src + suffix):
                    try:
                        shutil.copy2(src + suffix, dst + suffix)
                    except Exception:
                        pass
            db = MasterDatabase(path=dst, db_dir=db_dir)
            try:
                artists = {a.ID: a.Name for a in db.get_artist()}
                albums = {a.ID: a.Name for a in db.get_album()}
                try:
                    keys = {k.ID: k.ScaleName for k in db.get_key()}
                except Exception:
                    keys = {}
                cues = {}
                try:
                    for cue in db.get_cue():
                        if cue.InMsec is not None:
                            cues.setdefault(cue.ContentID, []).append(
                                (int(cue.InMsec), int(cue.Kind or 0)))
                except Exception:
                    cues = {}
                index, by_title = {}, {}
                for c in db.get_content():
                    if not c.Title:
                        continue
                    s = {
                        "id": c.ID,
                        "title": c.Title,
                        "artist": artists.get(c.ArtistID) or "",
                        "album": albums.get(c.AlbumID) or None,
                        "bpm": (c.BPM / 100.0) if c.BPM else None,
                        "key": keys.get(c.KeyID),
                        "length": c.Length or None,
                        "comment": c.Commnt or None,
                        "image_path": c.ImagePath or None,
                        "analysis_path": c.AnalysisDataPath or None,
                    }
                    k = (_norm(c.Title), _norm(s["artist"]))
                    index.setdefault(k, s)
                    by_title.setdefault(_norm(c.Title), []).append(s)
            finally:
                db.close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

        with self._lock:
            self._index, self._by_title, self._cues = index, by_title, cues
            self._db_dir = db_dir
            self._built_at = time.time()
            self._building = False
            self.available = True
        print(f"[dbmeta] master.db 索引構築完了: {len(index)} 曲")

    # ---------- 検索 ----------

    def lookup(self, title, artist, duration_sec=None):
        """画面読みの (曲名, アーティスト) から DB の曲を引く。無ければ None。"""
        if not self.available:
            self._maybe_build()
            return None
        with self._lock:
            index, by_title = self._index, self._by_title
        s = index.get((_norm(title), _norm(artist or "")))
        if s is not None:
            return s
        cands = by_title.get(_norm(title)) or []
        if len(cands) == 1:
            return cands[0]
        if cands and duration_sec:
            close = [c for c in cands
                     if c["length"] and abs(c["length"] - duration_sec) <= 3]
            if len(close) == 1:
                return close[0]
        self._maybe_build()  # 新規追加曲かもしれないので鮮度を回復しておく
        return None

    # ---------- 波形・キュー・ジャケット ----------

    def payload(self, summary):
        """曲ごとの重いデータ (波形・キュー・ジャケット) を返す。結果はキャッシュする。"""
        cid = summary["id"]
        with self._lock:
            cached = self._payload_cache.get(cid)
            cues = list(self._cues.get(cid) or [])
        if cached is not None:
            return cached
        out = {
            "waveform": self._waveform(summary),
            "cues": sorted(t / 1000.0 for t, _kind in cues)[:32] or None,
            "artwork_data": self._artwork_data(summary),
        }
        with self._lock:
            self._payload_cache[cid] = out
        return out

    def _anlz_dir(self, summary):
        ap = summary.get("analysis_path")
        if not ap or not self._db_dir:
            return None
        full = ap if os.path.isabs(ap) else os.path.join(self._db_dir, ap.lstrip("/"))
        d = os.path.dirname(full)
        return d if os.path.isdir(d) else None

    def _waveform(self, summary):
        try:
            from pyrekordbox.anlz import AnlzFile, get_anlz_paths
            d = self._anlz_dir(summary)
            if not d:
                return None
            paths = get_anlz_paths(d)
            vals = None
            if paths.get("EXT"):
                anlz = AnlzFile.parse_file(paths["EXT"])
                if "PWV4" in anlz:
                    heights, _c, _b = anlz.get("PWV4")
                    vals = [max(int(f), int(b)) for f, b in heights]
            if vals is None and paths.get("DAT"):
                anlz = AnlzFile.parse_file(paths["DAT"])
                for tag in ("PWV3", "PWV2", "PWAV"):
                    if tag in anlz:
                        wf, _col = anlz.get(tag)
                        vals = [int(v) for v in wf]
                        break
            if not vals:
                return None
            vmax = max(vals) or 1
            norm = [v * 31 // vmax for v in vals]
            if len(norm) <= WAVE_POINTS:
                return norm
            step = len(norm) / WAVE_POINTS
            return [max(norm[int(i * step):int((i + 1) * step)] or [0])
                    for i in range(WAVE_POINTS)]
        except Exception as e:
            print(f"[dbmeta] 波形取得失敗 ({summary.get('title')}): {e}",
                  file=sys.stderr)
            return None

    def _artwork_data(self, summary):
        try:
            rel = summary.get("image_path")
            if not rel or not self._db_dir:
                return None
            candidates = [rel] if os.path.isabs(rel) else [
                os.path.join(self._db_dir, rel),
                os.path.join(self._db_dir, "share", rel),
                os.path.join(self._db_dir, rel.lstrip("/")),
            ]
            path = next((p for p in candidates if os.path.exists(p)), None)
            if not path:
                return None
            with open(path, "rb") as f:
                data = f.read()
            ext = os.path.splitext(path)[1].lower()
            mime = "image/png" if ext == ".png" else "image/jpeg"
            if len(data) > ARTWORK_MAX_BYTES:
                data = self._shrink(path)
                if not data:
                    return None
                mime = "image/jpeg"
            return f"data:{mime};base64," + base64.b64encode(data).decode("ascii")
        except Exception:
            return None

    @staticmethod
    def _shrink(path):
        """macOS 標準の sips で長辺192pxのJPEGに縮小する。失敗したら None。"""
        if sys.platform != "darwin":
            return None
        try:
            fd, out = tempfile.mkstemp(suffix=".jpg")
            os.close(fd)
            subprocess.run(
                ["sips", "-s", "format", "jpeg", "-Z", "192", path, "--out", out],
                check=True, capture_output=True, timeout=10)
            with open(out, "rb") as f:
                data = f.read()
            os.unlink(out)
            return data if 0 < len(data) <= ARTWORK_MAX_BYTES else None
        except Exception:
            return None
