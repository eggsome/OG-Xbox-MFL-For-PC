"""xdis.py <xbox|pc> <start> [count] [skip]: disassembly with the float constants written out"""
import sys, re, struct, pickle
from pe import PE
from xbe import XBE
which, start = sys.argv[1], int(sys.argv[2], 16); count = int(sys.argv[3]) if len(sys.argv) > 3 else 80; skip = int(sys.argv[4]) if len(sys.argv) > 4 else 0
rd = XBE().rd if which == "xbox" else PE().rd
ins = pickle.load(open(("xbe" if which == "xbox" else "pc") + ".asm.pkl", "rb"))
import bisect
i = bisect.bisect_left(ins, (start,)) + skip
for a, n, mn, ops in ins[i:i + count]:
    note = ""
    for h in re.findall(r"0x([0-9a-f]{5,8})", ops):
        v = int(h, 16); b = rd(v, 8)
        if b and len(b) == 8 and mn.startswith("f"):
            x, = struct.unpack_from("<f", b); d, = struct.unpack_from("<d", b)
            note = "   ; %.7g" % (d if "QWORD" in ops else x)
    print("%x: %s %s%s" % (a, mn, ops, note))
