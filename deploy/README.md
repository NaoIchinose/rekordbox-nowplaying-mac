# Oracle Cloud Always Free に中継サーバーを立てる手順

所要時間の目安：サインアップ15分 + サーバー構築10分。
費用は0円（Always Free枠内）。ただしサインアップ時に本人確認用のクレジットカード登録が必要です。

## 1. サインアップ（先生の作業）

1. https://www.oracle.com/jp/cloud/free/ から「無料で開始」
2. **ホームリージョンは「Japan East (Tokyo)」を選択**
   - Always Freeのリソースはホームリージョンでしか作れません。後から変更不可なので、ここだけ間違えないでください
3. アカウント作成後、30日間有効なトライアルクレジットが付きますが、期限が切れても Always Free のサーバーはそのまま残ります

## 2. サーバー（インスタンス）作成（先生の作業）

OCIコンソール > Compute > Instances > Create instance

- Name: `nowplaying-relay`
- Image: **Ubuntu 24.04**
- Shape: **VM.Standard.E2.1.Micro**（「Always Free eligible」の表示があるもの）
  - 中継にはこの最小構成で十分です。Arm (Ampere A1) は空きが無いことが多いので避けます
- Networking: パブリックIPの割り当てを有効にする
- SSH keys: 「Generate a key pair for me」で生成し、**秘密鍵ファイル (.key) を必ずダウンロードして保管**
- Create

作成できたら、インスタンスの **Public IP address** を控えてください。

## 3. ポート開放（先生の作業）

インスタンス詳細 > Virtual cloud network > Subnet > Security Lists > Default Security List

Ingress Rules に追加：

- Source CIDR: `0.0.0.0/0`
- IP Protocol: `TCP`
- Destination Port Range: `8765`

## 4. 中継プログラムの配置（Macから）

Macのターミナルで、このプロジェクトのフォルダから：

```bash
# 転送先フォルダが無いと scp が失敗するので、先に作る
ssh -i ~/Downloads/<秘密鍵>.key ubuntu@<パブリックIP> "mkdir -p ~/np"
scp -i ~/Downloads/<秘密鍵>.key -r relay.py overlay.html deploy \
  ubuntu@<パブリックIP>:~/np/
ssh -i ~/Downloads/<秘密鍵>.key ubuntu@<パブリックIP>
```

サーバー側で：

```bash
cd ~/np
sudo RELAY_TOKEN=<好きな合言葉> bash deploy/setup.sh
curl http://localhost:8765/api
```

`{"now": null, "next": null, ...}` のようなJSONが返れば稼働中です。

## 5. つなぐ

- **表示ページ**（PA/VJが開くURL）：`http://<パブリックIP>:8765/`
- **Mac側** `config.json` に設定：

```json
{
  "relay_url": "http://<パブリックIP>:8765/push",
  "relay_token": "<手順4で決めた合言葉>"
}
```

※ `relay_url` は末尾の `/push` まで必須です。`/push` が無いと中継サーバーは 404 を返し、Mac側はエラーを表示せず黙って送り続けるため、表示ページがずっと空のままになります。表示ページ自体は `http://<パブリックIP>:8765/`（`/push` なし）で合っています。

`start.command` でエージェントを起動すれば、Rekordboxの状態が中継され始めます。

## 注意

- **アイドル回収**：Always Freeは、7日間ほぼ無負荷だとインスタンスが回収されることがあります。イベント前日に `http://<パブリックIP>:8765/api` が応答するか必ず確認してください。万一止められていても、手順2〜4のやり直しで復旧できます（15分程度）
- 表示ページはURLを知っていれば誰でも見られます（NOW PLAYINGの情報のみ。送信は合言葉トークンで保護）。気になる場合はご相談ください
- サーバー再起動時もサービスは自動で立ち上がります（systemd）
