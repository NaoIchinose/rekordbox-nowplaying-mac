-- probe v6: group 2 の直接の子に対する「一括指定子」読み取りの検証
-- デッキ要素はすべて group 2 of window の直接の子であることが判明したため、
--   value of every static text of group2
-- のような一括指定が高速に効くかを測る。
-- 結果はデスクトップの rekordbox-ui-dump-6.txt に書く。

set logLines to {}
set dumpPath to (POSIX path of (path to desktop)) & "rekordbox-ui-dump-6.txt"

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
				set g2 to group 2 of bestWin

				-- T1: static text の参照リスト取得
				set t0 to current date
				set refs to every static text of g2
				set end of logLines to "T1 refs-static: " & (count of refs) & " in " & ((current date) - t0) & "s"

				-- T2: value の一括指定
				set vals to missing value
				set t0 to current date
				try
					set vals to value of every static text of g2
					set end of logLines to "T2 bulk-value-static: OK count=" & (count of vals) & " in " & ((current date) - t0) & "s"
				on error errMsg number errNum
					set end of logLines to "T2 bulk-value-static: FAILED (" & errNum & ") in " & ((current date) - t0) & "s"
				end try

				-- T3: position の一括指定
				set poss to missing value
				set t0 to current date
				try
					set poss to position of every static text of g2
					set end of logLines to "T3 bulk-position-static: OK count=" & (count of poss) & " in " & ((current date) - t0) & "s"
				on error errMsg number errNum
					set end of logLines to "T3 bulk-position-static: FAILED (" & errNum & ") in " & ((current date) - t0) & "s"
				end try

				-- T4: text area の value 一括指定 (テンポ表示用)
				set tvals to missing value
				set tposs to missing value
				set t0 to current date
				try
					set tvals to value of every text area of g2
					set tposs to position of every text area of g2
					set end of logLines to "T4 bulk-textarea: OK count=" & (count of tvals) & " in " & ((current date) - t0) & "s"
				on error errMsg number errNum
					set end of logLines to "T4 bulk-textarea: FAILED (" & errNum & ") in " & ((current date) - t0) & "s"
				end try

				-- 一括が取れたら v3 形式で書き出す (パーサー検証用)
				if vals is not missing value and poss is not missing value then
					set end of logLines to ""
					set written to 0
					repeat with i from 1 to count of vals
						try
							set v to item i of vals
							if class of v is string and v is not "" and v is not "有効" and v is not "無効" then
								set p to item i of poss
								set end of logLines to "AXStaticText | value=" & v & " | pos=" & (item 1 of p) & "," & (item 2 of p)
								set written to written + 1
							end if
						end try
					end repeat
					if tvals is not missing value and tposs is not missing value then
						repeat with i from 1 to count of tvals
							try
								set v to item i of tvals
								if class of v is string and v is not "" then
									set p to item i of tposs
									set end of logLines to "AXTextArea | value=" & v & " | pos=" & (item 1 of p) & "," & (item 2 of p)
									set written to written + 1
								end if
							end try
						end repeat
					end if
					set end of logLines to "written: " & written
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
