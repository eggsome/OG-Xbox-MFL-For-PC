"""xbox_align.py (run by gdb, see run-with-gdb.sh): the alignment decision of the Xbox game's car_wheel_contact_update, read at the
instruction itself through xemu's gdb port.

Two hardware breakpoints in default.xbe:
  0x14d217  the cosine of the angle between the ground normal and the car's up axis is about to be compared with 0.9999
            edi = car record, [esp+0x40..0x48] = normal, [edi+0x9d0..] = up, [esp+0x10] = cosine, [esp+0x74] = wheels in contact before,
            [ebp+8] = limit flag, [esp+0x20] = the matrix being corrected (position at +0x30)
  0x14d3da  the car is about to be turned; [esp+0x10] = the angle in degrees
Lines as the PC game writes them with --debug ("align car=..."), into xbox-align.txt beside this script; after LINES lines the breakpoints
are removed and the game runs on at full speed.
"""
import gdb, os, struct
LINES = 12000
here = os.path.dirname(os.path.abspath(__file__))
out = open(os.path.join(here, "xbox-align.txt"), "w")
count = [0]
inf = None

def mem(addr, fmt):
    return struct.unpack("<" + fmt, bytes(gdb.selected_inferior().read_memory(addr & 0xffffffff, struct.calcsize("<" + fmt))))
def reg(name):
    return int(gdb.parse_and_eval("$" + name)) & 0xffffffff

def finish():
    for b in gdb.breakpoints() or []: b.delete()
    out.flush()

class Decision(gdb.Breakpoint):
    def stop(self):
        try:
            edi, esp, ebp = reg("edi"), reg("esp"), reg("ebp")
            if not (0x3d8fb0 <= edi < 0x3d8fb0 + 16 * 0xd10): return False
            n = mem(esp + 0x40, "3f"); up = mem(edi + 0x9d0, "3f"); cos, = mem(esp + 0x10, "f"); before, = mem(esp + 0x74, "i"); limit, = mem(ebp + 8, "i")
            m, = mem(esp + 0x20, "I"); pos = mem(m + 0x30, "3f"); av = mem(edi + 0x9c4, "3f")
            wd = [mem(edi + 0x194 + k * 0xc4, "f")[0] for k in range(4)]; wc = [mem(edi + 0x198 + k * 0xc4, "i")[0] for k in range(4)]
            out.write("align car=%d limit=%d before=%d n=%.6f,%.6f,%.6f up=%.6f,%.6f,%.6f cos=%.8f pos=%.4f,%.4f,%.4f wd=%.5f,%.5f,%.5f,%.5f wc=%d%d%d%d av=%.5f,%.5f,%.5f\n"
                      % ((edi - 0x3d8fb0) // 0xd10, limit, before, *n, *up, cos, *pos, *wd, *wc, *av))
        except Exception as e:
            out.write("# error %r\n" % (e,))
        count[0] += 1
        if count[0] % 200 == 0: out.flush()
        if count[0] >= LINES: gdb.post_event(finish)
        return False

class Turned(gdb.Breakpoint):
    def stop(self):
        try:
            edi, esp = reg("edi"), reg("esp")
            out.write("align car=%d turned by %.5f\n" % ((edi - 0x3d8fb0) // 0xd10, mem(esp + 0x10, "f")[0]))
        except Exception as e:
            out.write("# error %r\n" % (e,))
        return False

gdb.execute("set pagination off"); gdb.execute("set confirm off"); gdb.execute("set architecture i386")
gdb.execute("target remote localhost:1234")
Decision("*0x14d217", type=gdb.BP_HARDWARE_BREAKPOINT)
Turned("*0x14d3da", type=gdb.BP_HARDWARE_BREAKPOINT)
try:
    gdb.execute("continue")
except gdb.error:
    pass
out.close()
