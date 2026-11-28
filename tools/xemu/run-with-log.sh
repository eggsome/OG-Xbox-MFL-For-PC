#!/bin/bash
# run-with-log.sh: xemu with the Mashed disc as configured, and xbox_log.py recording the cars' state into xbox-debug-A.txt / -B.txt
# in this folder (the last two to four minutes are kept).  Close xemu to stop.
cd "$(dirname "$0")"
sock=/tmp/xemu-qmp-$$.sock
rm -f "$sock"
python3 ./xbox_log.py "$sock" &
logger=$!
"${XEMU:-xemu}" -qmp "unix:$sock,server,nowait"
kill $logger 2>/dev/null
rm -f "$sock"
