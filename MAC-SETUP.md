# Mac側セットアップ手順（帰宅後にやる分）

中継サーバーは開通済み。表示URL： https://rekordbox-relay.naoichinose97329.workers.dev/
Mac側に残っているのは、初回だけの調整2つ（プローブとMIDIラーン）です。

## 0. 準備（初回のみ）

1. プロジェクトフォルダをMacに置く
   - https://github.com/NaoIchinose/rekordbox-nowplaying-mac を開く
   - 緑の「Code」ボタン →「Download ZIP」→ 解凍して好きな場所に置く
2. フォルダの中に、ユウカから送った **config.json** を入れる（完成版・URLと合言葉入り）

## 1. 権限（初回のみ）

- システム設定 > プライバシーとセキュリティ > **アクセシビリティ** で「ターミナル」をオン

## 2. 画面のプローブ（初回のみ）→ ファイルをユウカに送る

1. Rekordbox 7を起動して、両デッキに曲をロードする（片方は再生しておく）
2. ターミナルでフォルダに移動して実行：

```bash
cd <プロジェクトフォルダのパス>
osascript probe.applescript
```

3. デスクトップにできる **rekordbox-ui-dump.txt** をユウカに送る

## 3. MIDIラーン（初回のみ）→ ファイルをユウカに送る

1. コントローラーを接続する（DDJ-1000 / DDJ-FLX4 のどちらでも可）
2. ターミナルで実行：

```bash
pip3 install mido python-rtmidi
python3 midi_learn.py
```

3. 複数のポートが出たら、使用するコントローラーの番号を選ぶ
4. 画面の指示どおりに、PLAYボタンとフェーダーを操作する
5. フォルダ内の **midi_maps** フォルダにできる機種名のファイルをユウカに送る
6. 両方のコントローラーを使う場合は、もう1台でも同じ手順を繰り返す（機種ごとにファイルが分かれるので、後から差し替えても大丈夫です）

## 4. 仕上げ（ユウカ側の作業）
- 送ってもらった2ファイルをもとに、曲情報の抽出とMIDIマッピングを実機合わせの確定版に差し替えます。Mac側の作業はありません

## 5. 起動確認

1. **start.command** をダブルクリック（止めるときはそのウィンドウで Ctrl+C）
2. iPhoneで表示URLを開いて、再生中の曲が NOW PLAYING に出るか確認
   - https://rekordbox-relay.naoichinose97329.workers.dev/
   - ローカル確認だけなら http://localhost:8765/ でも見られます

## 6. 複数DJで使う場合（部屋分け）

- DJごとに **config.json の `room`** に自分のDJ名（半角英数）を入れる。例：`"room": "nao"`（先生のconfigは設定済み）
- 他のDJも同じキットを使い、relay_url と合言葉（relay_token）は全員で共有し、`room` だけ各自の名前にする
- 表示側は、ページ上部のDJチップで切り替え可能。**AUTO** のままだと、再生中のDJを自動で追いかける
- 特定のDJに固定したい場合は、URLの末尾に `?room=<DJ名>` を付ける

## 7. 後日（二次会の準備として）

- OBSの30分テスト（最軽量設定 720p30・録画/配信なし）で、MacBook Airの負荷を確認する。音飛びや波形のカクつきが出たらミラーリング案に戻す

## 8. ハイブリッド補完（波形表示・任意）

Rekordbox の master.db と解析ファイル (ANLZ) から、波形・キュー位置・ジャケット・
アルバム名を補完する機能です。入れなくても従来どおり動作します。

1. 先行検証（初回のみ）：

```bash
pip3 install pyrekordbox
python3 db_probe.py
```

2. 最後に `PROBE_OK` と出たら、そのまま start.command で起動するだけです
   （dbmeta.py が自動で master.db を読みます。DB本体は読み取り専用の一時コピー経由）
3. `PROBE_NG` の場合は、出力全体をユウカに送ってください
4. 無効化したい場合は config.json に `"db_metadata": false` を追加します
