#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MIDIラーン: DDJ-1000の操作を実際に動かして、MIDI番号を記録する。
DDJ-1000のMIDIマッピングは機材依存の部分があるため、推測で決めず実機で学習する。

手順 (画面の指示に従ってコントローラーを操作するだけ):
  1. CH1フェーダーを 上→下
  2. CH2フェーダーを 上→下
  3. クロスフェーダーを 左→右
  4. DECK1 の PLAY を1回
  5. DECK2 の PLAY を1回
結果は midi_map.json に保存される。

必要: pip3 install mido python-rtmidi
注意: Rekordboxを起動したままでも構いません (macOSのMIDIは複数アプリで同時受信できます)。
"""
import json
import os
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "midi_map.json")

try:
    import mido
except ImportError:
    print("mido が入っていません。先に: pip3 install mido python-rtmidi")
    sys.exit(1)

STEPS = [
    ("cc", "ch1", "CH1フェーダーを ゆっくり 上→下 へ動かしてください"),
    ("cc", "ch2", "CH2フェーダーを ゆっくり 上→下 へ動かしてください"),
    ("cc", "cross", "クロスフェーダーを ゆっくり 左→右 へ動かしてください"),
    ("note", "play1", "DECK1 の PLAYボタンを 1回 押してください"),
    ("note", "play2", "DECK2 の PLAYボタンを 1回 押してください"),
]


def main():
    names = mido.get_input_names()
    if not names:
        print("MIDI入力ポートがありません。DDJ-1000を接続してください。")
        sys.exit(1)
    port_name = next((n for n in names if "DDJ-1000" in n), names[0])
    print(f"使用ポート: {port_name}")
    result = {"cc": {}, "note": {}, "port": port_name}
    with mido.open_input(port_name) as port:
        for kind, key, instruction in STEPS:
            print("\n>> " + instruction + " (10秒待ちます)")
            found = None
            deadline = time.time() + 10
            counts = {}
            last_seen = {}
            while time.time() < deadline and found is None:
                for msg in port.iter_pending():
                    if kind == "cc" and msg.type == "control_change":
                        counts[msg.control] = counts.get(msg.control, 0) + 1
                        last_seen[msg.control] = (msg.channel + 1, msg.value)
                        if max(counts.values()) >= 10:  # 十分動いたら確定
                            primary = max(counts, key=counts.get)
                            others = {c: n for c, n in counts.items()
                                      if c != primary and n >= 4}
                            lsb = max(others, key=others.get) if others else None
                            found = {"channel": last_seen[primary][0], "cc": primary}
                            if lsb is not None:
                                # 14bitフェーダー (MSB/LSBペア) の可能性があるため併記する
                                found["cc_lsb"] = lsb
                    elif kind == "note" and msg.type == "note_on" and msg.velocity > 0:
                        found = {"channel": msg.channel + 1, "note": msg.note}
                time.sleep(0.05)
            if found:
                result[kind][key] = found
                print(f"   記録: {key} -> {found}")
            else:
                print(f"   [未検出] {key} は記録できませんでした (後で再実行できます)")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n保存しました: {OUT}")
    print("このファイルをユウカにも送ってください (マッピング確認用)。")


if __name__ == "__main__":
    main()
