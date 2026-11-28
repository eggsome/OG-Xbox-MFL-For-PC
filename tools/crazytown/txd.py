"""txd.py: the game's platform-independent texture dictionaries (RenderWare chunk 0x23): a list of textures, each a chain of
mipmap images (RwImage: width, height, depth, stride, pixels, palette for 4/8 bit) and a Texture chunk (filter, name, mask name)."""
import struct
import rw

class Tex:
    pass

def parse(buf):
    id, size, ver = struct.unpack_from("<III", buf, 0)
    assert id == 0x23 and size == len(buf) - 12
    count, kind = struct.unpack_from("<HH", buf, 12)
    o, out = 16, []
    for i in range(count):
        t = Tex()
        nm, = struct.unpack_from("<I", buf, o); o += 4
        t.images = []
        for k in range(nm):
            cid, csize, cver = struct.unpack_from("<III", buf, o)
            assert cid == 0x18
            sid, ssize, sver = struct.unpack_from("<III", buf, o + 12)
            w, h, depth, stride = struct.unpack_from("<IIII", buf, o + 24)
            pix = buf[o + 40:o + 40 + stride * h]
            pal = buf[o + 40 + stride * h:o + 12 + csize]
            assert len(pal) == (0 if depth > 8 else 4 << depth), (depth, len(pal))
            t.images.append((w, h, depth, stride, pix, pal))
            o += 12 + csize
        cid, csize, cver = struct.unpack_from("<III", buf, o)
        assert cid == 6
        t.texture = rw.parse(buf, o, o + 12 + csize, False)[0]
        strs = t.texture.find(2)
        t.name, t.mask = strs[0].data.split(b"\0")[0].decode("latin1"), strs[1].data.split(b"\0")[0].decode("latin1")
        t.filter, = struct.unpack("<I", t.texture.children[0].data)
        o += 12 + csize
        out.append(t)
    assert o == len(buf)
    return out, kind, ver

def build(texs, kind=1, ver=0x1c020a00):
    body = struct.pack("<HH", len(texs), kind)
    for t in texs:
        body += struct.pack("<I", len(t.images))
        for w, h, depth, stride, pix, pal in t.images:
            img = struct.pack("<III", 1, 16, ver) + struct.pack("<IIII", w, h, depth, stride) + pix + pal
            body += struct.pack("<III", 0x18, len(img), ver) + img
        body += rw.serialize([t.texture])
    return struct.pack("<III", 0x23, len(body), ver) + body
