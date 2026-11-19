# Render（無料）に中継サーバーを立てる手順

クレジットカード不要。GitHubアカウントで登録して、リポジトリを選ぶだけです。
所要時間の目安：10分。

## 1. リポジトリに3ファイルを追加

このプロジェクトのルートに、次の3ファイルが入っていることを確認してください
（GitHubの「Add file > Upload files」で追加できます）。

- `render.yaml`
- `requirements.txt`
- 既存の `relay.py` / `overlay.html`

## 2. Renderに登録

1. https://render.com を開く
2. 「Get Started for Free」→ **GitHubでサインアップ**（カード登録はありません）

## 3. サービス作成

1. ダッシュボードで「New」>「Blueprint」を選ぶ
2. リポジトリ `rekordbox-nowplaying-mac` を接続（初回はGitHub側で許可が要ります）
3. `render.yaml` が読み込まれ、サービス名 `rekordbox-nowplaying-relay` が表示される
4. 環境変数 `RELAY_TOKEN` の入力を求められるので、**好きな合言葉**を決めて入力
5. 「Apply」でデプロイ開始。数分で `https://rekordbox-nowplaying-relay.onrender.com` のようなURLが発行されます

## 4. つなぐ

- **表示ページ**（PA/VJが開くURL）：`https://<発行されたURL>/`
- **Mac側** `config.json`：

```json
{
  "relay_url": "https://<発行されたURL>/push",
  "relay_token": "<手順3で決めた合言葉>"
}
```

## 注意（無料プランの仕様）

- 15分間アクセスがないとスリープし、次のアクセスで起きるまで約1分かかります。本番中はMacが毎秒pushするので寝ません。イベント開始前に一度ページを開いて起こしておくのが安全です
- 無料枠は月750時間まで。1サービス常時稼働でほぼ使い切る量なので、他に無料サービスを増やすと足りなくなります
- URLは公開されます。表示されるのはNOW PLAYINGの情報のみで、送信は合言葉トークンで保護されています
