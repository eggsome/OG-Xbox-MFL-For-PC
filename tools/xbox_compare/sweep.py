"""sweep.py: for every paired function of the physics / control tree, the ordered float constants and compare immediates of both sides,
diffed; prints only the functions where they differ"""
import funcs, pickle, re, sys, struct, difflib
from pe import PE
from xbe import XBE
m = pickle.load(open("match.pkl", "rb")); pairs, sym = m["pairs"], m["sym"]
PC = funcs.load("pc.asm", 0x401000, 0x5dc000, sym.keys()); XB = funcs.load("xbe.asm", 0x11000, 0x1ea6ac)
pe, xb = PE(), XBE()
pat = sys.argv[1] if len(sys.argv) > 1 else r"(car_|cars_|wheel|vehicle_|rwp_|player_distance|ai_|race_battle|camera_|weapon_|powerup_)"
roots = [a for a, n in sym.items() if re.match(pat, n) and a in PC]
seen, todo = set(), list(roots)
while todo:
    a = todo.pop()
    if a in seen or a not in PC or a >= 0x4b2000: continue
    seen.add(a); todo += PC[a].calls
def consts(f, rd, lo, hi):
    refs = {}
    for i, v in f.refs: refs.setdefault(i, []).append(v)
    out = []
    for i, ins in enumerate(f.ins):
        mn = ins.split(" ", 1)[0]
        for v in refs.get(i, ()):
            if lo <= v < hi or not mn.startswith("f"): continue
            b = rd(v, 8)
            if not b or len(b) < 8: continue
            x, = struct.unpack_from("<f", b); d, = struct.unpack_from("<d", b)
            val = d if "QWORD" in ins else x
            if val in (0.0, 1.0, -1.0) or not (1e-7 < abs(val) < 1e8): continue      # 0 and +-1 come and go with the compiler (clamps, compares)
            out.append("%.6g" % val)
        mm = re.search(r"DWORD PTR \[[^\]]*\],0x([0-9a-f]{8})$", ins)
        if mn == "mov" and mm:                               # a float stored as an immediate
            x, = struct.unpack("<f", struct.pack("<I", int(mm.group(1), 16)))
            if 1e-7 < abs(x) < 1e8 and x not in (1.0, -1.0) and abs(x - round(x, 4)) < 1e-6 * max(1, abs(x)): out.append("%.6g" % x)
    return out
n = 0
for a in sorted(seen):
    if a not in pairs: continue
    x, r = pairs[a]
    A, B = consts(PC[a], pe.rd, 0x401000, 0x5dc000), consts(XB[x], xb.rd, 0x11000, 0x27ee00)
    if sorted(A) == sorted(B): continue
    import collections
    ca, cb = collections.Counter(A), collections.Counter(B)
    only_pc, only_xb = sorted((ca - cb).elements(), key=float), sorted((cb - ca).elements(), key=float)
    n += 1
    print("%-36s %x -> %x seq %.2f  pc only: %s   xbox only: %s" % (sym.get(a), a, x, r, " ".join(only_pc[:10]), " ".join(only_xb[:10])))
print(n, "of", sum(1 for a in seen if a in pairs), "paired functions differ in their float constants;", sum(1 for a in seen if a not in pairs and len(PC[a].ins) >= 8), "functions of 8+ instructions unpaired")
