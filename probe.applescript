-- Rekordbox 7 UIプローブ v3 高速版（Mac版 NOW PLAYING ツール用）
-- v3変更点: 読む項目を role/value/position の3つに削減し、結果はメモリに貯めて最後に一括でUTF-8書き出し。
-- ★実行前に、両デッキの再生を止めてください（再生中は画面応答が遅く、読み取りが極端に遅くなります）。
-- 結果は デスクトップの rekordbox-ui-dump.txt に保存される。

set outFile to (POSIX path of (path to desktop)) & "rekordbox-ui-dump.txt"
set out to ""

tell application "System Events"
	if not (exists process "rekordbox") then
		set out to "ERROR: rekordboxプロセスが見つかりません。"
	else
		tell process "rekordbox"
			if (count of windows) is 0 then
				set out to "ERROR: ウィンドウがありません。"
			else
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
				set out to "main-window pos=" & (item 1 of winPos) & "," & (item 2 of winPos) & " size=" & (item 1 of winSize) & "x" & (item 2 of winSize) & linefeed & linefeed
				set elems to entire contents of bestWin
				set out to out & "elements: " & (count of elems) & linefeed & linefeed
				set written to 0
				repeat with el in elems
					try
						set v to ""
						try
							set v to value of el
							if v is missing value then
								set v to ""
							else if class of v is not in {string, integer, real, boolean} then
								set v to ""
							else
								set v to v as string
							end if
						end try
						if v is not "" then
							set r to "?"
							set px to -1
							set py to -1
							try
								set r to role of el
							end try
							try
								set p to position of el
								set px to item 1 of p
								set py to item 2 of p
							end try
							set out to out & r & " | value=" & v & " | pos=" & px & "," & py & linefeed
							set written to written + 1
						end if
					end try
				end repeat
				set out to out & linefeed & "written: " & written & linefeed & "DONE" & linefeed
			end if
		end tell
	end if
end tell

set fp to open for access (POSIX file outFile) with write permission
set eof of fp to 0
write out to fp as «class utf8»
close access fp
display dialog "プローブ完了（v3）。デスクトップの rekordbox-ui-dump.txt をユウカに送ってください。" buttons {"OK"} default button "OK"
