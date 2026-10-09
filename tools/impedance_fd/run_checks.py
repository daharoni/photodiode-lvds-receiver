from tl2 import *
import sys
g=G([(0.0994,4.1)],N=16); h=g.h
def zd(w,gap): return g.diff(round(w/h),round(gap/h)), round(w/h)*h, round(gap/h)*h
for w,gp in ((0.145,0.15),(0.145*0.8,0.15),(0.145*1.2,0.15),(0.11,0.15),(0.11*0.8,0.15),(0.11*1.2,0.15),(0.16,0.20),(0.125,0.20)):
    print("L1 3313",w,gp,zd(w,gp))
for w in (0.155,0.155*0.8,0.155*1.2): print("SE",w,g.se(round(w/h)),round(w/h)*h)
# L3 inner, planes L2 (0.55 below, er 4.6) and L4 (0.1088 above, er 4.16), t=0.0152
g3=G([(0.55,4.6)],above=[(0.1088,4.16)],t=0.0152,N=64,wtot=2.4)
print("L3 h",g3.h)
w50,a,b=interp_w(g3,g3.se,50.0,3,60); print("L3 SE50",w50)
for gp in (0.15,0.20):
    ng=round(gp/g3.h)
    for tz in (90.,100.):
        w,a,b=interp_w(g3,lambda n:g3.diff(n,ng),tz,3,60); print("L3",tz,gp,ng*g3.h,w)
