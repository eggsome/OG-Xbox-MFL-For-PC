"""match.py: pair PC and Xbox functions by mnemonic histogram, referenced constants and instruction sequence; writes match.pkl"""
import os, funcs, pickle, collections, re, sys, struct, difflib, math
import numpy as np
from pe import PE
from xbe import XBE
sym = {}
for l in open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src", "symbols.txt")):
    p = l.split()
    if len(p) == 2 and not re.match(r"(LAB_|caseD_|switch|default)", p[0]):
        try: sym.setdefault(int(p[1], 16), p[0])
        except ValueError: pass
PC = funcs.load("pc.asm", 0x401000, 0x5dc000, sym.keys()); XB = funcs.load("xbe.asm", 0x11000, 0x1ea6ac)
pe, xb = PE(), XBE()
def consts(f, rd, lo, hi):
    out = set()
    for i, v in f.refs:
        if lo <= v < hi: continue                           # code
        b = rd(v, 4)
        if b is None or len(b) < 4: continue
        w, = struct.unpack("<I", b); fl, = struct.unpack("<f", b)
        if w != 0 and (1e-6 < abs(fl) < 1e7): out.add(w)
    return out
pcs = [f for f in PC.values() if len(f.ins) >= 8 and f.start < 0x4b2000]
xbs = [f for f in XB.values() if len(f.ins) >= 8]
mn = lambda f: [i.split(" ", 1)[0] for i in f.ins]
vocab = {}
def hist(fs):
    M = np.zeros((len(fs), 400), dtype=np.float32)
    for r, f in enumerate(fs):
        for m in mn(f):
            k = vocab.setdefault(m, len(vocab))
            if k < 400: M[r, k] += 1
    M /= np.maximum(1e-9, np.linalg.norm(M, axis=1, keepdims=True))
    return M
HP, HX = hist(pcs), hist(xbs)
CP = [consts(f, pe.rd, 0x401000, 0x5dc000) for f in pcs]; CX = [consts(f, xb.rd, 0x11000, 0x27ee00) for f in xbs]
cidx = collections.defaultdict(list)
for j, c in enumerate(CX):
    for w in c: cidx[w].append(j)
LX = np.array([len(f.ins) for f in xbs])
cand = []
for i, f in enumerate(pcs):
    cos = HX @ HP[i]
    size_ok = np.abs(LX - len(f.ins)) <= np.maximum(6, 0.25 * len(f.ins))
    score = np.where(size_ok, cos, -1)
    bonus = collections.Counter()
    for w in CP[i]:
        l = cidx.get(w, ())
        if len(l) < 200:
            for j in l: bonus[j] += 1
    for j, c in bonus.items():
        if size_ok[j]: score[j] += 0.5 * c / max(1, len(CP[i] | CX[j]))
    top = np.argsort(-score)[:6]
    a = mn(f)
    for j in top:
        if score[j] < 0.6: continue
        r = difflib.SequenceMatcher(None, a, mn(xbs[j]), autojunk=False).ratio()
        cj = len(CP[i] & CX[j]) / max(1, len(CP[i] | CX[j])) if (CP[i] or CX[j]) else 0.5
        cand.append((r + 0.15 * cj, r, i, j))
cand.sort(reverse=True)
pairs, usedp, usedx = {}, set(), set()
for s, r, i, j in cand:
    if i in usedp or j in usedx or r < 0.55: continue
    usedp.add(i); usedx.add(j); pairs[pcs[i].start] = (xbs[j].start, r)
pickle.dump(dict(pairs=pairs, sym=sym), open("match.pkl", "wb"))
rs = [r for x, r in pairs.values()]
print("pc game functions", len(pcs), "paired", len(pairs), ">=0.95:", sum(r >= 0.95 for r in rs), "0.8-0.95:", sum(0.8 <= r < 0.95 for r in rs), "<0.8:", sum(r < 0.8 for r in rs))
inv = {v: k for k, v in sym.items()}
for n in ("car_integrate_step", "car_update", "car_apply_forces", "car_update_drivetrain", "controller_poll_player", "car_wheel_contact_update", "car_ground_contact_forces", "car_points_vs_triangles", "cars_step", "joypad_get_axis_info", "controller_action_pressed"):
    a = inv.get(n); print(n, hex(a) if a else None, pairs.get(a) and (hex(pairs[a][0]), round(pairs[a][1], 3)))
