#!/bin/bash
# Oracle Cloud (Ubuntu) に NOW PLAYING 中継サーバーを立てるセットアップ
# 使い方: relay.py と overlay.html と同じフォルダで
#   sudo RELAY_TOKEN=好きな合言葉 bash setup.sh
set -e

if [ -z "$RELAY_TOKEN" ]; then
  echo "RELAY_TOKEN を指定してください: sudo RELAY_TOKEN=合言葉 bash setup.sh"
  exit 1
fi

APP_DIR=/opt/nowplaying-relay
mkdir -p "$APP_DIR"
# relay.py / overlay.html は、このスクリプトと同じフォルダか1つ上のフォルダにある想定
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ ! -f "$SRC_DIR/relay.py" ]; then
  SRC_DIR="$(dirname "$SRC_DIR")"
fi
cp "$SRC_DIR/relay.py" "$APP_DIR/relay.py"
cp "$SRC_DIR/overlay.html" "$APP_DIR/overlay.html"

# 専用ユーザー
id relay >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin relay
chown -R relay:relay "$APP_DIR"

# systemd サービス
cat > /etc/systemd/system/nowplaying-relay.service <<EOF
[Unit]
Description=Rekordbox NOW PLAYING relay
After=network.target

[Service]
User=relay
WorkingDirectory=$APP_DIR
Environment=RELAY_TOKEN=$RELAY_TOKEN
ExecStart=/usr/bin/python3 $APP_DIR/relay.py 8765
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now nowplaying-relay

# OCIのUbuntuイメージは iptables で大半のポートが塞がれているため開放する
iptables -C INPUT -p tcp --dport 8765 -j ACCEPT 2>/dev/null || \
  iptables -I INPUT 5 -p tcp --dport 8765 -j ACCEPT
if command -v netfilter-persistent >/dev/null 2>&1; then
  netfilter-persistent save || true
fi

echo ""
echo "=== セットアップ完了 ==="
systemctl --no-pager status nowplaying-relay | head -5
echo ""
echo "確認: curl http://localhost:8765/api"
echo "外部からは http://<このVMのパブリックIP>:8765/ が表示ページです"
echo "OCIコンソール側で Security List の Ingress (TCP 8765, 0.0.0.0/0) も必要です"
