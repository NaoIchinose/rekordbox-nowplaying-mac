-- probe v4: 一括 (bulk) 読み取りの検証と時間計測
-- 目的: entire contents の要素を1つずつ読むと遅すぎるため、
--       「value of 要素リスト」のような一括取得が使えるか確認する。
-- 結果はデスクトップの rekordbox-ui-dump-4.txt に書く。

set logLines to {}
set dumpPath to (POSIX path of (path to desktop)) & "rekordbox-ui-dump-4.txt"

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

				-- Phase A: entire contents の取得時間
				set t0 to current date
				set elems to entire contents of bestWin
				set n to count of elems
				set end of logLines to "A entire-contents: " & n & " elems in " & ((current date) - t0) & "s"

				-- Phase B: value の一括取得
				set vals to missing value
				set t0 to current date
				try
					set vals to value of elems
					set end of logLines to "B bulk-value: OK, count=" & (count of vals) & " in " & ((current date) - t0) & "s"
				on error errMsg
					set end of logLines to "B bulk-value: FAILED (" & errMsg & ") in " & ((current date) - t0) & "s"
				end try

				-- Phase C: position の一括取得
				set poss to missing value
				set t0 to current date
				try
					set poss to position of elems
					set end of logLines to "C bulk-position: OK, count=" & (count of poss) & " in " & ((current date) - t0) & "s"
				on error errMsg
					set end of logLines to "C bulk-position: FAILED (" & errMsg & ") in " & ((current date) - t0) & "s"
				end try

				-- Phase D: role の一括取得
				set roles to missing value
				set t0 to current date
				try
					set roles to role of elems
					set end of logLines to "D bulk-role: OK, count=" & (count of roles) & " in " & ((current date) - t0) & "s"
				on error errMsg
					set end of logLines to "D bulk-role: FAILED (" & errMsg & ") in " & ((current date) - t0) & "s"
				end try

				if vals is not missing value and poss is not missing value then
					-- 一括取得できた場合は v3 と同じ形式で要素一覧も書く
					set end of logLines to ""
					set written to 0
					repeat with i from 1 to n
						try
							set v to item i of vals
							if class of v is string and v is not "" and v is not "有効" and v is not "無効" then
								set r to "?"
								if roles is not missing value then set r to item i of roles
								set p to item i of poss
								set end of logLines to r & " | value=" & v & " | pos=" & (item 1 of p) & "," & (item 2 of p)
								set written to written + 1
							end if
						end try
					end repeat
					set end of logLines to "written: " & written
				else
					-- Phase E: 一括が使えない場合、先頭60要素の個別読み時間だけ測る
					set t0 to current date
					set lim to n
					if lim > 60 then set lim to 60
					repeat with i from 1 to lim
						try
							set v to value of (item i of elems)
						end try
					end repeat
					set end of logLines to "E loop-60-values: " & ((current date) - t0) & "s"
				end if
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
