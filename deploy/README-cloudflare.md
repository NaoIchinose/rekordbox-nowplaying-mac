# Cloudflare Workers に中継サーバーを立てる手順

クレジットカード不要。メールアドレスだけで登録できます。
所要時間の目安：15分。プログラムは `cloudflare/worker.js`（検証済み）。

## 1. Cloudflareアカウント作成

1. https://dash.cloudflare.com/sign-up を開く
2. メールアドレスとパスワードで登録（カード登録はありません）
3. 確認メールのリンクを開いて認証

## 2. Workerを作る

1. 左メニューの「Workers & Pages」>「Create」>「Create Worker」
2. 名前は `rekordbox-relay`（URLが `https://rekordbox-relay.<あなたのサブドメイン>.workers.dev` になります）
3. 「Deploy」で一旦デプロイ（中身は後で差し替えます）

## 3. コードを差し替える

1. 作成したWorkerの「Edit code」を開く
2. 既存のコードを全部消して、`cloudflare/worker.js` の内容を貼る
3. 「Deploy」

## 4. 状態の保存先（Durable Object）を結びつける

1. Workerの「Settings」>「Bindings」>「Add」>「Durable Object」
2. Variable name：`RELAY`
3. Class name：`RelayState`（このWorker内のクラスを選ぶ）
4. 保存

## 5. 合言葉を設定する

1. Workerの「Settings」>「Variables and Secrets」>「Add」
2. Type：Secret、名前：`RELAY_TOKEN`、値：Mac側 config.json と同じ合言葉
3. 「Deploy」

## 6. つなぐ

- **表示ページ**（PA/VJが開くURL）：`https://rekordbox-relay.<サブドメイン>.workers.dev/`
- **Mac側** `config.json`：

```json
{
  "relay_url": "https://rekordbox-relay.<サブドメイン>.workers.dev/push",
  "relay_token": "<手順5の合言葉>"
}
```

## 注意（無料プランの仕様）

- 無料枠は1日10万リクエストまで。Macからの送信は1秒に1回なので、**24時間つけっぱなしだと約8.6万回**に達します。使う時だけエージェントを起動する運用なら問題ありません（4時間のイベントで約1.4万回）
- スリープはありません。いつ開いても即表示されます
- 状態はメモリ保持ではなく Durable Object に集約しているので、表示が食い違うことはありません
