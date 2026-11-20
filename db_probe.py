#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ハイブリッド方式の先行検証スクリプト (Mac で単体実行する)

Rekordbox の master.db を pyrekordbox で開けるか、ANLZ から波形が取れるかを
実機で確認するためのものです。master.db 本体は書き換えず、一時コピーを開きます。

使い方:
  pip3 install pyrekordbox
  python3 db_probe.py

最後に PROBE_OK / PROBE_NG の行が出ます。出力全体をユウカへ貼ってください。
"""
import os
import platform
import shutil
import sys
import tempfile

print(f"Python: {sys.version.split()[0]} / {platform.platform()}")


def ng(reason):
    print(f"PROBE_NG: {reason}")
    sys.exit(1)


try:
    import pyrekordbox
    print(f"[OK] pyrekordbox {getattr(pyrekordbox, '__version__', '?')} を読み込めました")
except Exception as e:
    print(f"[NG] pyrekordbox を読み込めません: {e}")
    print("     先に pip3 install pyrekordbox を実行してください")
    ng("pyrekordbox import")

from pyrekordbox import MasterDatabase
from pyrekordbox.config import get_config

cfg = get_config("rekordbox7") or get_config("rekordbox6")
src = (cfg or {}).get("db_path") or ""
print(f"master.db パス: {src}")
if not src or not os.path.exists(src):
    ng("master.db が見つかりません")
print(f"[OK] master.db 存在 ({os.path.getsize(src) / 1e6:.1f} MB)")

db_dir = os.path.dirname(src)
tmp = tempfile.mkdtemp(prefix="np-probe-")
try:
    dst = os.path.join(tmp, "master.db")
    shutil.copy2(src, dst)
    for suffix in ("-wal", "-shm"):
        if os.path.exists(src + suffix):
            try:
                shutil.copy2(src + suffix, dst + suffix)
            except Exception:
                pass
    try:
        db = MasterDatabase(path=dst, db_dir=db_dir)
    except Exception as e:
        ng(f"master.db を開けませんでした: {type(e).__name__}: {e}")
    print("[OK] master.db を開けました (一時コピー経由)")

    artists = {a.ID: a.Name for a in db.get_artist()}
    albums = {a.ID: a.Name for a in db.get_album()}
    contents = [c for c in db.get_content() if c.Title]
    print(f"[OK] コレクション: {len(contents)} 曲 / アーティスト {len(artists)} 件")

    sample = next((c for c in contents if c.AnalysisDataPath), None)
    if sample is None:
        ng("解析済み (ANLZあり) の曲が1曲もありません")
    print(f"サンプル曲: {sample.Title} / {artists.get(sample.ArtistID)}")
    print(f"  アルバム: {albums.get(sample.AlbumID)} / BPM: {(sample.BPM or 0) / 100} "
          f"/ 長さ: {sample.Length} 秒")
    cues = [q for q in db.get_cue(ContentID=sample.ID)]
    print(f"  キュー: {len(cues)} 件")
    db.close()

    # ジャケット
    art = sample.ImagePath or ""
    art_path = art if os.path.isabs(art) else os.path.join(db_dir, art)
    if art and os.path.exists(art_path):
        print(f"[OK] ジャケット: {art_path} ({os.path.getsize(art_path)} bytes)")
    else:
        print(f"[--] ジャケットは解決できませんでした: {art!r}")

    # ANLZ 波形
    from pyrekordbox.anlz import AnlzFile, get_anlz_paths
    anlz_full = (sample.AnalysisDataPath if os.path.isabs(sample.AnalysisDataPath)
                 else os.path.join(db_dir, sample.AnalysisDataPath.lstrip("/")))
    paths = get_anlz_paths(os.path.dirname(anlz_full))
    print(f"ANLZ ファイル: { {k: bool(v) for k, v in paths.items()} }")
    wave_ok = False
    if paths.get("EXT"):
        anlz = AnlzFile.parse_file(paths["EXT"])
        print(f"  EXT タグ: {anlz.tag_types()}")
        if "PWV4" in anlz:
            heights, _c, _b = anlz.get("PWV4")
            print(f"[OK] PWV4 波形: {len(heights)} 点")
            wave_ok = True
    if paths.get("DAT"):
        anlz = AnlzFile.parse_file(paths["DAT"])
        print(f"  DAT タグ: {anlz.tag_types()}")
        for tag in ("PWV3", "PWV2", "PWAV"):
            if tag in anlz:
                wf, _col = anlz.get(tag)
                print(f"[OK] {tag} 波形: {len(wf)} 点")
                wave_ok = True
                break
        if "PQTZ" in anlz:
            print(f"  ビートグリッド: {anlz.get_tag('PQTZ').count} 拍")
    if not wave_ok:
        ng("波形タグが見つかりませんでした")
    print("PROBE_OK: master.db 読み取り・波形取得ともに可能です")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
