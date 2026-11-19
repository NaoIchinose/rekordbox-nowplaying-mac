#!/bin/bash
# NOW PLAYING サーバー起動（ダブルクリック用）
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 が見つかりません。"
  echo "ターミナルで xcode-select --install を実行するか、python.org から Python 3 を入れてください。"
  read -p "Enterキーで閉じます"
  exit 1
fi
echo "NOW PLAYING サーバーを起動します: http://localhost:8765/"
echo "止めるときは このウィンドウで Ctrl+C"
python3 nowplaying.py
