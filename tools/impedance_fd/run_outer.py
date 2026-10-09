from tl2 import *
import sys
cases=[("4L JLC04161H-7628 L1/L4",0.2104,4.4),("4L JLC04161H-3313 L1/L4",0.0994,4.1),("4L JLC04161H-1080 L1/L4",0.0764,3.91),
       ("6L JLC06161H-3313 L1/L6",0.0994,4.1),("6L JLC06161H-1080 L1/L6",0.0764,3.91),("6L JLC06161H-7628 L1/L6",0.2104,4.4),("6L JLC06161H-2116A L1/L6",0.1164,4.16)]
for name,th,er in cases:
    g=G([(th,er)],N=16)
    h=g.h
    w50,a,b=interp_w(g,g.se,50.0,4,80)
    out=[f"{name}: h={th} er={er}  50ohm SE w={w50:.3f} mm"]
    for ng_mm in (0.10,0.15,0.20):
        ng=round(ng_mm/h)
        for tz in (90.0,100.0):
            w,a,b=interp_w(g,lambda n:g.diff(n,ng),tz,4,80)
            out.append(f"  Zd={tz:.0f} gap={ng*h:.3f} w={w:.3f}")
    print("\n".join(out)); sys.stdout.flush()
