"""piz.py: read and write the game's PIZ archives (magic, count at 8, 0x80-byte entries from 0x800: name[0x74], offset, size, extra)."""
import struct

def read(path):
    d = open(path, "rb").read()
    assert d[:4] == b"PIZ\0", path
    out = []
    for k in range(struct.unpack_from("<I", d, 8)[0]):
        e = 0x800 + k * 0x80
        off, size, extra = struct.unpack_from("<III", d, e + 0x74)
        out.append((d[e:e + 0x74].split(b"\0")[0].decode("latin1"), d[off:off + size], extra))
    return out, d

def files(path):
    return {n.upper(): b for n, b, x in read(path)[0]}

def write(path, entries):
    """entries: [(name, bytes, extra)]; data from the first 0x800 boundary after the table, each file on a 0x800 boundary"""
    assert len(entries) <= 256
    table = bytearray(len(entries) * 0x80)
    off = (0x800 + len(table) + 0x7ff) // 0x800 * 0x800
    body = bytearray()
    base = off
    for k, (name, data, extra) in enumerate(entries):
        nm = name.encode("latin1")
        table[k * 0x80:k * 0x80 + len(nm)] = nm
        struct.pack_into("<III", table, k * 0x80 + 0x74, off, len(data), extra)
        body += data + bytes(-len(data) % 0x800)
        off = base + len(body)
    head = b"PIZ\0" + struct.pack("<III", 3, len(entries), 0xcccccccc)
    head += bytes(0x800 - len(head))
    pad = bytes(base - 0x800 - len(table))
    open(path, "wb").write(head + table + pad + body)
