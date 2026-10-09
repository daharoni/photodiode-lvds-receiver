import numpy as np
from tl2d import cg_energy, ETA, MIL
class G:
    def __init__(s, below, above=None, t=0.0406, N=16, wtot=2.4, topair=0.7):
        s.below=below; s.above=above; s.t=t
        s.y0=sum(b[0] for b in below)
        s.h=s.y0/N
        s.ny=int(round((s.y0+(sum(a[0] for a in above) if above else topair))/s.h))+1
        s.nx=int(round(wtot/s.h))+1
        s.Nt=max(1,int(round(t/s.h)))
        s.N=N
    def build(s, specs):
        """specs: list of (i_left, ncells_w, volt). returns E, fixed, V"""
        h=s.h; nx,ny=s.nx,s.ny
        xc=(np.arange(nx-1)+0.5)*h; yc=(np.arange(ny-1)+0.5)*h
        X,Y=np.meshgrid(xc,yc,indexing='ij')
        E=np.ones_like(X)
        yb=0
        for thk,er in s.below:
            E[(Y>=yb)&(Y<yb+thk-1e-12)]=er; yb+=thk
        if s.above:
            ya=s.y0
            for thk,er in s.above:
                E[(Y>=ya-1e-12)&(Y<ya+thk-1e-12)]=er; ya+=thk
        fixed=np.zeros((nx,ny),bool); V=np.zeros((nx,ny))
        fixed[:,0]=True; fixed[:,-1]=True
        xn=np.arange(nx)*h; yn=np.arange(ny)*h
        XN,YN=np.meshgrid(xn,yn,indexing='ij')
        t=s.Nt*h
        j0=s.N
        for il,nw,v in specs:
            w=nw*h; xl=il*h; xr=xl+w
            frac=np.clip((YN-s.y0)/t,0,1)
            shrink=frac*0.7*MIL
            m=(YN>=s.y0-1e-9)&(YN<=s.y0+t+1e-9)&(XN>=xl+shrink-1e-9)&(XN<=xr-shrink+1e-9)
            fixed|=m; V[m]=v
            if not s.above:
                sm=3.8
                # mask: within 0.6 mil above/side of conductor outline
                halfc=(xl+xr)/2; hw=w/2-shrink[0:1,:].mean()*0  # coarse
                for yy in range(ny-1):
                    pass
        if not s.above:
            sm=3.8
            m=(Y>=s.y0)&(Y<s.y0+1.2*MIL); E[m]=sm
            for il,nw,v in specs:
                w=nw*h; xl=il*h; xr=xl+w
                frac=np.clip((Y-s.y0)/t,0,1); shrink=frac*0.7*MIL
                m=(X>=xl+shrink-0.6*MIL)&(X<=xr-shrink+0.6*MIL)&(Y>=s.y0)&(Y<s.y0+t+0.6*MIL)
                E[m]=sm
        return E,fixed,V
    def se(s,nw):
        il=(s.nx-1)//2-nw//2
        E,f,V=s.build([(il,nw,1.0)])
        S=cg_energy(E,f,V); S0=cg_energy(np.ones_like(E),f,V)
        return ETA/np.sqrt(S*S0)
    def diff(s,nw,ng):
        c=(s.nx-1)//2
        il=c-ng//2-nw
        E,f,V=s.build([(il,nw,1.0),(il+nw+ng,nw,-1.0)])
        S=cg_energy(E,f,V); S0=cg_energy(np.ones_like(E),f,V)
        return 2*ETA/np.sqrt((S/2)*(S0/2))
def interp_w(g,fn,target,lo=4,hi=60):
    zs={}
    def z(n):
        if n not in zs: zs[n]=fn(n)
        return zs[n]
    a,b=lo,hi
    while b-a>1:
        m=(a+b)//2
        if z(m)>target: a=m
        else: b=m
    za,zb=z(a),z(b)
    f=(za-target)/(za-zb)
    return (a+f*(b-a))*g.h, a,b
