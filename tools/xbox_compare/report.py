"""report.py: for the physics / control call tree, what differs between the PC function and its Xbox pair: constants, immediates"""
import funcs, pickle, collections, re, sys, struct
from pe import PE
from xbe import XBE
m = pickle.load(open("match.pkl", "rb")); pairs, sym = m["pairs"], m["sym"]
PC = funcs.load("pc.asm", 0x401000, 0x5dc000, sym.keys()); XB = funcs.load("xbe.asm", 0x11000, 0x1ea6ac)
pe, xb = PE(), XBE()
inv = {v: k for k, v in sym.items()}
roots = [inv[n] for n in ("cars_step", "cars_update_all", "car_update", "car_integrate_step", "car_apply_forces", "car_update_drivetrain", "car_wheel_contact_update", "car_ground_contact_forces", "car_world_collision_query", "car_car_collision", "car_init_dynamics", "car_air_control", "car_collision_impulse", "car_apply_throttle_force", "rwp_cars_update", "car_enter_rwp_mode", "ai_update_speed_scaling") if n in inv]
roots += [a for a, n in sym.items() if re.match(r"(car_|cars_|wheel|vehicle_handling|handling|drivetrain|steer|rwp_car|car_physics)", n) and a in PC]
seen, todo = set(), list(set(roots))
while todo:
    a = todo.pop()
    if a in seen or a not in PC or a >= 0x4b2000: continue
    seen.add(a)
    todo += [t for t in PC[a].calls if t not in seen]
def data(f, rd, code_lo, code_hi):
    fl, blobs = collections.Counter(), collections.Counter()
    for i, v in f.refs:
        if code_lo <= v < code_hi: continue
        b = rd(v, 16)
        if not b or len(b) < 16: continue
        w, = struct.unpack_from("<I", b); x, = struct.unpack_from("<f", b)
        if w and 1e-7 < abs(x) < 1e8: fl[round(x, 6) if abs(x) < 1e5 else x] += 1
        d, = struct.unpack_from("<d", b)
        if w == 0 and b[4:8] != bytes(4) and 1e-7 < abs(d) < 1e8: fl[("d", round(d, 9))] += 1
    return fl
def imms(f):
    c = collections.Counter()
    for ins in f.ins:
        mn = ins.split(" ", 1)[0]
        if mn in ("cmp", "test", "and", "or", "imul", "shl", "shr", "sar", "add", "sub", "mov", "push"):
            ops = ins.split(",")
            mm = re.fullmatch(r"\s*0x([0-9a-f]+)|\s*(\d)", ops[-1]) if len(ops) > 1 or mn == "push" else None
            if mm and mn in ("cmp", "test", "and", "or", "imul", "shl", "shr", "sar"):
                c[(mn, ops[-1].strip())] += 1
    return c
rows = []
for a in sorted(seen):
    n = sym.get(a, "sub_%x" % a)
    if a not in pairs: rows.append((n, a, None, None, None, None)); continue
    x, r = pairs[a]
    fp, fx = data(PC[a], pe.rd, 0x401000, 0x5dc000), data(XB[x], xb.rd, 0x11000, 0x27ee00)
    ip, ix = imms(PC[a]), imms(XB[x])
    rows.append((n, a, x, r, (sorted(map(str, (fp - fx).elements())), sorted(map(str, (fx - fp).elements()))), (sorted((ip - ix).elements()), sorted((ix - ip).elements()))))
print("functions in the physics / control tree:", len(rows), "unpaired:", sum(1 for r in rows if r[2] is None))
same = 0
for n, a, x, r, fd, idf in rows:
    if x is None: print("UNPAIRED %-40s %x (%d instructions)" % (n, a, len(PC[a].ins))); continue
    if not fd[0] and not fd[1] and not idf[0] and not idf[1]: same += 1; continue
    print("%-40s %x -> %x  seq %.2f  len %d/%d" % (n, a, x, r, len(PC[a].ins), len(XB[x].ins)))
    if fd[0] or fd[1]: print("     floats only pc:", fd[0][:12], " only xbox:", fd[1][:12])
    if idf[0] or idf[1]: print("     immediates only pc:", idf[0][:10], " only xbox:", idf[1][:10])
print("paired with identical constants and immediates:", same)
