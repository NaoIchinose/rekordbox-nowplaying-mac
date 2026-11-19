# Rekordbox 7 NOW PLAYING（Mac版）v1

Xで見かけた「Rekordboxの再生中情報をOBSにリアルタイム表示するツール」のMac版。

## 仕様（v1）

- **曲情報**: Rekordbox 7の画面要素をmacOSアクセシビリティで取得（曲名・アーティスト・BPM）
- **MIDI**: DDJ-1000から 再生/停止・CHフェーダー・クロスフェーダーを取得
- **オンエア判定**: フェーダー位置×再生状態から計算（MIDIなしの場合は時間表示の進行で判定）
- **NOW PLAYING / NEXT**: オンエア中の曲と、もう一方のデッキにロードされた次の曲を表示
- **オンライン中継**: Macが状態JSONを中継サーバーへpushし、VJ/PAや配信側はURLを開くだけで表示できる

対象: MacBook Air Late 2018 / macOS Sonoma / Rekordbox 7 / DDJ-1000
依存: Python 3 標準ライブラリのみ（MIDI使用時のみ `mido` と `python-rtmidi`）

## ファイル

| ファイル | 役割 |
|---|---|
| `nowplaying.py` | Mac側エージェント（読み取り＋ローカル配信＋中継push） |
| `relay.py` | オンライン中継サーバー（配置先はどこでも） |
| `deploy/` | Oracle Cloud Always Free への配置手順とセットアップスクリプト |
| `overlay.html` | OBSブラウザソース用表示（NOW/NEXT/フェーダーバー） |
| `probe.applescript` | 画面要素の診断（初回キャリブレーション用） |
| `midi_learn.py` | DDJ-1000のMIDI番号を実機で学習 → `midi_map.json` |
| `start.command` | エージェント起動（ダブルクリック） |
| `config.example.json` | 設定の見本（コピーして `config.json` にする） |

## セットアップ

### 1. 権限（初回のみ）
システム設定 > プライバシーとセキュリティ > アクセシビリティ で「ターミナル」をオン。

### 2. 画面のキャリブレーション（初回のみ）
1. Rekordbox 7で両デッキに曲をロード（片方は再生）
2. `osascript probe.applescript`
3. デスクトップの `rekordbox-ui-dump.txt` をユウカに送る → 抽出を確定版に差し替え

### 3. MIDIラーン（初回のみ）
1. `pip3 install mido python-rtmidi`
2. DDJ-1000を接続して `python3 midi_learn.py`
3. 画面の指示どおりフェーダーとPLAYを操作 → `midi_map.json` ができる
   （Rekordbox起動中でも同時受信できる）

### 4. エージェント起動
`start.command` をダブルクリック。ローカル確認: http://localhost:8765/

### 5. オンライン中継を使う場合
1. 中継先（VPS・自宅PCなど）で: `RELAY_TOKEN=合言葉 python3 relay.py 8765`
   ※ `relay.py` と `overlay.html` を同じフォルダに置く
2. Mac側 `config.json` に `"relay_url": "http://中継先:8765/push"` と
   `"relay_token": "合言葉"` を書く
3. VJ/PA・配信OBSは `http://中継先:8765/` をブラウザソースで開く

代替案: 中継サーバーを置かず、Cloudflare Tunnel等でMacの8765番を
一時URL化する方法もある（URLが毎回変わる・トンネルの常駐が増える点に注意）。

### 6. OBS
ブラウザソース URL は、ローカルなら `http://localhost:8765/`、
中継なら中継先のURL。最軽量設定（720p30・録画/配信なし）のまま。

## 状態JSON（/api の中身）

- `decks.1 / decks.2`: title / artist / bpm / playing / position_sec（経過秒）/ remaining_sec（残り秒）/ duration_sec（曲の長さ）/ progress（0–1）/ work（作品名）/ artwork（ジャケットURL）
- `on_air`: オンエア中のデッキ番号
- `next`: { deck, title, artist, bpm, duration_sec, work, artwork }
- `faders`: { ch1, ch2, cross }（0–127、未取得なら null）
- `midi_connected`: MIDI受信の有無

## 楽曲メタデータ（作品名・ジャケット）

- `catalog.csv`（列: title, artist, work, artwork）を置くと、曲名＋アーティストの
  完全一致で作品名（タイアップ等）とジャケットURLを付加する。見本は `catalog.example.csv`
- ジャケットが無い曲は iTunes Search API で補完し、`artwork_cache.json` に保存する
  （`config.json` の `"itunes_lookup": false` で無効化できる）
- 照合は正規化した完全一致系のみ。部分一致で別曲のジャケットを出す事故を防ぐ

## 参考にした元ツールから取り入れた設計

元ツール: nobutama_31 氏の note 記事と GitHub `NobuTama31/rekordbox-sync`（Windows版）

- ツールチップ等の小窓を掴まないよう、対象は「一番面積の大きいウィンドウ」にする
- BEAT SYNCボタン等のアンカーと幾何関係でデッキを分ける（ツリーの並び順に依存しない）
- オンエア表示はヒステリシス：今のデッキのフェーダーが上がっている間は切り替えず、
  下げ切った時点で切り替える（ミックス中のチラつき防止）
- 取得が部分的に欠けたら「情報なし」として前回の正常値を短時間保持する
- 分からない値は推測で埋めず null のままにする（フェーダーは接続後に動かすまで不明）
- フェーダーは14bit（MSB/LSBペア）の可能性を考慮する

## v1の制限

- 画面抽出は位置ベース推定（プローブのダンプで確定版に差し替え予定）
- ジャケット/作品名は catalog.csv と iTunes の照合が当たった曲だけ出る（外れた曲は仮表示のまま）
- 再生/停止の判定は、時間表示の進行を優先する（2回連続で読めた場合）。
  時間表示が読めないときだけMIDIのPLAYトグルを使う。シーク直後の
  1ポーリングだけ再生扱いになることがある
- 負荷が基準を超えたら、このツールは止めてミラーリング案に戻す
