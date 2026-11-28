"""tables.py: every initialised data block the PC physics / control functions refer to: is the same block in the Xbox executable?"""
import funcs, pickle, re, struct, sys
from pe import PE
from xbe import XBE
m = pickle.load(open("match.pkl", "rb")); pairs, sym = m["pairs"], m["sym"]
PC = funcs.load("pc.asm", 0x401000, 0x5dc000, sym.keys())
pe, xb = PE(), XBE()
inv = {v: k for k, v in sym.items()}
roots = [a for a, n in sym.items() if re.match(r"(car_|cars_|wheel|vehicle_|rwp_|ai_|player_distance|controller_|joypad_)", n) and a in PC]
seen, todo = set(), list(roots)
while todo:
    a = todo.pop()
    if a in seen or a not in PC or a >= 0x4b2000: continue
    seen.add(a); todo += PC[a].calls
datasyms = sorted(a for a in sym if 0x5dd000 <= a < 0x94a000)
import bisect
xdata = xb.d
refs = {}
for a in seen:
    for i, v in PC[a].refs:
        if 0x5dd000 <= v < 0x94a000: refs.setdefault(v, set()).add(sym.get(a, hex(a)))
missing, found, zero = [], 0, 0
for v in sorted(refs):
    j = bisect.bisect_right(datasyms, v); nxt = datasyms[j] if j < len(datasyms) else v + 64
    n = max(4, min(256, nxt - v))
    b = pe.rd(v, n)
    if not b or b == bytes(len(b)): zero += 1; continue
    if n == 4:
        x, = struct.unpack("<f", b)
        if xdata.find(b) >= 0: found += 1
        else: missing.append((v, n, "float %.7g" % x if 1e-9 < abs(x) < 1e9 else b.hex(), refs[v]))
        continue
    # pointers differ between the builds: compare as floats / small ints only where the block has no pointer-like words
    words = struct.unpack("<%dI" % (n // 4), b[:n // 4 * 4])
    if any(0x400000 <= w < 0x950000 for w in words): continue
    if xdata.find(b) >= 0: found += 1
    else:
        k = 16
        part = sum(1 for o in range(0, n - k + 1, k) if xdata.find(b[o:o + k]) >= 0), max(1, (n - k) // k + 1)
        missing.append((v, n, "%d of %d 16-byte pieces found" % part, refs[v]))
print("data blocks referred to:", len(refs), "zero / uninitialised:", zero, "found in the Xbox image:", found, "not found:", len(missing))
for v, n, what, who in missing:
    print("%x %-28s %3d bytes  %s  <- %s" % (v, sym.get(v, "?"), n, what, ", ".join(sorted(who)[:3])))
