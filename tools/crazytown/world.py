"""world.py: RenderWare 3.7 world (.BSP) files as plain data, and back to the same bytes.

World = header + materials + a tree of plane sectors over atomic sectors.  An atomic sector holds vertices, optional normals,
prelight colours and texture coordinates, triangles (v0, v1, v2, material), a BinMesh extension (per-material index lists for
drawing) and optionally a Collision extension (RpCollTree: a kd-tree over the sector's triangles).
"""
import struct
import rw

F_TRISTRIP, F_TEXTURED, F_PRELIT, F_NORMALS, F_LIGHT, F_MODULATE, F_POSITIONS, F_TEXTURED2 = 1, 4, 8, 0x10, 0x20, 0x40, 0x40, 0x80

class Sector:      # atomic sector
    pass

class Plane:       # plane sector
    pass

def tex_sets(flags):
    n = (flags >> 16) & 0xff
    return n if n else (2 if flags & F_TEXTURED2 else 1 if flags & F_TEXTURED else 0)

def parse_coll(data):
    ver, cid, csize, cver = struct.unpack_from("<IIII", data, 0)
    assert cid == 0x2c and csize == len(data) - 16
    sid, ssize, sver = struct.unpack_from("<III", data, 16)
    assert sid == 1 and ssize == csize - 12
    b = data[28:]
    use_map, = struct.unpack_from("<I", b, 0)
    bbox = struct.unpack_from("<6f", b, 4)
    ntri, nsplit = struct.unpack_from("<II", b, 28)
    o = 36
    splits = [struct.unpack_from("<BBHfBBHf", b, o + 16 * i) for i in range(nsplit)]
    o += 16 * nsplit
    tmap = list(struct.unpack_from("<%dH" % ntri, b, o)) if use_map else None
    o += 2 * ntri if use_map else 0
    assert o == len(b), (o, len(b))
    return dict(ver=ver, cver=cver, sver=sver, use_map=use_map, bbox=bbox, ntri=ntri, splits=splits, map=tmap)

def build_coll(c):
    b = struct.pack("<I6fII", c["use_map"], *c["bbox"], c["ntri"], len(c["splits"]))
    b += b"".join(struct.pack("<BBHfBBHf", *s) for s in c["splits"])
    if c["use_map"]:
        b += struct.pack("<%dH" % c["ntri"], *c["map"])
    st = struct.pack("<III", 1, len(b), c["sver"]) + b
    return struct.pack("<IIII", c["ver"], 0x2c, len(st), c["cver"]) + st

def parse_binmesh(data):
    flags, nmesh, total = struct.unpack_from("<III", data, 0)
    o, meshes = 12, []
    for i in range(nmesh):
        n, mat = struct.unpack_from("<II", data, o)
        meshes.append((mat, list(struct.unpack_from("<%dI" % n, data, o + 8))))
        o += 8 + 4 * n
    assert o == len(data) and total == sum(len(m[1]) for m in meshes)
    return dict(flags=flags, meshes=meshes)

def build_binmesh(m):
    out = struct.pack("<III", m["flags"], len(m["meshes"]), sum(len(i) for _, i in m["meshes"]))
    for mat, idx in m["meshes"]:
        out += struct.pack("<II%dI" % len(idx), len(idx), mat, *idx)
    return out

def parse_node(c, flags):
    if c.id == 0xA:
        p = Plane()
        p.version = c.version
        p.type, p.value, lw, rw_, p.left_value, p.right_value = struct.unpack("<IfIIff", c.children[0].data)
        p.sversion = c.children[0].version
        p.left, p.right = parse_node(c.children[1], flags), parse_node(c.children[2], flags)
        assert lw == (c.children[1].id == 9) and rw_ == (c.children[2].id == 9) and len(c.children) == 3
        return p
    assert c.id == 9
    s = Sector()
    s.version, s.sversion = c.version, c.children[0].version
    d = c.children[0].data
    s.mat_base, nt, nv = struct.unpack_from("<III", d, 0)
    s.bbox = struct.unpack_from("<6f", d, 12)
    s.coll_present, s.unused = struct.unpack_from("<II", d, 36)
    o = 44
    s.vertices = [struct.unpack_from("<3f", d, o + 12 * i) for i in range(nv)]; o += 12 * nv
    s.normals = s.prelit = None
    if flags & F_NORMALS:
        s.normals = [struct.unpack_from("<4b", d, o + 4 * i) for i in range(nv)]; o += 4 * nv
    if flags & F_PRELIT:
        s.prelit = [struct.unpack_from("<4B", d, o + 4 * i) for i in range(nv)]; o += 4 * nv
    s.uvs = []
    for k in range(tex_sets(flags)):
        s.uvs.append([struct.unpack_from("<2f", d, o + 8 * i) for i in range(nv)]); o += 8 * nv
    s.triangles = [struct.unpack_from("<4H", d, o + 8 * i) for i in range(nt)]; o += 8 * nt
    assert o == len(d), (o, len(d))
    assert len(c.children) == 2 and c.children[1].id == 3
    s.binmesh = s.coll = None
    s.ext_order, s.ext_other = [], {}
    for e in c.children[1].children:
        s.ext_order.append((e.id, e.version))
        if e.id == 0x50E: s.binmesh = parse_binmesh(e.data)
        elif e.id == 0x11D: s.coll = parse_coll(e.data)
        else: s.ext_other[e.id] = e
    s.ext_version = c.children[1].version
    return s

def build_node(n, flags):
    if isinstance(n, Plane):
        st = rw.Chunk(1, n.sversion, struct.pack("<IfIIff", n.type, n.value, isinstance(n.left, Sector), isinstance(n.right, Sector), n.left_value, n.right_value))
        return rw.Chunk(0xA, n.version, None, [st, build_node(n.left, flags), build_node(n.right, flags)])
    d = struct.pack("<III6fII", n.mat_base, len(n.triangles), len(n.vertices), *n.bbox, n.coll_present, n.unused)
    d += b"".join(struct.pack("<3f", *v) for v in n.vertices)
    if flags & F_NORMALS: d += b"".join(struct.pack("<4b", *v) for v in n.normals)
    if flags & F_PRELIT: d += b"".join(struct.pack("<4B", *v) for v in n.prelit)
    for uv in n.uvs: d += b"".join(struct.pack("<2f", *v) for v in uv)
    d += b"".join(struct.pack("<4H", *t) for t in n.triangles)
    ext = []
    for id, ver in n.ext_order:
        if id == 0x50E: ext.append(rw.Chunk(id, ver, build_binmesh(n.binmesh)))
        elif id == 0x11D: ext.append(rw.Chunk(id, ver, build_coll(n.coll)))
        else: ext.append(n.ext_other[id])
    return rw.Chunk(9, n.version, None, [rw.Chunk(1, n.sversion, d), rw.Chunk(3, n.ext_version, None, ext)])

class World:
    pass

def parse(buf):
    top = rw.parse(buf)
    assert len(top) == 1 and top[0].id == 0xB
    c = top[0]
    w = World()
    w.version, w.sversion = c.version, c.children[0].version
    h = struct.unpack("<I3f6I6f", c.children[0].data)
    w.root_is_sector, w.inv_origin, (w.ntri, w.nvert, w.nplane, w.nsector, w.col_sector_size, w.flags), w.bbox = h[0], h[1:4], h[4:10], h[10:16]
    assert [k.id for k in c.children] in ([1, 8, 9, 3], [1, 8, 0xA, 3])
    w.matlist = c.children[1]                      # kept as chunks (see materials())
    w.root = parse_node(c.children[2], w.flags)
    w.ext = c.children[3]
    return w

def build(w):
    h = struct.pack("<I3f6I6f", w.root_is_sector, *w.inv_origin, w.ntri, w.nvert, w.nplane, w.nsector, w.col_sector_size, w.flags, *w.bbox)
    c = rw.Chunk(0xB, w.version, None, [rw.Chunk(1, w.sversion, h), w.matlist, build_node(w.root, w.flags), w.ext])
    return rw.serialize([c])

def sectors(w):
    out = []
    def go(n):
        if isinstance(n, Plane): go(n.left); go(n.right)
        else: out.append(n)
    go(w.root)
    return out

def materials(w):
    """[(colour rgba, texture name or None, mask name, surface (ambient, specular, diffuse), [extension chunk names])]"""
    out = []
    for m in w.matlist.find(7):
        flags, r, g, b, a, unused, textured, amb, spec, dif = struct.unpack("<I4BiI3f", m.children[0].data)
        tex = mask = None
        for t in m.find(6):
            strs = t.find(2)
            tex, mask = strs[0].data.split(b"\0")[0].decode("latin1"), strs[1].data.split(b"\0")[0].decode("latin1")
        out.append(((r, g, b, a), tex, mask, (amb, spec, dif), [e.name for e in m.find(3)[0].children]))
    return out
