#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MIDIラーン v2: コントローラーを実際に動かして、MIDI番号を記録する。
DDJ-1000 / DDJ-FLX4 など、使うコントローラーごとに1回ずつ実行する。

v2の変更点: 自動確定をやめ、各ステップは Enter を押してから計測する方式に変更。
フェーダーは「値の振れ幅が大きいCC」を採用するので、微振動 (ジッター) や
残留メッセージで勝手に確定することはない。同じCCが重複したら警告してやり直す。

手順 (画面の指示に従うだけ):
  1. CH1フェーダーを 上→下
  2. CH2フェーダーを 上→下
  3. クロスフェーダーを 左→右
  4. DECK1 の PLAY を1回
  5. DECK2 の PLAY を1回
結果は midi_maps/<機種名>.json に保存される (nowplaying.py が接続中の機種を
自動判別して読み分ける)。互換のため midi_map.json にも同じ内容を書く。

必要: pip3 install mido python-rtmidi
注意: Rekordboxを起動したままでも構いません (macOSのMIDIは複数アプリで同時受信できます)。
"""
import json
import os
import re
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "midi_map.json")
MAPS_DIR = os.path.join(BASE, "midi_maps")

try:
    import mido
except ImportError:
    print("mido が入っていません。先に: pip3 install mido python-rtmidi")
    sys.exit(1)

STEPS = [
    ("cc", "ch1", "CH1フェーダー (左の縦フェーダー) を ゆっくり 上→下"),
    ("cc", "ch2", "CH2フェーダー (右の縦フェーダー) を ゆっくり 上→下"),
    ("cc", "cross", "クロスフェーダー (一番下の横フェーダー) を ゆっくり 左→右"),
    ("note", "play1", "DECK1 の PLAYボタン を 1回"),
    ("note", "play2", "DECK2 の PLAYボタン を 1回"),
]


def choose_port(names):
    if len(names) == 1:
        return names[0]
    default = next((i for i, n in enumerate(names)
                    if "DDJ" in n or "FLX" in n), 0)
    print("MIDI入力ポートが複数あります:")
    for i, n in enumerate(names):
        mark = " (Enterで選択)" if i == default else ""
        print(f"  {i + 1}: {n}{mark}")
    try:
        ans = input(f"番号を入力してください [{default + 1}]: ").strip()
    except EOFError:
        ans = ""
    if ans.isdigit() and 1 <= int(ans) <= len(names):
        return names[int(ans) - 1]
    return names[default]


def wait_enter(prompt):
    try:
        input(prompt)
    except EOFError:
        pass


def flush(port):
    for _ in port.iter_pending():
        pass


def learn_cc(port, used):
    """5秒間計測し、値の振れ幅が最大のCCを採用する。used と重複したら None。"""
    flush(port)
    stats = {}  # (channel, control) -> [count, min, max]
    deadline = time.time() + 5
    while time.time() < deadline:
        for msg in port.iter_pending():
            if msg.type == "control_change":
                s = stats.setdefault((msg.channel + 1, msg.control), [0, 127, 0])
                s[0] += 1
                s[1] = min(s[1], msg.value)
                s[2] = max(s[2], msg.value)
        time.sleep(0.02)
    if not stats:
        return None, "MIDI信号が来ませんでした"
    ranked = sorted(stats.items(),
                    key=lambda kv: (kv[1][2] - kv[1][1], kv[1][0]), reverse=True)
    (ch, cc), (cnt, lo, hi) = ranked[0]
    if hi - lo < 30:
        return None, f"振れ幅が小さいです (CC{cc}: {lo}〜{hi})。端から端まで動かしてください"
    if (ch, cc) in used:
        return None, f"CC{cc} は既に別のフェーダーで記録済みです。指定されたフェーダーを動かしてください"
    found = {"channel": ch, "cc": cc}
    # 14bitフェーダー (MSB/LSBペア): 同時に大きく振れた +32 のCCをLSBとする
    for (ch2, cc2), (cnt2, lo2, hi2) in ranked[1:]:
        if ch2 == ch and cc2 == cc + 32 and hi2 - lo2 >= 30:
            found["cc_lsb"] = cc2
            break
    return found, None


def learn_note(port):
    flush(port)
    deadline = time.time() + 15
    while time.time() < deadline:
        for msg in port.iter_pending():
            if msg.type == "note_on" and msg.velocity > 0:
                return {"channel": msg.channel + 1, "note": msg.note}
        time.sleep(0.02)
    return None


def main():
    names = mido.get_input_names()
    if not names:
        print("MIDI入力ポートがありません。コントローラーを接続してください。")
        sys.exit(1)
    port_name = choose_port(names)
    print(f"使用ポート: {port_name}")
    result = {"cc": {}, "note": {}, "port": port_name}
    used_cc = set()
    with mido.open_input(port_name) as port:
        for kind, key, instruction in STEPS:
            while True:
                print(f"\n>> {instruction}")
                wait_enter("   準備ができたら Enter を押してください (押した直後から計測します)...")
                if kind == "cc":
                    print("   計測中 (5秒): いまフェーダーを動かしてください")
                    found, err = learn_cc(port, used_cc)
                else:
                    print("   計測中: いまボタンを押してください")
                    found, err = learn_note(port), None
                if found:
                    print(f"   記録: {key} -> {found}")
                    ans = ""
                    try:
                        ans = input("   これでOKですか? [Enter=OK / r=やり直し]: ").strip().lower()
                    except EOFError:
                        ans = ""
                    if ans == "r":
                        continue
                    result[kind][key] = found
                    if kind == "cc":
                        used_cc.add((found["channel"], found["cc"]))
                    break
                print(f"   [未検出] {err or '信号が来ませんでした'}。もう一度試します")
    os.makedirs(MAPS_DIR, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", port_name).strip("_") or "device"
    profile_path = os.path.join(MAPS_DIR, safe + ".json")
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n保存しました: {profile_path}")
    print(f"（互換用コピー: {OUT}）")
    print("このファイルをユウカにも送ってください (マッピング確認用)。")


if __name__ == "__main__":
    main()
