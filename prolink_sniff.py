#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PRO DJ LINK パケット観測スクリプト (受信専用・何も送信しない)

UDP 50000〜50002 を60秒間聞いて、ポートごとのパケット数・サイズ・
読み取れた文字列 (機器名など) を集計する。
DJ側の Rekordbox が再生状態を LINK に流しているかの切り分け用。

使い方: python3 prolink_sniff.py
"""
import re
import socket
import time
from collections import Counter

DUR = 60
PORTS = (50000, 50001, 50002)

socks = []
for port in PORTS:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except AttributeError:
        pass
    s.bind(("", port))
    s.setblocking(False)
    socks.append((port, s))

print(f"{DUR}秒間、PRO DJ LINK のパケットを観測します。")
print("この間に DJ側の Rekordbox で LINK を有効にして、DECK1 を再生してください。")
print("途中で一度ポーズを挟むと、再生状態のパケットかどうか判別しやすくなります。")
print("観測中...")

counts = Counter()
sizes = Counter()
senders = Counter()
strings = Counter()
first_seen = {}
end = time.time() + DUR
while time.time() < end:
    for port, s in socks:
        try:
            data, addr = s.recvfrom(65535)
        except BlockingIOError:
            continue
        except OSError:
            continue
        counts[port] += 1
        sizes[(port, len(data))] += 1
        senders[addr[0]] += 1
        if port not in first_seen:
            first_seen[port] = DUR - (end - time.time())
        for m in re.findall(rb"[\x20-\x7e]{4,}", data):
            strings[m.decode("ascii", "replace")] += 1
    time.sleep(0.01)

print("\n=== 結果 ===")
for port in PORTS:
    t = f" (最初は開始 {first_seen[port]:.0f} 秒後)" if port in first_seen else ""
    print(f"port {port}: {counts[port]} パケット{t}")
print("送信元IP:", dict(senders) or "なし")
print("サイズ分布 (ポート,バイト数): 回数 =", dict(sizes) or "なし")
print("読み取れた文字列:")
if strings:
    for text, c in strings.most_common(20):
        print(f"  x{c}: {text}")
else:
    print("  なし")
print("\n判定の目安:")
print("  50000 に機器名 (rekordbox等) → LINK上に機器がいる")
print("  50001/50002 に多数のパケット → 再生状態が流れている可能性あり")
print("  全部 0 → この構成では LINK に何も流れていない")
