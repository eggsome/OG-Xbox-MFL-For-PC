#!/usr/bin/env python3
"""tools/crazytown/make_crazytown.py <game folder>/ToastArt/TRACKS: writes CrazyTwn.piz there, the archive of the track "Crazy Town"
(src/mfl_custom_track.c).

The track is generated: gen_track.py makes the circuit (road, pavements, the ground, houses, boundary wall), its collision world, the
lap gates and the lap script from the control points at its top; this file adds the course script, the bots' routes, the power-ups,
the outline model of the loading screen and the two pictures of the event list (rendered here from the track's triangles).
Textures, sky, lights and the models the power-ups and the outline are made from are copied from the game's own archives (NT1.piz
and Keys.piz in that folder, SFX.piz and Perm.piz in ../Common), so no game data is in this repository.  The other files here read
and write the game's formats: piz.py (archives), rw.py (RenderWare chunks), world.py / build.py (world and collision files), txd.py
(texture dictionaries).  Needs Python with Pillow.
"""
import copy, math, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import piz, rw, txd, gen_track

def renamed(t, name):
    t = copy.deepcopy(t)
    s = t.texture.find(2)[0]
    s.data = name.encode("latin1") + bytes(4 - len(name) % 4)
    t.name = name
    return t

COURSE = b'''-- course.lua (Crazy Town, generated)
Texture_Dictionary_Filename("textures.txd")
World_Bsp_Filename("main.bsp")
AI_Bsp_Filename("ai.bsp")
Collision_Bsp_Filename("coll.bsp")
Lights_Filename("lights.dff")
Sky_Filename("skydome.dff")
Setup_Fog(500,3000,255,255,255)
'''
def frame_positions(dff, positions):
    """the clump `dff` with the positions of its frames 2.. replaced (frames 0 and 1 are the clump's roots)"""
    t = rw.parse(dff, 0, len(dff), True)
    st = t[0].find(0xe)[0].children[0]; d = bytearray(st.data)
    count, = struct.unpack_from("<I", d, 0)
    assert len(positions) == count - 2
    for k, p in enumerate(positions):
        struct.pack_into("<3f", d, 4 + 56 * (k + 2) + 36, *p)
    st.data = bytes(d)
    return rw.serialize(t)

def powerups(info, nt1_dff):
    """NT1's power-up model (23 pick-ups: four rows of four across the road and seven single ones, the kind of each is in the model)
    with the pick-ups moved onto this circuit, 0.25 m above the road as there; none on the hill or near the jump"""
    ring = info["ring"]; n = len(ring)
    def at(frac, off, along=0):
        x, z, nx, nz, h = ring[(int(frac * n) + along) % n][:5]
        return (x + nx * off, h + 0.25, z + nz * off)
    row = lambda frac: [at(frac, -2.25 + 1.5 * k, k % 2) for k in range(4)]
    single = lambda k: at((0.22, 0.34, 0.46, 0.58, 0.70, 0.82, 0.93)[k], 1.5 if k % 2 else -1.5)
    pos = row(0.28) + row(0.40) + row(0.52) + [single(0)] + row(0.64) + [single(k) for k in range(1, 7)]
    return frame_positions(nt1_dff, pos)

def outline(info, map_dff):
    """the track outline of the loading screen (the game's map_<id>.dff of perm.piz): a 5 m wide ribbon along the lap, its first two vertices white (the start), made from NT1's model with the geometry replaced"""
    rib = info["ribbon"]; rib = rib + rib[:1]; n = len(rib) - 1; v = []
    for p, w in rib:
        v += [tuple(p[k] + w[k] * 2.5 for k in range(3)), tuple(p[k] - w[k] * 2.5 for k in range(3))]
    tris = []
    for k in range(n):
        tris += [(2 * k + 1, 2 * k + 3, 0, 2 * k), (2 * k + 2, 2 * k, 0, 2 * k + 3)]
    lo = [min(p[a] for p in v) for a in range(3)]; hi = [max(p[a] for p in v) for a in range(3)]
    mid = [(lo[a] + hi[a]) / 2 for a in range(3)]; radius = max(math.dist(p, mid) for p in v)
    body = struct.pack("<IIII", 0x1000f, len(tris), len(v), 1)
    body += b"".join(b"\xff\xff\xff\xff" if k < 2 else b"\x80\x80\x80\xff" for k in range(len(v)))
    body += b"".join(struct.pack("<ff", k % 2, (k // 2) % 2) for k in range(len(v)))
    body += b"".join(struct.pack("<4H", *t) for t in tris)
    body += struct.pack("<4fII", *mid, radius, 1, 0) + b"".join(struct.pack("<3f", *p) for p in v)
    t = rw.parse(map_dff, 0, len(map_dff), True)
    geo = t[0].find(0x1a)[0].find(0xf)[0]
    geo.children[0].data = body
    strip = [i for k in range(n, -1, -1) for i in (2 * k, 2 * k + 1)]
    mesh = [c for c in geo.find(3)[0].children if c.id == 0x50e][0]
    mesh.data = struct.pack("<III", 1, 1, len(strip)) + struct.pack("<II", len(strip), 0) + struct.pack("<%dI" % len(strip), *strip)
    return rw.serialize(t)

# --- the two pictures of the event list: the track's own triangles, flat shaded, drawn back to front ---------------------------------
COLOURS = ((96, 96, 100), (168, 168, 164), (74, 128, 52), (120, 116, 108), (186, 178, 160), (120, 70, 58))      # per graphics material
def picture(info, eye, target, fov=50.0, size=256, over=3):
    from PIL import Image, ImageDraw
    g = info["graphics"]; S = size * over
    im = Image.new("RGB", (S, S)); dr = ImageDraw.Draw(im)
    for y in range(S):                                      # sky above, haze at the horizon
        t = y / S; dr.line([(0, y), (S, y)], fill=(int(110 + 120 * t), int(150 + 90 * t), int(225 + 20 * t)))
    f = [target[k] - eye[k] for k in range(3)]; l = math.sqrt(sum(a * a for a in f)); f = [a / l for a in f]
    r = [f[2], 0.0, -f[0]]; l = math.hypot(r[0], r[2]); r = [a / l for a in r]
    u = [r[1] * f[2] - r[2] * f[1], r[2] * f[0] - r[0] * f[2], r[0] * f[1] - r[1] * f[0]]
    if u[1] < 0: u = [-a for a in u]
    k = (S / 2) / math.tan(math.radians(fov) / 2); sun = (0.35, 0.8, 0.45)
    cam = []
    for p in g.v:
        d = [p[a] - eye[a] for a in range(3)]
        cam.append((sum(d[a] * r[a] for a in range(3)), sum(d[a] * u[a] for a in range(3)), sum(d[a] * f[a] for a in range(3))))
    out = []
    for a, b, c, m in g.t:
        A, B, C = cam[a], cam[b], cam[c]
        if min(A[2], B[2], C[2]) < 0.5: continue
        P, Q, R = g.v[a], g.v[b], g.v[c]
        e1 = [Q[i] - P[i] for i in range(3)]; e2 = [R[i] - P[i] for i in range(3)]
        nrm = [e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0]]
        l = math.sqrt(sum(x * x for x in nrm)) or 1.0; nrm = [x / l for x in nrm]
        if m <= 2 and nrm[1] < 0: nrm = [-x for x in nrm]
        if m >= 3 and sum(nrm[i] * (eye[i] - P[i]) for i in range(3)) <= 0: continue      # walls are stored with both windings
        light = 0.55 + 0.45 * max(0.0, sum(nrm[i] * sun[i] for i in range(3)))
        depth = (A[2] + B[2] + C[2]) / 3 - (0.6 if m < 2 else 0.0)      # the road lies on the ground: drawn after it
        col = tuple(int(x * light) for x in COLOURS[m])
        out.append((depth, [(S / 2 + k * V[0] / V[2], S / 2 - k * V[1] / V[2]) for V in (A, B, C)], col))
    out.sort(key=lambda t: -t[0])
    for depth, pts, col in out: dr.polygon(pts, fill=col)
    return im.resize((size, size), Image.LANCZOS)

def pictures(info, template):
    """PICTURES.TXD: CrazyTown1 and CrazyTown2, 256 x 256 with 256 colours as the pictures of the game's TrackImages.txd"""
    from PIL import Image
    views = (((-150.0, 150.0, -230.0), (0.0, -15.0, -5.0)), ((30.0, 30.0, -135.0), (10.0, 2.0, -85.0)))
    out = []
    for name, (eye, target) in zip(("CrazyTown1", "CrazyTown2"), views):
        im = picture(info, eye, target).quantize(256, method=Image.MEDIANCUT, dither=Image.NONE)
        pal = im.getpalette()[:768]; pal += [0] * (768 - len(pal))
        t = renamed(template, name)
        w, h, depth, stride, pix, old = t.images[0]
        assert (w, h, depth, stride) == (256, 256, 8, 256)
        t.images = [(w, h, depth, stride, im.tobytes(), b"".join(bytes(pal[3 * i:3 * i + 3]) + b"\xff" for i in range(256)))]
        out.append(t)
    return out

SOURCE = {"gen_Road": "Road", "gen_RoadSide": "Sidewalk", "gen_Grass": "Grass", "gen_StoneWall": "StoneWall", "gen_Window": "Window", "gen_Roof": "Roof"}

def opaque(t):
    """NT1 draws its road and pavement half transparent over a water plane; here they are the ground itself"""
    t.images = [(w, h, depth, stride, pix, bytes(255 if k % 4 == 3 else b for k, b in enumerate(pal)) if depth <= 8 else pal)
                for (w, h, depth, stride, pix, pal) in t.images]
    return t

def routes(info):
    """the bots' routes (the game's AI<id>.AI: chunk 0x13269902 of 0x11884 bytes): an empty danger grid and, as in NT1's file, two racing
    lines, an inside line and two slow lines, each a closed list of at most 64 points (x, z)."""
    line = info["route"]; n = len(line); step = -(-n // 62); sets = {}
    def offset(off):
        pts = []
        for i in range(0, n, step):
            (x, z), (px, pz), (qx, qz) = line[i], line[i - 1], line[(i + 1) % n]
            tx, tz = qx - px, qz - pz; l = math.hypot(tx, tz) or 1.0
            pts.append((x - tz / l * off, z + tx / l * off))
        return pts[:64]
    for (s, k), off in {(0, 0): 0.0, (0, 1): 0.6, (1, 0): -0.6, (2, 0): 0.3, (2, 1): -0.3}.items():
        sets[s * 3 + k] = offset(off)
    body = struct.pack("<16384h", *([-1] * 16384)) + b"\xff" * 32768 + struct.pack("<i", 0)
    for r in range(12):
        pts = sets.get(r, [])
        body += b"".join(struct.pack("<ff", *p) for p in pts) + bytes(0x200 - 8 * len(pts)) + struct.pack("<i", len(pts))
    body += bytes(80)
    assert len(body) == 0x11884
    return struct.pack("<III", 0x13269902, len(body), 0x1c02000a) + body

if __name__ == "__main__":
    T = os.path.join(sys.argv[1], ""); C = os.path.join(T, "..", "Common", "")
    gen_track.TEXTURES = tuple(SOURCE)
    files, info = gen_track.make()
    keys = piz.files(T + "Keys.piz")
    nt1 = piz.files(T + "NT1.piz")
    tt, kind, ver = txd.parse(nt1["TEXTURES.TXD"])
    by = {t.name: t for t in tt}
    images, ikind, iver = txd.parse(piz.files(C + "SFX.piz")["TRACKIMAGES.TXD"])
    ents = [("COURSE.LUA", COURSE), ("LAPDATA.LUA", files["lapdata"]), ("MAIN.BSP", files["graphics"]), ("COLL.BSP", files["collision"]),
            ("AI.BSP", files["lap"]), ("TEXTURES.TXD", txd.build([opaque(renamed(by[SOURCE[n]], n)) for n in gen_track.TEXTURES], kind, ver)),
            ("ROUTES.AI", routes(info)), ("LIGHTS.DFF", keys["LIGHTS.DFF"]), ("SKYDOME.DFF", keys["SKYDOME.DFF"]),
            ("POWERUPS_GOLD.DFF", powerups(info, nt1["POWERUPS_GOLD.DFF"])),
            ("OUTLINE.DFF", outline(info, piz.files(C + "Perm.piz")["MAP_17.DFF"])),
            ("PICTURES.TXD", txd.build(pictures(info, images[0]), ikind, iver))]
    piz.write(T + "CrazyTwn.piz", [(n, b, 0) for n, b in ents])      # the game opens archives by their 8.3 name: at most 8 characters
    print("%sCrazyTwn.piz: %d gates, %.0f m, %d files" % (T, info["gates"], info["length"], len(ents)))
