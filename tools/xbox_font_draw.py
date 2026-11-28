#!/usr/bin/env python3
"""tools/xbox_font_draw.py <Font36.piz> <FRADMCN.TTF> <sheet.png> [scale=8]: draws the sheet tools/xbox_font.py installs.

The Xbox menu font of Font36.piz (XBOX/XBOXFGDC20.TXD/.RWF) is Franklin Gothic Demi Cond 20 pt on a 512 x 256 sheet, with pictures of
the A/B/X/Y/START buttons and of the controller.  This draws the same layout <scale> times as large: the letters from the TrueType
font (not part of the repository; it comes with Microsoft Office), each fitted to its place on the old sheet; the four coloured
buttons, START and the two controller pictures redrawn after the old ones.  assets/xbox_font/fgdc20_8x.png is its output at scale 8.
The archive is only read.  Needs numpy, Pillow and Arial Bold / Bold Italic for the pictures.
"""
import os, struct, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

path, ttf, out = sys.argv[1], sys.argv[2], sys.argv[3]
K = int(sys.argv[4]) if len(sys.argv) > 4 else 8
W, H = 512, 256
POINT_PX = 20 * 96 / 72.0                                  # "FGDC20": 20 pt at 96 dpi; the fit below agrees (26.5 - 27)
BUTTONS = {0x80: "A", 0x81: "Y", 0x82: "X", 0x83: "B"}    # characters the Xbox .RWF points at the pictures
PADS = {0x87: False, 0x8f: True}                           # 0x84 is START; these the white and the black controller
LETTER_FONT = "/usr/share/fonts/truetype/msttcorefonts/arialbi.ttf"
WORD_FONT = "/usr/share/fonts/truetype/msttcorefonts/arialbd.ttf"

d = open(path + ".orig" if os.path.exists(path + ".orig") else path, "rb").read()      # the original, if xbox_font.py kept one
assert d[:4] == b"PIZ\0"
ents = {}
for k in range(struct.unpack_from("<I", d, 8)[0]):        # directory at 0x800: name[0x74], offset, size, (unknown)
    e = 0x800 + k * 0x80
    ents[d[e:e + 0x74].split(b"\0")[0].decode().upper()] = (e,) + struct.unpack_from("<II", d, e + 0x74)
get = lambda n: d[ents[n][1]:ents[n][1] + ents[n][2]]

# --- the Xbox sheet: 8 bit, BGRA palette, swizzled pixels ---------------------------------------------------------------------
x = get("XBOX/XBOXFGDC20.TXD")
o = 0x28 + 12 + 8 + 64
assert struct.unpack_from("<HHB", x, o + 8) == (W, H, 8), "unexpected Xbox font texture"
o += 20
palx = np.frombuffer(x[o:o + 1024], np.uint8).reshape(256, 4)[:, [2, 1, 0, 3]]
sw = np.frombuffer(x[o + 1024:o + 1024 + W * H], np.uint8)
xs, ys = np.meshgrid(np.arange(W), np.arange(H))
idx = np.zeros((H, W), np.int64)
for b in range(8):                                         # x and y bits interleave while both remain, then the rest of x
    idx |= ((xs >> b) & 1) << (2 * b) | ((ys >> b) & 1) << (2 * b + 1)
idx |= ((xs >> 8) & 1) << 16
old = palx[sw[idx]]                                        # H x W x RGBA
old_alpha = old[..., 3] / 255.0

# --- the Xbox .RWF: 256 character -> glyph numbers (0x80.. first), then 21 byte glyph records -----------------------------------
rwf = get("XBOX/XBOXFGDC20.RWF")
cmap = struct.unpack_from("<256H", rwf, 0x30)
cells = {}                                                 # character -> x0, y0, x1, y1 in the old sheet's pixels
for i, g in enumerate(cmap):
    if g != 0xffff:
        u0, v0, u1, v1 = struct.unpack_from("<4f", rwf, 0x230 + g * 21)
        cells[(i + 128) % 256] = (int(u0 * W), int(v0 * H), int(u1 * W), int(v1 * H))

def text_of(c):
    try:
        return bytes([c]).decode("cp1252")
    except UnicodeDecodeError:
        return chr(c)

def drawn(c, font, ss, dx, by):
    """character c in its cell at ss pixels per old pixel, pen at dx, baseline at by (both in ss pixels)"""
    x0, y0, x1, y1 = cells[c]
    im = Image.new("L", ((x1 - x0) * ss, (y1 - y0) * ss))
    ImageDraw.Draw(im).text((dx, by), text_of(c), font=font, fill=255, anchor="ls")
    return im

def misfit(c, font, ss, dx, by):
    x0, y0, x1, y1 = cells[c]
    a = np.asarray(drawn(c, font, ss, dx, by), float).reshape(y1 - y0, ss, x1 - x0, ss).mean((1, 3)) / 255
    return ((a - old_alpha[y0:y1, x0:x1]) ** 2).sum()

# where the old sheet has its baseline, and each letter its pen position: the closest match to the old pixels
FIT = 4
fit_font = ImageFont.truetype(ttf, POINT_PX * FIT)
probe = [ord(ch) for ch in "ABDEGHKMNRSTXabdeghkmnpsty0235689"]
baseline = min(range(24 * FIT, 28 * FIT), key=lambda by: sum(min(misfit(c, fit_font, FIT, dx, by) for dx in range(-4, 5, 2)) for c in probe))
print("baseline %.2f px below the cell top" % (baseline / FIT))

# --- the new sheet ------------------------------------------------------------------------------------------------------------
SS = 4                                                     # letters are drawn SS times larger still, then averaged down
new = np.zeros((H * K, W * K, 4), np.uint8)
new[..., :3] = 255                                         # white under the transparent parts: no dark fringe when filtered
font = ImageFont.truetype(ttf, POINT_PX * K * SS)

def canvas(c):
    """a blank picture of character c's cell and the pen for it, u pixels per old pixel"""
    x0, y0, x1, y1 = cells[c]
    im = Image.new("RGBA", ((x1 - x0) * K * SS, (y1 - y0) * K * SS), (255, 255, 255, 0))
    return im, ImageDraw.Draw(im), K * SS

def shrunk(im):
    return np.asarray(im.convert("RGBa").resize((im.size[0] // SS, im.size[1] // SS), Image.BOX).convert("RGBA"))

def disc(dr, u, cx, cy, r, fill=None, outline=None, width=0.0):
    dr.ellipse(((cx - r) * u, (cy - r) * u, (cx + r) * u, (cy + r) * u), fill=fill, outline=outline, width=max(1, int(width * u)))

def smooth(points, steps=24):
    """a closed curve through the points (Catmull-Rom)"""
    p = np.array(points, float)
    t = np.linspace(0, 1, steps, endpoint=False)[:, None]
    out = []
    for i in range(len(p)):
        a, b, c, d = p[i - 1], p[i], p[(i + 1) % len(p)], p[(i + 2) % len(p)]
        out.append(0.5 * (2 * b + (c - a) * t + (2 * a - 5 * b + 4 * c - d) * t ** 2 + (3 * b - a - 3 * c + d) * t ** 3))
    return np.concatenate(out)

PAD_MIDDLE = 27.3                                          # the controller pictures, in the old sheet's pixels from the cell corner
PAD_LEFT = [(27.3, 4.7), (22.5, 4.3), (18.0, 3.3), (13.0, 3.5), (9.6, 5.6), (7.0, 11.0), (5.3, 18.0), (4.5, 26.0), (4.7, 33.0),
            (6.5, 37.2), (9.5, 37.9), (12.4, 36.4), (14.5, 32.5), (17.0, 29.0), (21.0, 27.9)]

def pad(c, black):
    im, dr, u = canvas(c)
    body, rim, line, mark = ((0, 0, 0), (176, 176, 176), (96, 96, 96), (255, 255, 255)) if black else \
                            ((255, 255, 255), (40, 40, 40), (168, 168, 168), (0, 0, 0))
    grey = lambda v: (v, v, v, 255)
    shape = PAD_LEFT + [(PAD_MIDDLE, 27.9)] + [(2 * PAD_MIDDLE - x, y) for x, y in reversed(PAD_LEFT[1:])]
    curve = [(x * u, y * u) for x, y in smooth(shape)]
    dr.polygon(curve, fill=body + (255,))
    dr.line(curve + curve[:2], fill=rim + (255,), width=int(0.9 * u), joint="curve")
    for cx, cy in ((14.5, 13.5), (33.6, 21.2)):            # the two sticks
        disc(dr, u, cx, cy, 4.2, outline=line + (255,), width=0.7)
        disc(dr, u, cx, cy, 2.6, fill=grey(52 if black else 226), outline=line + (255,), width=0.5)
    disc(dr, u, 20.6, 21.2, 4.4, outline=line + (255,), width=0.8)                      # the direction pad
    disc(dr, u, 20.6, 21.2, 3.0, fill=grey(24 if black else 240), outline=line + (255,), width=0.4)
    for dx, dy in ((0, -3.2), (-3.3, 0), (3.3, 0), (0, 3.2)):                             # the four buttons
        disc(dr, u, 40.5 + dx, 13.5 + dy, 1.7, fill=grey(120 if black else 150), outline=line + (255,), width=0.3)
    disc(dr, u, 41.2, 22.6, 1.6, fill=grey(60 if black else 215), outline=line + (255,), width=0.3)
    disc(dr, u, PAD_MIDDLE, 13.0, 4.1, fill=mark + (255,))                               # the jewel
    disc(dr, u, PAD_MIDDLE, 13.0, 2.9, outline=grey(150 if black else 70), width=0.4)
    for cx, cy in ((10.0, 18.3), (12.7, 21.0), (44.2, 20.0)):
        disc(dr, u, cx, cy, 1.1, fill=mark + (255,))
    return shrunk(im)

def start(c):
    im, dr, u = canvas(c)
    w, h = im.size
    yy, xx = np.mgrid[0:h, 0:w] / float(u)
    cx, cy, r = 15.5, 7.6, 7.3                              # the dark round button: lit from the upper left
    inside = (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r
    glow = np.clip(1 - np.hypot(xx - (cx - 2.4), yy - (cy - 2.8)) / (r * 1.25), 0, 1)
    ball = np.zeros((h, w, 4), np.uint8)
    ball[..., :3] = (38 + 96 * glow ** 1.6)[..., None]
    ball[..., 3] = inside * 255
    im.alpha_composite(Image.fromarray(ball, "RGBA"))
    disc(dr, u, cx, cy, r, outline=(20, 20, 20, 255), width=0.5)
    size = 10.0 * u                                        # the word across the cell's width
    word = ImageFont.truetype(WORD_FONT, int(size))
    left, top, right, bottom = word.getbbox("START", stroke_width=int(0.8 * u))
    word = ImageFont.truetype(WORD_FONT, int(size * (w - 0.6 * u) / (right - left)))
    dr.text((w / 2, h - 0.2 * u), "START", font=word, fill=(255, 255, 255, 255), anchor="mb",
            stroke_width=int(0.8 * u), stroke_fill=(24, 24, 24, 255))
    return shrunk(im)

def button(c, letter):
    x0, y0, x1, y1 = cells[c]
    w, h = (x1 - x0) * K * SS, (y1 - y0) * K * SS
    part = old[y0:y1, x0:x1].reshape(-1, 4).astype(int)
    vivid = part[(part[:, 3] > 250) & (part[:, :3].max(1) - part[:, :3].min(1) > 120)]
    fill = tuple(int(v) for v in np.median(vivid, axis=0)[:3])
    # the old picture: an ellipse one pixel inside the cell, dark rim, black slanted letter
    cols = np.where((old_alpha[y0:y1, x0:x1] > 0.5).any(0))[0]
    rows = np.where((old_alpha[y0:y1, x0:x1] > 0.5).any(1))[0]
    u = K * SS
    box = (cols[0] * u, rows[0] * u, (cols[-1] + 1) * u - 1, (rows[-1] + 1) * u - 1)
    im = Image.new("RGBA", (w, h), fill + (0,))
    dr = ImageDraw.Draw(im)
    dr.ellipse(box, fill=fill + (255,), outline=(36, 36, 36, 255), width=int(1.3 * u))
    lf = ImageFont.truetype(LETTER_FONT, int(15.5 * u))
    dr.text(((box[0] + box[2]) / 2, (box[1] + box[3]) / 2), letter, font=lf, fill=(0, 0, 0, 255), anchor="mm")
    return np.asarray(im.convert("RGBa").resize((w // SS, h // SS), Image.BOX).convert("RGBA"))

for c, (x0, y0, x1, y1) in sorted(cells.items()):
    where = new[y0 * K:y1 * K, x0 * K:x1 * K]
    if c in BUTTONS:
        where[:] = button(c, BUTTONS[c])
    elif c == 0x84:
        where[:] = start(c)
    elif c in PADS:
        where[:] = pad(c, PADS[c])
    elif old_alpha[y0:y1, x0:x1].any():
        dx = min(range(-6, 7), key=lambda v: misfit(c, fit_font, FIT, v, baseline))
        big = drawn(c, font, K * SS, dx * K * SS // FIT, baseline * K * SS // FIT)
        where[..., 3] = np.asarray(big.resize(((x1 - x0) * K, (y1 - y0) * K), Image.BOX))

Image.fromarray(new, "RGBA").save(out, optimize=True)
print("%s: %d x %d" % (out, W * K, H * K))
