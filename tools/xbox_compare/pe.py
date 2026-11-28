"""pe.py: read the PC executable by virtual address (path: $MFL_EXE, default MFL.exe)"""
import os,struct,sys
class PE:
    def __init__(s,p=None):
        p=p or os.environ.get("MFL_EXE","MFL.exe")
        s.d=open(p,'rb').read(); e=struct.unpack_from('<I',s.d,0x3c)[0]
        n=struct.unpack_from('<H',s.d,e+6)[0]; oh=struct.unpack_from('<H',s.d,e+20)[0]
        s.base=struct.unpack_from('<I',s.d,e+24+28)[0]; s.secs=[]
        for i in range(n):
            o=e+24+oh+i*40; nm=s.d[o:o+8].rstrip(b'\0'); vs,va,rs,ro=struct.unpack_from('<IIII',s.d,o+8); s.secs.append((nm,va,vs,ro,rs))
    def off(s,va):
        r=va-s.base
        for nm,a,vs,ro,rs in s.secs:
            if a<=r<a+max(vs,rs): return ro+r-a if r-a<rs else None
    def rd(s,va,n):
        o=s.off(va); return s.d[o:o+n] if o is not None else bytes(n)
    def u32(s,va,n=1): return struct.unpack('<%dI'%n,s.rd(va,4*n))
    def i32(s,va,n=1): return struct.unpack('<%di'%n,s.rd(va,4*n))
    def cstr(s,va): 
        b=s.rd(va,256); return b.split(b'\0')[0].decode('latin1')
