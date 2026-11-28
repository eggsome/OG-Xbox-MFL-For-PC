"""rw.py: RenderWare binary stream chunks (id, size, library stamp) as a tree, and back to the same bytes."""
import struct

NAMES = {1: "Struct", 2: "String", 3: "Extension", 5: "Camera", 6: "Texture", 7: "Material", 8: "MaterialList", 9: "AtomicSector",
         0xA: "PlaneSector", 0xB: "World", 0xC: "Spline", 0xD: "Matrix", 0xE: "FrameList", 0xF: "Geometry", 0x10: "Clump", 0x12: "Light",
         0x14: "Atomic", 0x15: "TextureNative", 0x16: "TexDictionary", 0x18: "Image", 0x1A: "GeometryList", 0x1B: "AnimAnimation",
         0x23: "PITexDictionary", 0x2B: "UVAnimDict", 0x50E: "BinMesh", 0x510: "NativeData", 0x11D: "Collision", 0x116: "SkinPLG",
         0x11E: "HAnim", 0x11F: "UserData", 0x120: "MatFX", 0x135: "UVAnimPLG", 0x105: "MorphPLG", 0x127: "ParticlesStd", 0x12A: "RightToRender"}
# chunks whose payload is a sequence of chunks
CONTAINERS = {3, 6, 7, 8, 9, 0xA, 0xB, 0xE, 0xF, 0x10, 0x12, 0x14, 0x16, 0x1A, 5, 0x2B}

class Chunk:
    def __init__(self, id, version, data=None, children=None):
        self.id, self.version, self.data, self.children = id, version, data, children
    @property
    def name(self):
        return NAMES.get(self.id, "0x%x" % self.id)
    def find(self, id):
        return [c for c in self.children or [] if c.id == id]

def parse(buf, start=0, end=None, top=True):
    """chunks in buf[start:end]; at top level trailing bytes that are not a chunk are returned as a raw pseudo-chunk (id -1)"""
    end = len(buf) if end is None else end
    out, o = [], start
    while o + 12 <= end:
        id, size, ver = struct.unpack_from("<III", buf, o)
        if o + 12 + size > end or (top and id == 0 and size == 0):
            break
        body = (o + 12, o + 12 + size)
        kids = None
        if id in CONTAINERS:
            kids = parse(buf, body[0], body[1], False)
            if sum(12 + len(serialize([k])) - 12 for k in kids) != size:      # not cleanly a chunk sequence: keep raw
                kids = None
        out.append(Chunk(id, ver, None if kids is not None else buf[body[0]:body[1]], kids))
        o = body[1]
    if o != end:
        out.append(Chunk(-1, 0, buf[o:end]))
    return out

def serialize(chunks):
    out = bytearray()
    for c in chunks:
        if c.id == -1:
            out += c.data; continue
        body = serialize(c.children) if c.children is not None else c.data
        out += struct.pack("<III", c.id, len(body), c.version) + body
    return bytes(out)

def tree(chunks, depth=0, limit=3):
    for c in chunks:
        print("  " * depth + "%s %d" % (c.name if c.id != -1 else "(raw tail)", len(serialize([c])) - (12 if c.id != -1 else 0)))
        if c.children and depth < limit:
            tree(c.children, depth + 1, limit)
