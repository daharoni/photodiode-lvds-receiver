import numpy as np
MIL=0.0254
ETA=376.730313
H=0.00635

class Geo:
    def __init__(s, below, above=None, outer=True, t=0.0406, wtot=2.0, topair=0.6, h=H):
        # below: list (thk, er) from plane up to trace base. above: inner: list (thk,er) to upper plane; outer: None
        s.h=h; s.below=below; s.above=above; s.outer=outer; s.t=t
        s.y0=sum(b[0] for b in below)
        s.ytop = s.y0 + (sum(a[0] for a in above) if above else topair)
        s.nx=int(round(wtot/h))+1; s.ny=int(round(s.ytop/h))+1
        s.W=wtot
    def eps(s, tr):
        """tr: list of (xc, wbase). returns cell eps array (nx-1,ny-1), and vacuum"""
        h=s.h; nx,ny=s.nx,s.ny
        xc=(np.arange(nx-1)+0.5)*h; yc=(np.arange(ny-1)+0.5)*h
        X,Y=np.meshgrid(xc,yc,indexing='ij')
        E=np.ones_like(X)
        # below
        yb=0
        for thk,er in s.below:
            m=(Y>=yb)&(Y<yb+thk); E[m]=er; yb+=thk
        if s.above:
            ya=s.y0
            for thk,er in s.above:
                m=(Y>=ya)&(Y<ya+thk); E[m]=er; ya+=thk
        else:
            sm=3.8
            m=(Y>=s.y0)&(Y<s.y0+1.2*MIL); E[m]=sm
            for xcn,w in tr:
                # mask over trace: within 0.6 mil of trapezoid
                wt=w-0.7*MIL
                frac=np.clip((Y-s.y0)/s.t,0,1)
                half=(w/2)-(frac*(w-wt)/2)
                m=(np.abs(X-xcn)<=half+0.6*MIL)&(Y>=s.y0)&(Y<s.y0+s.t+0.6*MIL)
                E[m]=sm
        return E
    def conductor(s,tr,volts):
        h=s.h; nx,ny=s.nx,s.ny
        x=np.arange(nx)*h; y=np.arange(ny)*h
        X,Y=np.meshgrid(x,y,indexing='ij')
        fixed=np.zeros((nx,ny),bool); V=np.zeros((nx,ny))
        fixed[:,0]=True; fixed[:,-1]=True
        for (xcn,w),v in zip(tr,volts):
            wt=w-0.7*MIL
            frac=(Y-s.y0)/s.t
            half=(w/2)-(np.clip(frac,0,1)*(w-wt)/2)
            m=(frac>=-1e-9)&(frac<=1+1e-9)&(np.abs(X-xcn)<=half+1e-9)
            fixed|=m; V[m]=v
        return fixed,V

def cg_energy(E,fixed,V):
    nx,ny=fixed.shape
    # conductances
    gx=np.zeros((nx-1,ny)); gy=np.zeros((nx,ny-1))
    Ep=np.pad(E,((0,0),(1,1)),mode='edge')   # (nx-1, ny+1)
    gx=(Ep[:,:-1]+Ep[:,1:])/2
    Eq=np.pad(E,((1,1),(0,0)),mode='edge')   # (nx+1, ny-1)
    gy=(Eq[:-1,:]+Eq[1:,:])/2
    diag=np.zeros((nx,ny))
    diag[:-1,:]+=gx; diag[1:,:]+=gx; diag[:,:-1]+=gy; diag[:,1:]+=gy
    def L(p):
        o=diag*p
        o[:-1,:]-=gx*p[1:,:]; o[1:,:]-=gx*p[:-1,:]
        o[:,:-1]-=gy*p[:,1:]; o[:,1:]-=gy*p[:,:-1]
        return o
    free=~fixed
    p=np.where(fixed,V,0.0)
    r=-L(p); r[fixed]=0
    d=np.where(free,diag,1.0)
    z=r/d; q=z.copy(); rz=(r*z).sum()
    for it in range(20000):
        Aq=L(q); Aq[fixed]=0
        a=rz/(q*Aq).sum()
        p+= a*np.where(free,q,0); r-=a*Aq
        if np.sqrt((r*r).sum())<1e-9*np.sqrt(rz+1e-30)+1e-12: break
        z=r/d; rzn=(r*z).sum(); q=z+(rzn/rz)*q; rz=rzn
    dx=p[1:,:]-p[:-1,:]; dy=p[:,1:]-p[:,:-1]
    return (gx*dx*dx).sum()+(gy*dy*dy).sum()

def zse(g,w,xc=None):
    xc=g.W/2 if xc is None else xc
    tr=[(xc,w)]
    f,V=g.conductor(tr,[1.0])
    S=cg_energy(g.eps(tr),f,V); S0=cg_energy(np.ones((g.nx-1,g.ny-1)),f,V)
    return ETA/np.sqrt(S*S0)

def zdiff(g,w,gap):
    tr=[(g.W/2-(gap+w)/2,w),(g.W/2+(gap+w)/2,w)]
    f,V=g.conductor(tr,[1.0,-1.0])
    E=g.eps(tr); S=cg_energy(E,f,V); S0=cg_energy(np.ones_like(E),f,V)
    zo=ETA/np.sqrt((S/2)*(S0/2))*0.5*0+ETA/np.sqrt(S*S0)*2/1  # S=2Co -> Co=S/2; Zo=ETA/sqrt(Co Co0)=2ETA/sqrt(S S0)
    return 2*zo/2*1  # placeholder replaced below

def zdiff2(g,w,gap):
    tr=[(g.W/2-(gap+w)/2,w),(g.W/2+(gap+w)/2,w)]
    f,V=g.conductor(tr,[1.0,-1.0])
    E=g.eps(tr); S=cg_energy(E,f,V); S0=cg_energy(np.ones_like(E),f,V)
    Zodd=ETA/np.sqrt((S/2)*(S0/2))
    return 2*Zodd

def solve_w(fn,target,lo,hi,tol=0.1):
    flo=fn(lo)-target; fhi=fn(hi)-target
    for _ in range(30):
        mid=(lo+hi)/2; fm=fn(mid)-target
        if abs(fm)<tol: return mid,fm+target
        if (fm>0)==(flo>0): lo,flo=mid,fm
        else: hi,fhi=mid,fm
    return mid,fm+target
