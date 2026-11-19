-- Rekordbox 7 UIプローブ（Mac版 NOW PLAYING ツール用）
-- 目的: Rekordboxの画面要素（役割・名前・値・位置）を全部書き出し、
--       曲名・アーティストがどの要素に入っているかを特定するための診断スクリプト。
-- 使い方: Rekordbox 7 で両デッキに曲をロードした状態で、このスクリプトを実行する。
-- 結果は デスクトップの rekordbox-ui-dump.txt に保存される。

set outFile to (POSIX path of (path to desktop)) & "rekordbox-ui-dump.txt"
set fp to open for access (POSIX file outFile) with write permission
set eof of fp to 0

tell application "System Events"
	if not (exists process "rekordbox") then
		write "ERROR: rekordboxプロセスが見つかりません。Rekordboxを起動してから実行してください。" to fp
		close access fp
		return
	end if
	tell process "rekordbox"
		set winCount to count of windows
		write ("windows: " & winCount & linefeed) to fp
		if winCount is 0 then
			write "ERROR: ウィンドウがありません。" to fp
			close access fp
			return
		end if
		-- ツールチップ等の小窓ではなく、一番面積の大きいウィンドウを本画面とする
		set bestWin to missing value
		set bestArea to -1
		repeat with w in windows
			try
				set s to size of w
				set a to (item 1 of s) * (item 2 of s)
				if a > bestArea then
					set bestArea to a
					set bestWin to w
				end if
			end try
		end repeat
		set winPos to position of bestWin
		set winSize to size of bestWin
		write ("main-window pos=" & (item 1 of winPos) & "," & (item 2 of winPos) & " size=" & (item 1 of winSize) & "x" & (item 2 of winSize) & linefeed & linefeed) to fp
		set elems to entire contents of bestWin
		write ("elements: " & (count of elems) & linefeed & linefeed) to fp
		repeat with el in elems
			try
				set r to role of el
			on error
				set r to "?"
			end try
			try
				set n to name of el
			on error
				set n to ""
			end try
			try
				set v to value of el
			on error
				set v to ""
			end try
			try
				set d to description of el
			on error
				set d to ""
			end try
			try
				set p to position of el
				set px to item 1 of p
				set py to item 2 of p
			on error
				set px to -1
				set py to -1
			end try
			if n is missing value then set n to ""
			if v is missing value then set v to ""
			if d is missing value then set d to ""
			-- 値か名前がある要素だけ記録（空要素はノイズなので省く）
			if (n is not "") or (v is not "") then
				write (r & " | name=" & n & " | value=" & v & " | desc=" & d & " | pos=" & px & "," & py & linefeed) to fp
			end if
		end repeat
	end tell
end tell

close access fp
display dialog "プローブ完了。デスクトップの rekordbox-ui-dump.txt をユウカに送ってください。" buttons {"OK"} default button "OK"
