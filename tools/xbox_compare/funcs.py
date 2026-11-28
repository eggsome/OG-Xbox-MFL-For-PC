"""funcs.py: both executables as lists of functions of normalised instructions, for matching the Xbox code to the PC code.

  load(asm, lo, hi, starts)  -> {start: Func}   from objdump -d -M intel text
An instruction is (mnemonic, operands with every number >= 0x10000 replaced by A and every jump target by L); the numbers replaced
are kept (Func.refs) so matched functions can be compared constant by constant.
"""
import re, pickle, os, sys

LINE = re.compile(r"^\s*([0-9a-f]+):\t([0-9a-f ]+?)\s*\t(\S+)\s*(.*)$")
HEX = re.compile(r"0x([0-9a-f]+)")
JUMPS = {"jmp", "je", "jne", "jz", "jnz", "ja", "jae", "jb", "jbe", "jg", "jge", "jl", "jle", "jo", "jno", "js", "jns", "jp", "jnp", "jcxz", "jecxz", "loop"}
PAD = {"int3", "nop"}

class Func:
    __slots__ = ("start", "ins", "refs", "calls", "size")
    def __init__(self, start): self.start, self.ins, self.refs, self.calls, self.size = start, [], [], [], 0

def parse(path):
    out = []
    for line in open(path, errors="replace"):
        m = LINE.match(line)
        if not m: continue
        ops = m.group(4).split("#")[0].strip()
        ops = re.sub(r"\s*<[^>]*>", "", ops)
        out.append((int(m.group(1), 16), len(m.group(2).split()), m.group(3), ops))
    return out

def load(path, lo, hi, starts=()):
    cache = path + ".pkl"
    if os.path.exists(cache) and os.path.getmtime(cache) > os.path.getmtime(path):
        ins = pickle.load(open(cache, "rb"))
    else:
        ins = parse(path); pickle.dump(ins, open(cache, "wb"))
    begin = set(a for a in starts if lo <= a < hi)
    for a, n, mn, ops in ins:                               # call targets and code addresses used as values
        if mn == "call" or mn in JUMPS:
            m = re.fullmatch(r"0x([0-9a-f]+)", ops)
            if m and mn == "call": begin.add(int(m.group(1), 16))
        else:
            for h in HEX.findall(ops):
                v = int(h, 16)
                if lo <= v < hi and mn in ("push", "mov"): begin.add(v)
    prev_pad, prev_end = False, True
    for a, n, mn, ops in ins:                               # after padding that follows a ret / jmp
        if mn in PAD: prev_pad = True; continue
        if prev_pad and prev_end: begin.add(a)
        prev_pad = False; prev_end = mn in ("ret", "jmp", "retn")
    addrs = set(a for a, n, mn, ops in ins)
    begin &= addrs
    funcs, cur = {}, None
    for a, n, mn, ops in ins:
        if a in begin:
            cur = Func(a); funcs[a] = cur
        if cur is None or mn in PAD: continue
        cur.size = a + n - cur.start
        if mn == "call" or mn in JUMPS:
            m = re.fullmatch(r"0x([0-9a-f]+)", ops)
            if m:
                t = int(m.group(1), 16)
                if mn == "call": cur.calls.append(t); cur.ins.append("call A"); cur.refs.append((len(cur.ins) - 1, t))
                elif t in begin and t != cur.start and mn == "jmp": cur.calls.append(t); cur.ins.append("jmp A"); cur.refs.append((len(cur.ins) - 1, t))
                else: cur.ins.append(mn + " L")
                continue
        def rep(m, cur=cur):
            v = int(m.group(1), 16)
            if v >= 0x10000 and v < 0xfff00000:
                cur.refs.append((len(cur.ins), v)); return "A"
            return m.group(0)
        cur.ins.append(mn + " " + HEX.sub(rep, ops))
    return funcs
