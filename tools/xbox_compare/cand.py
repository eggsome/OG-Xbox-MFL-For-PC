"""cand.py <pc name>...: for a PC function without a pair, the Xbox functions that use the same constants (it may be inlined there)"""
import funcs, pickle, re, sys, struct, collections
from pe import PE
from xbe import XBE
m = pickle.load(open("match.pkl", "rb")); pairs, sym = m["pairs"], m["sym"]
PC = funcs.load("pc.asm", 0x401000, 0x5dc000, sym.keys()); XB = funcs.load("xbe.asm", 0x11000, 0x1ea6ac)
pe, xb = PE(), XBE(); inv = {v: k for k, v in sym.items()}; back = {x: p for p, (x, r) in pairs.items()}
def consts(f, rd, lo, hi):
    c = collections.Counter()
    for i, v in f.refs:
        if lo <= v < hi: continue
        b = rd(v, 8)
        if not b or len(b) < 8: continue
        x, = struct.unpack_from("<f", b)
        if 1e-7 < abs(x) < 1e8 and x not in (1.0, -1.0, 0.5, 2.0): c["%.6g" % x] += 1
    for ins in f.ins:
        mm = re.search(r",0x([0-9a-f]{8})$", ins)
        if mm:
            x, = struct.unpack("<f", struct.pack("<I", int(mm.group(1), 16)))
            if 1e-7 < abs(x) < 1e8 and x not in (1.0, -1.0, 0.5, 2.0) and abs(x - round(x, 4)) < 1e-6 * max(1, abs(x)): c["%.6g" % x] += 1
    return c
XC = {x: consts(f, xb.rd, 0x11000, 0x27ee00) for x, f in XB.items() if len(f.ins) >= 20}
for n in sys.argv[1:]:
    a = inv[n]; c = consts(PC[a], pe.rd, 0x401000, 0x5dc000)
    best = sorted(((sum((c & xc).values()) / max(1, sum(c.values())), x) for x, xc in XC.items()), reverse=True)[:3]
    print("%s (%d ins) constants: %s" % (n, len(PC[a].ins), dict(c)))
    for s, x in best:
        miss = c - XC[x]
        print("    xbox %x (%d ins, pair of %s): %.0f%% of the constants; not there: %s" % (x, len(XB[x].ins), sym.get(back.get(x)), s * 100, dict(miss)))
