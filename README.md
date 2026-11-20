# Rekordbox NOW PLAYING（Mac版）

Rekordbox 7（macOS）の再生中情報を、ブラウザで開ける表示ページにリアルタイムで出すツールです。
Xで見かけた Windows 向けの同種ツールをきっかけに、Mac 版として作り直しました。OBS は不要で、表示ページの URL を開くだけで PA / VJ と共有できます。

## できること

- **NOW PLAYING / NEXT 表示**：オンエア中の曲と、もう一方のデッキにロードされた次の曲
- **波形とキュー表示**（ハイブリッド方式）：Rekordbox の `master.db` と解析データ（ANLZ）を読み、波形・キュー・ジャケット・コメントを補完。DB が読めない環境では画面読み取りのみで自動継続
- **遅延補正**：再生位置にサンプリング時刻を持たせ、表示側で外挿するので、転送遅延ぶん表示が遅れません
- **MIDI 連携**：再生/停止・チャンネルフェーダー・クロスフェーダーを取得してオンエア判定。DDJ-1000 / DDJ-FLX4 対応（機種別プロファイル＋自動判別＋抜き差し自動再接続、初回のみ MIDI ラーンが必要）
- **複数 DJ 対応**：中継 URL に `?room=<DJ名>` を付けると DJ ごとに状態を分離。表示ページ上部のチップで切替、AUTO で再生中の DJ を自動追従
- **中継**：Cloudflare Workers（推奨）または同梱の `relay.py`。Mac から push する方式なので、表示側は URL を開くだけ

## 動作環境

- macOS（開発・検証：MacBook Air Late 2018 / macOS Sonoma）
- Rekordbox 7
- Python 3（本体は標準ライブラリのみ）
- 任意依存：MIDI を使う場合 `pip3 install mido python-rtmidi`／波形などの DB 補完を使う場合 `pip3 install pyrekordbox`

## セットアップ

詳しい手順は [MAC-SETUP.md](MAC-SETUP.md) を参照してください。流れだけ書くと：

1. システム設定 > プライバシーとセキュリティ > アクセシビリティ で「ターミナル」を許可
2. `config.example.json` を `config.json` にコピーし、中継 URL と合言葉（relay_token）、自分の `room` を設定
3. MIDI を使う場合は `python3 midi_learn.py` で接続機種ごとに 1 回だけラーン
4. ハイブリッド方式を使う場合は `pip3 install pyrekordbox` のあと `python3 db_probe.py` で読み取り可否を確認
5. `start.command` をダブルクリックで起動

中継を Cloudflare Workers に置く場合は `cloudflare/worker.js` をデプロイし、合言葉を Worker のシークレット（RELAY_TOKEN）に設定します。手順は `deploy/README-cloudflare.md` にあります。

## ファイル

| ファイル | 役割 |
|---|---|
| `nowplaying.py` | Mac 側エージェント（画面読み取り＋MIDI＋ローカル配信＋中継 push） |
| `dbmeta.py` | ハイブリッド補完（master.db / ANLZ から波形・キュー・ジャケット・コメント） |
| `db_probe.py` | ハイブリッド方式が使えるかの事前検証 |
| `overlay.html` | 表示ページ（NOW PLAYING / NEXT / 波形 / フェーダー）。`?transparent=1` で OBS ブラウザソース用 |
| `relay.py` | ローカル / 汎用の中継サーバー（部屋分け対応） |
| `cloudflare/worker.js` | Cloudflare Workers 用中継（表示ページ同梱） |
| `midi_learn.py` | コントローラの MIDI 番号を実機で学習 |
| `probe.applescript` | 画面要素の診断（キャリブレーション用） |
| `prolink_sniff.py` | PRO DJ LINK のパケット受信テスト（受信のみ） |
| `start.command` | エージェント起動（ダブルクリック） |
| `config.example.json` | 設定の見本（コピーして `config.json` にする） |
| `MAC-SETUP.md` | セットアップ手順の詳細 |

## 注意

- **`config.json` は絶対にコミットしないでください**（合言葉が入ります）。`.gitignore` で除外済みです
- MIDI ラーン結果（`midi_maps/`）も個人の実機データなので `.gitignore` で除外しています
- Rekordbox の画面構成が変わると画面読み取りの調整が必要になる場合があります

## ライセンス

MIT License（[LICENSE](LICENSE) 参照）
