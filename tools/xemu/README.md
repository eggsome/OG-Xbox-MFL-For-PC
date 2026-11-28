# Recording the Xbox version in xemu

Two recorders that write the same lines as the PC game's `--debug` log, so the two can be compared. Set `XEMU` to the xemu binary (default `xemu`), with the game's disc configured in it. Output is written beside the scripts.

- `run-with-log.sh`: polls guest memory through QMP (`xbox_log.py`) and writes each car's position, axes, velocity and wheel contacts to `xbox-debug-A.txt` / `xbox-debug-B.txt`. Runs at full speed.
- `run-with-gdb.sh`: attaches gdb to xemu's debug port (`xbox_align.py`) and records every ground alignment decision of `car_wheel_contact_update` to `xbox-align.txt`. The game runs slowly for the first 12000 decisions.

The addresses in both scripts are those of the `default.xbe` used for this work.
