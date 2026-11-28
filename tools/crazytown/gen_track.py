"""gen_track.py: the circuit "Crazy Town" -- the three world files and the lap script of a Mashed track, generated.

The lap: a start plateau TOP metres up, a steep straight hill down, a run-up to a jump (a ramp that curves upwards and ends in the
air), a long landing straight, then a circuit through the town that climbs back to the plateau.  The map is 2 * EDGE metres
square, about the range the game's bot grid covers (256 m).

  graphics   road and pavements, the ground (a height field over the whole map: level with the road beside it, sloping down to the
             town), the ramp, houses, a boundary wall (textured, prelit)
  collision  the ground height field, the ramp, houses and wall, with the surface type as the material colour, a "fell off" plane
             below, kd-trees for collision
  lap        one vertical gate across the road every GATE metres, gate i with the material colour (i, 0, 0), facing forwards
"""
import math, struct
import rw, world, build

EDGE, CELL, GROUND_Y, WALL = 126.0, 2.0, -1.0, 2.0         # half size of the map; ground grid size; level of the town; boundary wall height
STEP, GATE = 2.0, 2                                        # centre line sample distance; a gate every GATE samples
HALF, VERGE, SHOULDER, BANK, SLOPE, UNDER = 3.0, 1.2, 1.5, 5.0, 1.0, 0.08
TOP = 32.0                                                 # height of the start plateau
RAMP_X, RAMP_L, RAMP_H, RAMP_N = 10.0, 16.0, 3.5, 16      # the jump on the straight (z = ROAD_Z, heading +x): where it begins, its length and height
ROAD_Z = -85.0
CUT_H, SUNK = 0.6, 0.7                                     # under the ramp where it is lower than CUT_H the ground lies SUNK deeper: a wheel takes the
                                                           # first drivable surface within 0.25 m of it, and must find the ramp
# the centre line, closed (the last point joins the first): (x, z, height)
PATH = [(42, ROAD_Z, 0), (62, ROAD_Z, 0), (82, ROAD_Z, 0), (104, -58, 0), (110, -30, 0), (88, -5, 0), (72, 22, 0), (92, 48, 0),
        (106, 70, 0), (88, 92, 0), (55, 96, 0), (15, 90, 4), (-25, 96, 9), (-60, 90, 14), (-86, 72, 18), (-93, 40, 21), (-91, 0, TOP),
        (-93, -40, TOP), (-90, -68, TOP), (-76, ROAD_Z, TOP), (-52, ROAD_Z, TOP), (-4, ROAD_Z, 0), (18, ROAD_Z, 0), (40, ROAD_Z, 0)]
START = (-64.0, ROAD_Z)                                    # the start line, on the plateau
SURF_ROAD, SURF_GRASS, SURF_WALL, SURF_OUT = (0, 64, 128, 255), (0, 128, 0, 255), (1, 1, 1, 255), (255, 0, 0, 255)
TEX_FILTER = 0x11102
TEXTURES = ("Road", "RoadSide", "Grass", "StoneWall", "Window", "Roof")      # graphics materials 0..5
FLOOR = 2.5                                                # height of one storey (one repeat of the wall texture)

def centreline():
    """the path at STEP metre spacing: [(x, z, height)], heights smoothed along the length"""
    pts = [(PATH[0][0] - 20, PATH[0][1], 0)] + PATH + [(PATH[-1][0] + 20, PATH[-1][1], 0)]      # straight on at both ends
    dense = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for j in range(60):
            t = j / 60.0
            xz = tuple(0.5 * (2 * p1[a] + (p2[a] - p0[a]) * t + (2 * p0[a] - 5 * p1[a] + 4 * p2[a] - p3[a]) * t * t +
                              (3 * p1[a] - p0[a] - 3 * p2[a] + p3[a]) * t ** 3) for a in range(2))
            dense.append(xz + (p1[2] + (p2[2] - p1[2]) * t,))
    dense.append(tuple(float(a) for a in PATH[-1]))
    seg = [math.dist(dense[i][:2], dense[i + 1][:2]) for i in range(len(dense) - 1)]
    total = sum(seg); count = int(round(total / STEP)); step = total / count
    out, i, acc = [], 0, 0.0
    for k in range(count + 1):
        target = min(k * step, total - 1e-9)
        while acc + seg[i] < target: acc += seg[i]; i += 1
        f = (target - acc) / seg[i]; a, b = dense[i], dense[i + 1]
        out.append(tuple(a[c] + (b[c] - a[c]) * f for c in range(3)))
    r = 3                                                  # +- 6 m: rounds the crest and the foot of the hill
    hs = [sum(out[min(len(out) - 1, max(0, k + d))][2] for d in range(-r, r + 1)) / (2 * r + 1) for k in range(len(out))]
    return [(p[0], p[1], h) for p, h in zip(out, hs)], step

def ramp_point(k):
    """the ramp's centre at piece boundary k (0 .. RAMP_N): it curves upwards (a parabola), level where it begins"""
    t = k / RAMP_N
    return (RAMP_X + RAMP_L * t, RAMP_H * t * t, ROAD_Z)

def clip(poly, a, b, inside):
    """the part of the polygon [(x, y, z)] to the left (inside) or right of the line a -> b on the map"""
    side = lambda p: ((b[0] - a[0]) * (p[2] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])) * (-1 if inside else 1)      # > 0: dropped
    out = []
    for i, p in enumerate(poly):
        q = poly[(i + 1) % len(poly)]; sp, sq = side(p), side(q)
        if sp <= 0: out.append(p)
        if (sp < 0 < sq) or (sq < 0 < sp):
            t = sp / (sp - sq); out.append(tuple(p[k] + (q[k] - p[k]) * t for k in range(3)))
    return out

def area(poly):
    return abs(sum(poly[i][0] * poly[(i + 1) % len(poly)][2] - poly[(i + 1) % len(poly)][0] * poly[i][2] for i in range(len(poly)))) / 2

def split(polys, quad):
    """the polygons cut along the convex quad [(x, z)] (wound to the left): (what lies outside it, what lies inside)"""
    lo = [min(p[k] for p in quad) for k in range(2)]; hi = [max(p[k] for p in quad) for k in range(2)]
    out, inner = [], []
    for poly in polys:
        if max(p[0] for p in poly) <= lo[0] or min(p[0] for p in poly) >= hi[0] or max(p[2] for p in poly) <= lo[1] or min(p[2] for p in poly) >= hi[1]:
            out.append(poly); continue
        rest = poly
        for i in range(4):
            a, b = quad[i], quad[(i + 1) % 4]
            cut = clip(rest, a, b, False)
            if len(cut) >= 3 and area(cut) > 1e-7: out.append(cut)
            rest = clip(rest, a, b, True)
            if len(rest) < 3: break
        if len(rest) >= 3 and area(rest) > 1e-7: inner.append(rest)
    return out, inner

class Mesh:
    def __init__(self): self.v, self.uv, self.t = [], [], []
    def quad(self, a, b, c, d, mat, uvs=None, facing=None):
        """corners in order around the quad; with `facing` wound so that the face looks that way"""
        if facing is not None:
            e1 = [b[i] - a[i] for i in range(3)]; e2 = [c[i] - a[i] for i in range(3)]
            n = (e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0])
            if sum(n[i] * facing[i] for i in range(3)) < 0:
                a, b, c, d = d, c, b, a
                if uvs: uvs = uvs[::-1]
        base = len(self.v); self.v += [a, b, c, d]; self.uv += uvs or [(0, 0)] * 4
        self.t += [(base, base + 1, base + 2, mat), (base, base + 2, base + 3, mat)]
    def both(self, a, b, c, d, mat, uvs=None):
        """seen and hit from either side"""
        self.quad(a, b, c, d, mat, uvs); self.quad(d, c, b, a, mat, uvs[::-1] if uvs else None)
    def face_up(self):
        out = []
        for a, b, c, m in self.t:
            A, B, C = self.v[a], self.v[b], self.v[c]
            ny = (B[2] - A[2]) * (C[0] - A[0]) - (B[0] - A[0]) * (C[2] - A[2])
            out.append((a, b, c, m) if ny >= 0 else (a, c, b, m))
        self.t = out

def nearest(line, x, z):
    """distance from (x, z) to the centre line [(x, z, height)] (closed) and the road height at the nearest point of it"""
    best = (1e18, 0.0); n = len(line)
    for i in range(n):
        ax, az, ah = line[i]; bx, bz, bh = line[(i + 1) % n]
        ux, uz = bx - ax, bz - az; t = ((x - ax) * ux + (z - az) * uz) / (ux * ux + uz * uz); t = min(1.0, max(0.0, t))
        d = (x - ax - ux * t) ** 2 + (z - az - uz * t) ** 2
        if d < best[0]: best = (d, ah + (bh - ah) * t)
    return math.sqrt(best[0]), best[1]

def terrain(d, h):
    """height of the ground at distance d from the centre line (road height h there): level with the road to SHOULDER beyond the
    pavement, then a smooth slope down to the town's level, the wider the higher the road is (1 in SLOPE, at least BANK wide)"""
    t = min(1.0, max(0.0, (d - HALF - VERGE - SHOULDER) / max(BANK, SLOPE * (h - GROUND_Y))))
    return h + (GROUND_Y - h) * t * t * (3 - 2 * t)

def houses(height):
    """(centre x, centre z, half width, half depth, height) of the houses: a jittered grid over the map, only on the town's level"""
    out, seed = [], 12345
    def rnd():
        nonlocal seed
        seed = (seed * 1103515245 + 12345) & 0x7fffffff
        return seed / 0x7fffffff
    pitch = 12.0; k = int((EDGE - 8) // pitch)
    for i in range(-k, k + 1):
        for j in range(-k, k + 1):
            cx, cz = i * pitch + (rnd() - 0.5) * 4, j * pitch + (rnd() - 0.5) * 4
            hx, hz, top = 2.0 + rnd() * 2.5, 2.0 + rnd() * 2.5, FLOOR * (1 + int(rnd() * 4.99))
            if all(height(cx + a * (hx + 3), cz + b * (hz + 3)) < GROUND_Y + 0.02 for a in (-1, 0, 1) for b in (-1, 0, 1)):
                out.append((cx, cz, hx, hz, top))
    return out

def make():
    path, step = centreline()
    W = HALF + VERGE
    # --- the ring: the path's samples in lap order from the start line ------------------------------------------------------------
    k0 = min(range(len(path)), key=lambda i: math.dist(path[i][:2], START))
    order = list(range(k0, len(path))) + list(range(0, k0))
    ring = []                                              # centre x, z, left normal (x, z), height, tangent (x, z), ring distance
    for r, i in enumerate(order):
        a, b = path[max(0, i - 1)], path[min(len(path) - 1, i + 1)]
        tx, tz = b[0] - a[0], b[1] - a[1]; l = math.hypot(tx, tz); tx, tz = tx / l, tz / l
        ring.append((path[i][0], path[i][1], -tz, tx, path[i][2], r * step, tx, tz))
    n = len(ring)
    def at(r, off):
        x, z, nx, nz, h = ring[r % n][:5]
        return (x + nx * off, h, z + nz * off)
    g, c = Mesh(), Mesh()                                  # graphics: materials 0 road 1 pavement 2 grass 3 wall 4 house 5 roof; collision: 0 road 1 grass 2 wall 3 out
    for r in range(n):                                     # the road and its pavements: drawn only, the cars drive on the ground below
        s0, s1 = ring[r][5] / 6.0, (ring[r][5] + step) / 6.0
        g.quad(at(r, -HALF), at(r, HALF), at(r + 1, HALF), at(r + 1, -HALF), 0, [(0, s0), (1, s0), (1, s1), (0, s1)])
        for sgn in (-1, 1):
            a, b = sgn * HALF, sgn * W
            g.quad(at(r, a), at(r, b), at(r + 1, b), at(r + 1, a), 1, [(0, s0), (0.5, s0), (0.5, s1), (0, s1)])
    g.face_up()
    # --- the ground: one height field over the whole map (shared vertices), so it has no gaps or folds -----------------------------
    line = [(p[0], p[1], p[4]) for p in ring]
    cells = int(round(2 * EDGE / CELL))
    grid = [[nearest(line, -EDGE + i * CELL, -EDGE + j * CELL) for j in range(cells + 1)] for i in range(cells + 1)]
    ground = lambda i, j: terrain(*grid[i][j])
    def height(x, z):                                      # of the ground, between the grid points
        fi, fj = min(cells - 1e-6, max(0.0, (x + EDGE) / CELL)), min(cells - 1e-6, max(0.0, (z + EDGE) / CELL))
        i, j = int(fi), int(fj); u, v = fi - i, fj - j
        return (ground(i, j) * (1 - u) + ground(i + 1, j) * u) * (1 - v) + (ground(i, j + 1) * (1 - u) + ground(i + 1, j + 1) * u) * v
    ramp = [ramp_point(k) for k in range(RAMP_N + 1)]
    side = lambda p, off: (p[0], p[1], p[2] + off)
    low = [k for k in range(RAMP_N) if ramp[k][1] < CUT_H]      # the ramp's pieces near the ground
    holes = []
    for k in low:                                          # under them the ground is sunk
        q = [(ramp[k][0], ROAD_Z - W), (ramp[k + 1][0], ROAD_Z - W), (ramp[k + 1][0], ROAD_Z + W), (ramp[k][0], ROAD_Z + W)]
        if sum(q[i][0] * q[(i + 1) % 4][1] - q[(i + 1) % 4][0] * q[i][1] for i in range(4)) < 0: q = q[::-1]
        holes.append(q)
    hx0, hx1 = min(p[0] for q in holes for p in q) - CELL, max(p[0] for q in holes for p in q) + CELL
    hz0, hz1 = min(p[1] for q in holes for p in q) - CELL, max(p[1] for q in holes for p in q) + CELL
    for mesh, drawn in ((g, True), (c, False)):
        base = len(mesh.v)
        for i in range(cells + 1):
            for j in range(cells + 1):
                d, h = grid[i][j]; y = terrain(d, h)
                if drawn: y -= UNDER * (1 - min(1.0, max(0.0, (d - W) / SHOULDER)))      # the drawn ground lies just under the drawn road
                x, z = -EDGE + i * CELL, -EDGE + j * CELL
                mesh.v.append((x, y, z)); mesh.uv.append((x / 4.0, z / 4.0))
        idx = lambda i, j: base + i * (cells + 1) + j
        for i in range(cells):
            for j in range(cells):
                on_road = not drawn and (grid[i][j][0] + grid[i + 1][j][0] + grid[i + 1][j + 1][0] + grid[i][j + 1][0]) / 4.0 <= W + 0.7
                mat = 2 if drawn else (0 if on_road else 1)
                tris = [(idx(i, j), idx(i, j + 1), idx(i + 1, j + 1)), (idx(i, j), idx(i + 1, j + 1), idx(i + 1, j))]
                x, z = -EDGE + i * CELL, -EDGE + j * CELL
                if x + CELL < hx0 or x > hx1 or z + CELL < hz0 or z > hz1:
                    mesh.t += [t + (mat,) for t in tris]; continue
                for t in tris:                             # near the ramp: the triangle cut along the ramp's low pieces, in new vertices
                    polys, sunk = [[mesh.v[k] for k in t]], []
                    for q in holes:
                        polys, inner = split(polys, q); sunk += inner
                    polys += [[(p[0], p[1] - SUNK, p[2]) for p in poly] for poly in sunk]
                    for poly in polys:
                        b0 = len(mesh.v); mesh.v += poly; mesh.uv += [(p[0] / 4.0, p[2] / 4.0) for p in poly]
                        for k in range(1, len(poly) - 1):
                            A, B, C = poly[0], poly[k], poly[k + 1]
                            up = (B[2] - A[2]) * (C[0] - A[0]) - (B[0] - A[0]) * (C[2] - A[2]) >= 0
                            mesh.t.append((b0, b0 + k, b0 + k + 1, mat) if up else (b0, b0 + k + 1, b0 + k, mat))
    # --- the ramp: road on top, walls at its sides and under its end; the same faces drawn and solid --------------------------------
    for k in range(RAMP_N):
        p0, p1 = ramp[k], ramp[k + 1]
        v0, v1 = (p0[0] - RAMP_X) / 6.0, (p1[0] - RAMP_X) / 6.0
        up = (-(p1[1] - p0[1]), p1[0] - p0[0], 0.0)
        for mesh, solid in ((g, False), (c, True)):
            mesh.quad(side(p0, -HALF), side(p0, HALF), side(p1, HALF), side(p1, -HALF), 0, [(0, v0), (1, v0), (1, v1), (0, v1)], facing=up)
            for sgn in (-1, 1):
                a, b = sgn * HALF, sgn * W
                mesh.quad(side(p0, a), side(p0, b), side(p1, b), side(p1, a), 0 if solid else 1, [(0, v0), (0.5, v0), (0.5, v1), (0, v1)], facing=up)
                if k not in low:                           # the side wall below this piece; a solid one ends just below the road
                    gap = 0.05 if solid else 0.0
                    e0, e1 = side(p0, b), side(p1, b)
                    mesh.both((e0[0], e0[1] - gap, e0[2]), (e1[0], e1[1] - gap, e1[2]), (e1[0], -0.3, e1[2]), (e0[0], -0.3, e0[2]), 2 if solid else 3,
                              [(v0, 1 - e0[1] / 4), (v1, 1 - e1[1] / 4), (v1, 1), (v0, 1)])
    end = ramp[-1]
    for mesh, solid in ((g, False), (c, True)):            # the wall under the end of the ramp
        top = end[1] - (0.05 if solid else 0.0)
        mesh.both((end[0], top, ROAD_Z - W), (end[0], top, ROAD_Z + W), (end[0], -0.3, ROAD_Z + W), (end[0], -0.3, ROAD_Z - W), 2 if solid else 3,
                  [(0, 0), (2, 0), (2, 1), (0, 1)])
    # --- the boundary wall, on the ground's edge ------------------------------------------------------------------------------------
    for k in range(cells):
        for (i0, j0, i1, j1) in ((k, 0, k + 1, 0), (cells, k, cells, k + 1), (k + 1, cells, k, cells), (0, k + 1, 0, k)):
            a = (-EDGE + i0 * CELL, ground(i0, j0), -EDGE + j0 * CELL); b = (-EDGE + i1 * CELL, ground(i1, j1), -EDGE + j1 * CELL)
            q = (a, b, (b[0], b[1] + WALL, b[2]), (a[0], a[1] + WALL, a[2])); uv = [(k * CELL / 4, 1), ((k + 1) * CELL / 4, 1), ((k + 1) * CELL / 4, 0), (k * CELL / 4, 0)]
            g.both(*q, 3, uv); c.both(*q, 2)
    # --- houses: four walls (both windings) and a roof ------------------------------------------------------------------------------
    for (cx, cz, hx, hz, top) in houses(height):
        x0, x1, z0, z1, y0, y1 = cx - hx, cx + hx, cz - hz, cz + hz, GROUND_Y - 0.1, GROUND_Y + top
        for (ax, az), (bx, bz) in (((x0, z0), (x1, z0)), ((x1, z0), (x1, z1)), ((x1, z1), (x0, z1)), ((x0, z1), (x0, z0))):
            q = ((ax, y0, az), (bx, y0, bz), (bx, y1, bz), (ax, y1, az))
            u, v = math.hypot(bx - ax, bz - az) / FLOOR, top / FLOOR
            g.both(*q, 4, [(0, v), (u, v), (u, 0), (0, 0)]); c.both(*q, 2)
        roof = ((x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0))
        g.quad(*roof, 5, [(p[0] / 3.0, p[2] / 3.0) for p in roof], facing=(0, 1, 0)); c.quad(*roof, 2, facing=(0, 1, 0))
    big = 3 * EDGE; cs = 8; size = 2 * big / cs             # far below: where a car that left the map lands
    for i in range(cs):
        for j in range(cs):
            x0, z0 = -big + i * size, -big + j * size
            c.quad((x0, GROUND_Y - 6, z0), (x0, GROUND_Y - 6, z0 + size), (x0 + size, GROUND_Y - 6, z0 + size), (x0 + size, GROUND_Y - 6, z0), 3, facing=(0, 1, 0))
    # --- lap gates ------------------------------------------------------------------------------------------------------------------
    gates, gate_ring = Mesh(), []                           # gate_ring: the ring sample of each gate
    def gate(left, right, lo, hi, forward):
        v = [(left[0], lo, left[1]), (right[0], lo, right[1]), (left[0], hi, left[1]), (right[0], hi, right[1])]      # low left, low right, high left, high right
        e1 = tuple(v[1][k] - v[0][k] for k in range(3)); e2 = tuple(v[2][k] - v[0][k] for k in range(3))
        fx, fz = e1[1] * e2[2] - e1[2] * e2[1], e1[0] * e2[1] - e1[1] * e2[0]
        if fx * forward[0] + fz * forward[1] < 0: v = [v[1], v[0], v[3], v[2]]
        i = len(gates.t) // 2; base = len(gates.v); gates.v += v
        gates.t += [(base, base + 1, base + 2, i), (base + 2, base + 1, base + 3, i)]
    for r in range(0, n, GATE):
        x, z, nx, nz, h, s, tx, tz = ring[r]
        gate((x + nx * W, z + nz * W), (x - nx * W, z - nz * W), h - 0.05, h + 1.8, (tx, tz)); gate_ring.append(r)
    ng = len(gate_ring); assert ng <= 250, ng
    on_straight = lambda r, x0, x1: abs(ring[r][1] - ROAD_Z) < 1.0 and x0 <= ring[r][0] <= x1
    crest = next(k for k, r in enumerate(gate_ring) if on_straight(r, -54.0, 1e9))                    # the first gate at the top of the hill
    landed = next(k for k, r in enumerate(gate_ring) if on_straight(r, RAMP_X + RAMP_L + 30.0, 1e9))  # the first gate well behind the jump
    # --- for the other files of the archive --------------------------------------------------------------------------------------------
    route = [(p[0], p[1]) for p in ring]                   # the lap on the map
    ribbon = [((p[0], p[4], p[1]), (p[2], 0.0, p[3])) for p in ring]      # centre and unit vector across, in lap order
    white = lambda m: [(255, 255, 255, 255)] * len(m.v)
    gm = build.matlist([build.material((255, 255, 255, 255), t, TEX_FILTER) for t in TEXTURES])
    cm = build.matlist([build.material(s) for s in (SURF_ROAD, SURF_GRASS, SURF_WALL, SURF_OUT)])
    lm = build.matlist([build.material((i, 0, 0, 255)) for i in range(ng)])
    files = {
        "graphics": build.new_world(0x4001004c, gm, g.v, g.t, prelit=white(g), uvs=[g.uv]),
        "collision": build.new_world(0x40000048, cm, c.v, c.t, prelit=white(c), coll=True),
        "lap": build.new_world(0x40000040, lm, gates.v, gates.t, coll=True),
        # restarts (after a point is won) only where the whole hill is still ahead or the jump is behind
        "lapdata": ("-- lapdata.lua (generated)\n\nLap_Variations(1)\n\nLap_Line(0)\nLap_Line(%d)\nLap_Line_End()\n\nSafe_Start_Lines(0,%d)\n"
                    "Safe_Start_Lines(%d,%d)\n\nSplit_Sector(0, %d)\nSplit_Sector(1, %d)\n"
                    % (ng - 1, max(0, crest - 1), landed, ng - 1, ng // 3, 2 * ng // 3)).encode(),
    }
    length = n * step
    return files, dict(gates=ng, length=length, ring=ring, route=route, ribbon=ribbon, graphics=g, height=height,
                       tris=(len(g.t), len(c.t), len(gates.t)), verts=(len(g.v), len(c.v)))

if __name__ == "__main__":
    files, info = make()
    print({k: len(v) for k, v in files.items()}, {k: v for k, v in info.items() if k in ("gates", "length", "tris", "verts")})
