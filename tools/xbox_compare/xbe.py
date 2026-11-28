"""xbe.py: read the Xbox executable by virtual address (path: $MFL_XBE, default default.xbe).

  python3 xbe.py <section> <out file>    writes one section as raw bytes (for objdump, see README.md)
"""
import os, struct, sys
class XBE:
    def __init__(s, p=None):
        p = p or os.environ.get("MFL_XBE", "default.xbe")
        s.d = open(p, "rb").read(); base, = struct.unpack_from("<I", s.d, 0x104); n, = struct.unpack_from("<I", s.d, 0x11c); sh, = struct.unpack_from("<I", s.d, 0x120)
        s.secs = []
        for i in range(n):
            fl, va, vs, ro, rs, na = struct.unpack_from("<IIIIII", s.d, sh - base + i * 56)
            s.secs.append((s.d[na - base:na - base + 16].split(b"\0")[0].decode(), va, vs, ro, rs))
    def rd(s, va, n):
        for nm, a, vs, ro, rs in s.secs:
            if a <= va < a + vs:
                o = va - a
                return (s.d[ro + o:ro + o + n] if o + n <= rs else bytes(n))
        return None
    def sec(s, va):
        for nm, a, vs, ro, rs in s.secs:
            if a <= va < a + vs: return nm

if __name__ == "__main__":
    x = XBE()
    for nm, a, vs, ro, rs in x.secs:
        if nm == sys.argv[1]:
            open(sys.argv[2], "wb").write(x.d[ro:ro + rs]); print("%s at 0x%x, %d bytes" % (nm, a, rs))
