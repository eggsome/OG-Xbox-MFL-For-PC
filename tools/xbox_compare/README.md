# Comparing the PC and Xbox executables

Scripts that pair the functions of `MFL.exe` with those of the Xbox version's `default.xbe` and list where their constants and tables differ. Results are in `docs/XBOX_DIFFERENCES.md`. Needs Python 3 with numpy, and objdump.

Set up (in this folder; the listings are large and are not part of the repository):

```sh
export MFL_EXE=<path>/MFL.exe MFL_XBE=<path>/default.xbe
objdump -d -M intel --section=.text "$MFL_EXE" > pc.asm
python3 xbe.py .text text.bin
objdump -D -b binary -mi386 -Mintel --adjust-vma=0x11000 text.bin > xbe.asm
python3 match.py          # pairs the functions, writes match.pkl
```

Then:

| Script | Shows |
|---|---|
| `sweep.py [name pattern]` | every paired function whose float constants or compare immediates differ |
| `report.py` | the same for the physics / control call tree, function by function |
| `tables.py` | whether each data block the PC physics refers to is also in the Xbox executable |
| `skel.py <pc function>...` | a PC function and its pair as skeletons (calls, constants, immediates), diffed |
| `cand.py <pc function>...` | for a function without a pair, the Xbox functions that use the same constants |
| `xdis.py <xbox\|pc> <address> [count]` | disassembly with float constants written out |

`funcs.py`, `pe.py` and `xbe.py` are the shared readers. The pairing is a heuristic: check a pair with `skel.py` before trusting a difference.
