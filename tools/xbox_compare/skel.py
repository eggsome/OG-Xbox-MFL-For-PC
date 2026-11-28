"""skel.py <pc function name>...: the PC function and its Xbox pair as skeletons (calls, float constants with their instruction,
compare immediates), diffed"""
import funcs, pickle, re, sys, struct, difflib
from pe import PE
from xbe import XBE
m = pickle.load(open("match.pkl", "rb")); pairs, sym = m["pairs"], m["sym"]
PC = funcs.load("pc.asm", 0x401000, 0x5dc000, sym.keys()); XB = funcs.load("xbe.asm", 0x11000, 0x1ea6ac)
pe, xb = PE(), XBE()
inv = {v: k for k, v in sym.items()}; back = {x: p for p, (x, r) in pairs.items()}
def skel(f, rd, lo, hi, name):
    refs = {}
    for i, v in f.refs: refs.setdefault(i, []).append(v)
    out = []
    for i, ins in enumerate(f.ins):
        mn = ins.split(" ", 1)[0]
        if mn in ("call", "jmp") and ins.endswith(" A"):
            out.append("call " + name(refs[i][0])); continue
        vals = []
        for v in refs.get(i, ()):
            if lo <= v < hi: continue
            b = rd(v, 8)
            if not b or len(b) < 8: continue
            w, = struct.unpack_from("<I", b); x, = struct.unpack_from("<f", b); d, = struct.unpack_from("<d", b)
            if "QWORD" in ins and (d == 0 or 1e-9 < abs(d) < 1e9): vals.append("%.6g" % d)
            elif w == 0: vals.append("0") if mn.startswith("f") else None
            elif 1e-7 < abs(x) < 1e8: vals.append("%.6g" % x)
        if vals and (mn.startswith("f") or mn in ("mov", "push", "cmp")):
            out.append("%s %s" % (re.sub(r"p$", "", mn) if mn.startswith("fcom") else mn, ",".join(vals)))
        elif mn in ("cmp", "test") and re.search(r",\s*(0x[0-9a-f]+|\d)$", ins) and "esp" not in ins:
            out.append("%s #%s" % (mn, ins.rsplit(",", 1)[1].strip()))
    return out
for n in sys.argv[1:]:
    a = inv[n]; x, r = pairs[a]
    A = skel(PC[a], pe.rd, 0x401000, 0x5dc000, lambda t: sym.get(t, "sub"))
    B = skel(XB[x], xb.rd, 0x11000, 0x27ee00, lambda t: sym.get(back.get(t), "sub") if t in back else "sub")
    print("=== %s %x -> %x (seq %.2f) skeleton %d / %d" % (n, a, x, r, len(A), len(B)))
    for l in difflib.unified_diff(A, B, "pc", "xbox", n=1, lineterm=""):
        if not l.startswith(("---", "+++")): print("   ", l)
