"""build.py: make the game's world files from plain data (the reverse direction of world.py's parser)."""
import struct
import rw, world

VER = 0x1c020a00

def colltree(vertices, triangles, leaf=3):
    """RpCollTree over the triangles: a kd-tree of splits.  Each split has a left and a right half: (type, contents, index, value);
    type = axis * 4 (+1 on the left), contents = 0xff for another split (index = its number) or the number of triangles of a leaf
    (index = their start in the map); the left half holds triangles with max <= value on the axis, the right one min >= value."""
    cent = [tuple(sum(vertices[v][a] for v in t[:3]) / 3 for a in range(3)) for t in triangles]
    lo = [tuple(min(vertices[v][a] for v in t[:3]) for a in range(3)) for t in triangles]
    hi = [tuple(max(vertices[v][a] for v in t[:3]) for a in range(3)) for t in triangles]
    splits, order = [], []
    def half(ids, axis, left):
        value = max(hi[i][axis] for i in ids) if left else min(lo[i][axis] for i in ids)
        if len(ids) <= leaf:
            start = len(order); order.extend(ids)
            return (axis * 4 + left, len(ids), start, value)
        return (axis * 4 + left, 0xff, node(ids), value)
    def node(ids):
        me = len(splits); splits.append(None)
        ext = [max(cent[i][a] for i in ids) - min(cent[i][a] for i in ids) for a in range(3)]
        axis = ext.index(max(ext))
        ids = sorted(ids, key=lambda i: cent[i][axis])
        m = len(ids) // 2
        l, r = half(ids[:m], axis, 1), half(ids[m:], axis, 0)
        splits[me] = l + r
        return me
    assert len(triangles) >= 2
    node(list(range(len(triangles))))
    assert len(splits) < 65536
    bbox = tuple(min(v[a] for v in vertices) for a in range(3)) + tuple(max(v[a] for v in vertices) for a in range(3))
    return dict(ver=0x37002, cver=VER, sver=VER, use_map=1, bbox=bbox, ntri=len(triangles), splits=splits, map=order)

def new_world(flags, matlist, vertices, triangles, prelit=None, uvs=(), normals=None, coll=False, ext=None):
    """a world of one atomic sector.  triangles: (v0, v1, v2, material); drawn as triangle lists (no strips)."""
    assert len(vertices) < 65536
    flags &= ~world.F_TRISTRIP
    s = world.Sector()
    s.version = s.sversion = s.ext_version = VER
    s.mat_base, s.coll_present, s.unused = 0, 0, 0
    inf = tuple(min(v[a] for v in vertices) for a in range(3)); sup = tuple(max(v[a] for v in vertices) for a in range(3))
    s.bbox = inf + sup
    s.vertices, s.normals, s.prelit, s.uvs, s.triangles = vertices, normals, prelit, list(uvs), triangles
    assert bool(flags & world.F_PRELIT) == (prelit is not None) and world.tex_sets(flags) == len(s.uvs) and bool(flags & world.F_NORMALS) == (normals is not None)
    meshes = {}
    for t in triangles:
        meshes.setdefault(t[3], []).extend(t[:3])
    s.binmesh = dict(flags=0, meshes=sorted(meshes.items()))
    s.ext_order, s.ext_other = [(0x50E, VER)], {}
    s.coll = None
    if coll:
        s.coll = colltree(vertices, triangles); s.ext_order.append((0x11D, VER))
    w = world.World()
    w.version = w.sversion = VER
    w.root_is_sector, w.inv_origin = 1, (-0.0, -0.0, -0.0)
    w.ntri, w.nvert, w.nplane, w.nsector, w.col_sector_size, w.flags = len(triangles), len(vertices), 0, 1, 0, flags
    w.bbox = sup + inf
    w.matlist, w.root = matlist, s
    w.ext = ext if ext is not None else rw.Chunk(3, VER, None, [])
    return world.build(w)

def material(colour, texture=None, filter=0x1106, ext=None):
    st = struct.pack("<I4BiI3f", 0, *colour, 0, texture is not None, 1.0, 1.0, 1.0)
    kids = [rw.Chunk(1, VER, st)]
    if texture is not None:
        pad = lambda s: s.encode("latin1") + bytes(4 - len(s) % 4)
        kids.append(rw.Chunk(6, VER, None, [rw.Chunk(1, VER, struct.pack("<I", filter)), rw.Chunk(2, VER, pad(texture)), rw.Chunk(2, VER, pad("")),
                                           rw.Chunk(3, VER, None, [])]))
    kids.append(rw.Chunk(3, VER, None, ext or []))
    return rw.Chunk(7, VER, None, kids)

def matlist(materials):
    st = struct.pack("<I%di" % len(materials), len(materials), *([-1] * len(materials)))
    return rw.Chunk(8, VER, None, [rw.Chunk(1, VER, st)] + list(materials))

def soup(w):
    """a parsed world's sectors merged into one vertex / triangle list"""
    V, T, P, U, N = [], [], [], None, []
    for s in world.sectors(w):
        base = len(V)
        V += s.vertices
        if s.prelit: P += s.prelit
        if s.normals: N += s.normals
        if s.uvs:
            U = U or [[] for _ in s.uvs]
            for k, uv in enumerate(s.uvs): U[k] += uv
        T += [(a + base, b + base, c + base, m + s.mat_base) for a, b, c, m in s.triangles]
    return V, T, (P or None), (U or []), (N or None)
