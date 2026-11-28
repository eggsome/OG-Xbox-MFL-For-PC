#!/usr/bin/env python3
"""xbox_log.py <qmp socket>: a running record of the Xbox game's cars, read from xemu's guest memory through QMP (memsave).

Lines as the PC game writes them with --debug, so the two can be compared:
  F <sample> t=<ms> phase=<race phase>
  C<n> act= mode= pos= up= fwd= vel= spd= wic= wd=<the four wheels' contact distances> wc=<their in_contact>
Written to xbox-debug-A.txt / xbox-debug-B.txt beside this script, two minutes each in turn.  A sample is taken about every 8 ms
and written when anything in it changed, so there is about one per game frame.

Addresses of default.xbe (Mashed Fully Loaded, PAL/NTSC image used here): the car records start at 0x3d8fb0, 0xd10 bytes each;
the race phase is the dword at 0x46a090.  Offsets in a car record (the PC record's, shifted): +4 active, +0x930 two matrices,
+0x9b0 current matrix, +0x9b8 velocity, +0x9e8 wheels in contact, +0x9ec speed, +0x9f8 mode; wheel k: +0x194 + k * 0xc4 contact
distance, +0x198 + k * 0xc4 in contact.
"""
import json, os, socket, struct, sys, time
CARS, CAR_SIZE, NCARS, PHASE = 0x3d8fb0, 0xd10, 4, 0x46a090
here = os.path.dirname(os.path.abspath(__file__))
tmp = "/dev/shm/xemu-mem-%d.bin" % os.getpid()

def connect(path):
    for k in range(600):
        try:
            s = socket.socket(socket.AF_UNIX); s.connect(path); return s
        except OSError:
            time.sleep(0.1)
    sys.exit("no QMP socket")

class Qmp:
    def __init__(self, path):
        self.s = connect(path); self.f = self.s.makefile("rw")
        self.f.readline(); self.cmd("qmp_capabilities")
    def cmd(self, name, **args):
        self.f.write(json.dumps({"execute": name, "arguments": args} if args else {"execute": name}) + "\n"); self.f.flush()
        while True:
            line = self.f.readline()
            if not line: raise EOFError
            r = json.loads(line)
            if "return" in r or "error" in r: return r
    def read(self, addr, size):
        r = self.cmd("memsave", val=addr, size=size, filename=tmp)
        if "error" in r: return None
        with open(tmp, "rb") as f: return f.read()

def main():
    q = Qmp(sys.argv[1]); start = time.time(); which, out, file_start, n, last = 0, None, 0, 0, None
    try:
        while True:
            time.sleep(0.008)
            cars = q.read(CARS, CAR_SIZE * NCARS); ph = q.read(PHASE, 4)
            if not cars or not ph or len(cars) < CAR_SIZE * NCARS: continue
            if cars == last: continue
            last = cars
            ms = int((time.time() - start) * 1000)
            if out is None or ms - file_start >= 120000:
                if out: out.close(); which ^= 1
                out = open(os.path.join(here, "xbox-debug-%s.txt" % "AB"[which]), "w"); file_start = ms
                out.write("# xbox debug log, file started at t=%d ms, sample %d\n" % (ms, n))
            n += 1
            out.write("F %d t=%d phase=%d\n" % (n, ms, struct.unpack("<i", ph)[0]))
            for c in range(NCARS):
                r = cars[c * CAR_SIZE:(c + 1) * CAR_SIZE]
                active, = struct.unpack_from("<i", r, 4)
                if not active: continue
                cur, = struct.unpack_from("<I", r, 0x9b0)
                m = struct.unpack_from("<16f", r, 0x930 + (cur & 1) * 64)
                vel = struct.unpack_from("<3f", r, 0x9b8); wic, spd = struct.unpack_from("<2f", r, 0x9e8); mode, = struct.unpack_from("<i", r, 0x9f8)
                wd = [struct.unpack_from("<f", r, 0x194 + k * 0xc4)[0] for k in range(4)]; wc = [struct.unpack_from("<i", r, 0x198 + k * 0xc4)[0] for k in range(4)]
                out.write("C%d act=%d mode=%d pos=%.3f,%.3f,%.3f up=%.4f,%.4f,%.4f fwd=%.4f,%.4f,%.4f vel=%.3f,%.3f,%.3f spd=%.2f wic=%.0f wd=%.3f,%.3f,%.3f,%.3f wc=%d%d%d%d\n"
                          % (c, active, mode, m[12], m[13], m[14], m[4], m[5], m[6], m[8], m[9], m[10], vel[0], vel[1], vel[2], spd, wic, *wd, *wc))
            if n % 60 == 0: out.flush()
    except (EOFError, BrokenPipeError, ConnectionResetError, json.JSONDecodeError):
        pass
    finally:
        if out: out.close()
        try: os.remove(tmp)
        except OSError: pass

if __name__ == "__main__":
    main()
