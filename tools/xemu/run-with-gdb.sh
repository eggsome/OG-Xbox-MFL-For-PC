#!/bin/bash
# run-with-gdb.sh: xemu with the Mashed disc as configured and gdb attached to its debug port, recording how the game aligns its cars to
# the ground (xbox_align.py -> xbox-align.txt in this folder).  The game runs slowly while it records (the first 12000 decisions, about 20
# seconds of a race start), then at full speed.  Close xemu to stop.
cd "$(dirname "$0")"
"${XEMU:-xemu}" -gdb tcp::1234 &
emu=$!
sleep 4
gdb -q -batch -x ./xbox_align.py > xbox-align.gdb.log 2>&1 &
wait $emu
