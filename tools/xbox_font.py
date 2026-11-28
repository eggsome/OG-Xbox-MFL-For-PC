#!/usr/bin/env python3
"""tools/xbox_font.py <Font36.piz> [sheet.png]: the Xbox menu font, redrawn sharp, in place of the PC one.

The PC game's Font36.piz holds both menu fonts: FGDC20.TXD/.RWF (PC, arrow pictures) and XBOX/XBOXFGDC20.TXD/.RWF (Xbox, A/B/X/Y/START
and controller pictures, in an Xbox texture format the PC game cannot load).  This stores the sheet (default: assets/xbox_font/
fgdc20_8x.png, the Xbox font's layout drawn 8 times as large by tools/xbox_font_draw.py) as FGDC20.TXD, a 32-bit texture with mipmaps,
and the Xbox .RWF as FGDC20.RWF: its positions are fractions of the sheet, so it fits a sheet of any size unchanged.
A backup <file>.orig is kept (never overwritten); copy it back to undo.  Needs Pillow.
"""
import os, shutil, struct, sys
from PIL import Image

path = sys.argv[1]
sheet = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "xbox_font", "fgdc20_8x.png")
W, H = 512, 256                                            # the PC font's sheet
RW = 0x1c020a00                                            # the library stamp the game's own chunks carry

if not os.path.exists(path + ".orig"):
    shutil.copy2(path, path + ".orig")
d = bytearray(open(path + ".orig", "rb").read())           # always start from the original
assert d[:4] == b"PIZ\0"
ents = {}
for k in range(struct.unpack_from("<I", d, 8)[0]):        # directory at 0x800: name[0x74], offset, size, (unknown)
    e = 0x800 + k * 0x80
    ents[bytes(d[e:e + 0x74]).split(b"\0")[0].decode().upper()] = (e,) + struct.unpack_from("<II", d, e + 0x74)
get = lambda n: bytes(d[ents[n][1]:ents[n][1] + ents[n][2]])

rwf = get("XBOX/XBOXFGDC20.RWF")
new = Image.open(sheet).convert("RGBA")
assert new.size[0] == 2 * new.size[1], "the sheet is twice as wide as high"

# --- as a platform-independent texture dictionary: the PC one's own wrapping around new 32 bit images ----------------------------
p = get("FGDC20.TXD")
assert struct.unpack_from("<IIII", p, 0x2c) == (W, H, 8, W), "unexpected PC font texture"
tail = bytearray(p[0x3c + W * H + 1024:])                   # the texture chunk: filter + addressing, name, mask name
n = tail.index(b"FGDC20\0\0")
tail[n - 12:n + 8] = struct.pack("<II", 2, 12) + tail[n - 4:n] + b"XboxFGDC20\0\0"   # the name the Xbox .RWF asks for
struct.pack_into("<I", tail, 4, struct.unpack_from("<I", tail, 4)[0] + 4)
tail[0x18] = 6                                             # filter: linear between mipmap levels

images, level = [], new.convert("RGBa")
while True:
    w, h = level.size
    image = struct.pack("<III", 1, 16, RW) + struct.pack("<IIII", w, h, 32, w * 4) + level.convert("RGBA").tobytes()
    images.append(struct.pack("<III", 0x18, len(image), RW) + image)
    if w == 1 or h == 1:
        break
    level = level.resize((w // 2, h // 2), Image.BOX)
body = p[0x0c:0x10] + struct.pack("<I", len(images)) + b"".join(images) + bytes(tail)
txd = struct.pack("<III", 0x23, len(body), RW) + body

# --- into the archive: the .RWF over the PC one, the texture (too large for its old place) at the end -----------------------------
e, off, size = ents["FGDC20.RWF"]
assert len(rwf) <= size
d[off:off + size] = rwf + bytes(size - len(rwf))
struct.pack_into("<I", d, e + 0x78, len(rwf))
d += bytes(-len(d) % 0x800)
struct.pack_into("<II", d, ents["FGDC20.TXD"][0] + 0x74, len(d), len(txd))
d += txd + bytes(-len(txd) % 0x800)
open(path, "wb").write(d)
print("patched %s: %d x %d sheet, %d mipmap levels (original kept as %s.orig)" % (path, new.size[0], new.size[1], len(images), path))
