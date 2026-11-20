-- probe v5: 競合のない状態での読み取り速度の再計測
-- 前提: エージェント (nowplaying.py) は完全に停止していること。
-- A: 先頭60要素の value 読み取り時間
-- B: エージェントと同じ方式のフル取得の総時間 + 要素一覧 (v3形式)
-- 結果はデスクトップの rekordbox-ui-dump-5.txt に書く。

set logLines to {}
set dumpPath to (POSIX path of (path to desktop)) & "rekordbox-ui-dump-5.txt"

tell application "System Events"
	if not (exists process "rekordbox") then
		set end of logLines to "NOREKORDBOX"
	else
		tell process "rekordbox"
			if (count of windows) is 0 then
				set end of logLines to "NOWIN"
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
				set end of logLines to "main-window pos=" & (item 1 of winPos) & "," & (item 2 of winPos) & " size=" & (item 1 of winSize) & "x" & (item 2 of winSize)

				set t0 to current date
				set elems to entire contents of bestWin
				set n to count of elems
				set end of logLines to "entire-contents: " & n & " elems in " & ((current date) - t0) & "s"

				-- A: 先頭60要素の value だけ読む
				set t0 to current date
				set lim to n
				if lim > 60 then set lim to 60
				repeat with i from 1 to lim
					try
						set v to value of (item i of elems)
					end try
				end repeat
				set end of logLines to "A loop-60-values: " & ((current date) - t0) & "s"

				-- B: フル取得 (エージェント方式: value→文字列だけ role/position)
				set t0 to current date
				set written to 0
				repeat with el in elems
					try
						set v to value of el
						if v is missing value then
							set v to ""
						else if class of v is not string then
							set v to ""
						end if
						if v is not "" and v is not "有効" and v is not "無効" then
							set r to role of el
							if r is "AXStaticText" or r is "AXTextField" or r is "AXTextArea" then
								try
									set p to position of el
									set px to item 1 of p
									set py to item 2 of p
								on error
									set px to -1
									set py to -1
								end try
								set end of logLines to r & " | value=" & v & " | pos=" & px & "," & py
								set written to written + 1
							end if
						end if
					end try
				end repeat
				set end of logLines to "B full-fetch: " & written & " written in " & ((current date) - t0) & "s"
				set end of logLines to "DONE"
			end if
		end tell
	end if
end tell

set outText to ""
repeat with ln in logLines
	set outText to outText & ln & linefeed
end repeat
try
	set fh to open for access (POSIX file dumpPath) with write permission
	set eof of fh to 0
	write outText to fh as «class utf8»
	close access fh
on error
	try
		close access (POSIX file dumpPath)
	end try
end try
