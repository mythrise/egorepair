"""V5 product-space bounded reference repair. No robot feasibility claims."""
from dataclasses import dataclass
import numpy as np
from scipy.interpolate import BSpline, PchipInterpolator
from scipy.integrate import quad
from scipy.optimize import brentq
from scipy.spatial.transform import Rotation


def _finite_scalar(value, name, nonnegative=False):
    a=np.asarray(value)
    if a.shape!=() or a.dtype.kind not in "iuf" or not np.isfinite(a) or (nonnegative and a<0):
        raise ValueError("invalid "+name)
    return float(a)


def smoothstep(u):
    u=np.clip(np.asarray(u,dtype=float),0,1)
    return u**3*(10+u*(-15+6*u))


def c2_envelope(t, base, restrictions=(), protected=(), transition=.15, endpoints=None):
    """Intersection by product, never non-C2 pointwise min.

    restrictions: (start,end,cap); protected: (start,end) with zero cap.
    Endpoint times must be true episode bounds, never computing-window bounds.
    """
    base=_finite_scalar(base,"base",True);transition=_finite_scalar(transition,"transition",True)
    t=np.asarray(t,dtype=float)
    if base<0 or transition<=0 or not np.isfinite(t).all(): raise ValueError('invalid envelope')
    out=np.full(t.shape,float(base))
    for a,b,cap in list(restrictions)+[(a,b,0.) for a,b in protected]:
        a=_finite_scalar(a,"interval start");b=_finite_scalar(b,"interval end");cap=_finite_scalar(cap,"cap",True)
        if a>b or not 0<=cap<=base: raise ValueError('invalid restrictive interval')
        h=smoothstep((t-a+transition)/transition)*smoothstep((b+transition-t)/transition)
        if base: out*=1-(1-cap/base)*h
    if endpoints is not None:
        a,b=endpoints
        a=_finite_scalar(a,"episode start");b=_finite_scalar(b,"episode end")
        if a>=b: raise ValueError('invalid episode')
        out*=smoothstep((t-a)/transition)*smoothstep((b-t)/transition)
    return out


def project_coefficients(z, edit_mask):
    z=np.asarray(z,dtype=float); mask=np.asarray(edit_mask)
    if z.shape[-2:]!=(32,15) or mask.shape!=z.shape or mask.dtype!=bool: raise ValueError('32x15 boolean mask required')
    if not np.isfinite(z[mask]).all(): raise ValueError('nonfinite editable coefficient')
    out=np.where(mask,z,0.)
    for start in (0,3,7,10):
        v=out[...,start:start+3]; out[...,start:start+3]=v/np.maximum(1,np.linalg.norm(v,axis=-1,keepdims=True))
    out[...,6]=np.clip(out[...,6],-1,1); out[...,13]=np.clip(out[...,13],-1,1)
    out[...,14]=np.clip(out[...,14],0,np.log(3))
    return out


def spline_basis(t, bounds, derivative=0):
    a,b=bounds; t=np.asarray(t,float)
    if a>=b or np.any(t<a) or np.any(t>b): raise ValueError('outside spline episode')
    knots=np.r_[np.repeat(a,4),np.linspace(a,b,30)[1:-1],np.repeat(b,4)]
    return BSpline(knots,np.eye(32),3)(t,nu=derivative)


@dataclass
class DecodedReference:
    position: np.ndarray
    rotation: np.ndarray
    width: np.ndarray
    effective_coefficients: np.ndarray
    raw_coefficients: np.ndarray
    pose_mask: np.ndarray
    width_mask: np.ndarray
    frame_qualification: np.ndarray
    status: str='REFERENCE_ONLY_M5_NOT_RUN'


def decode_reference(t,z,position,rotation,width,F,D,beta_rotation,beta_width,edit_mask,
                     pose_mask,width_mask,width_limits,episode_bounds=None,frame_mask=None):
    """Inputs all reference original baseline; missing components stay NaN.

    pose_mask [N,2,2] means separately position and orientation. F [N,2,3,3]
    columns are world basis; D [N,2,3] are per-direction metres.
    """
    t=np.asarray(t,float); n=len(t); z=np.asarray(z,float)
    p=np.asarray(position,float); R=np.asarray(rotation,float); w=np.asarray(width,float)
    pm=np.asarray(pose_mask); wm=np.asarray(width_mask)
    F=np.asarray(F,float); D=np.asarray(D,float)
    br=np.asarray(beta_rotation,float); bw=np.asarray(beta_width,float)
    if p.shape!=(n,2,3) or R.shape!=(n,2,3,3) or w.shape!=(n,2): raise ValueError('baseline shape')
    if pm.shape!=(n,2,2) or wm.shape!=(n,2) or pm.dtype!=bool or wm.dtype!=bool: raise ValueError('component masks required')
    if F.shape!=(n,2,3,3) or D.shape!=(n,2,3) or br.shape!=(n,2) or bw.shape!=(n,2): raise ValueError('envelope shape')
    if not np.isfinite(D).all() or np.any(D<0) or not np.isfinite(br).all() or np.any(br<0) or not np.isfinite(bw).all() or np.any(bw<0): raise ValueError('invalid budget')
    fm=np.ones((n,2),bool) if frame_mask is None else np.asarray(frame_mask)
    if fm.shape!=(n,2) or fm.dtype!=bool: raise ValueError('frame mask')
    if not np.isfinite(F[fm]).all() or not np.allclose(np.swapaxes(F[fm],-1,-2)@F[fm],np.eye(3),atol=1e-8) or np.any(np.linalg.det(F[fm])<0): raise ValueError('frame not SO3')
    if not np.isfinite(p[pm[...,0]]).all() or not np.isfinite(R[pm[...,1]]).all() or not np.isfinite(w[wm]).all(): raise ValueError('invalid observed baseline')
    validR=R[pm[...,1]]
    if not np.allclose(np.swapaxes(validR,-1,-2)@validR,np.eye(3),atol=1e-7) or np.any(np.linalg.det(validR)<0): raise ValueError('invalid reference rotation')
    zp=project_coefficients(z,edit_mask); B=spline_basis(t,episode_bounds or (t[0],t[-1])); v=B@zp
    pp=np.full_like(p,np.nan); rr=np.full_like(R,np.nan); ww=np.full_like(w,np.nan)
    lo,hi=np.broadcast_arrays(np.asarray(width_limits[0],float),np.asarray(width_limits[1],float))
    lo=np.broadcast_to(lo,(2,));hi=np.broadcast_to(hi,(2,))
    if np.any(lo>hi): raise ValueError('width limits')
    for h,k in enumerate((0,7)):
        available=pm[:,h,0]; qualified=available&fm[:,h]
        pp[available,h]=p[available,h]
        pp[qualified,h]+=np.einsum('nij,nj->ni',F[qualified,h],D[qualified,h]*v[qualified,k:k+3])
        valid=pm[:,h,1]
        rr[valid,h]=R[valid,h]@Rotation.from_rotvec(br[valid,h,None]*v[valid,k+3:k+6]).as_matrix()
        valid=wm[:,h];ww[valid,h]=np.clip(w[valid,h]+bw[valid,h]*v[valid,k+6],lo[h],hi[h])
    return DecodedReference(pp,rr,ww,zp,z.copy(),pm.copy(),wm.copy(),np.where(fm,'AVAILABLE','UNKNOWN'))


class CommonRetiming:
    """One monotone clock for a whole episode, numerical tolerance <=1e-6 s."""
    def __init__(self,nodes,kappa,allowed=True,offset=None):
        if not isinstance(allowed,(bool,np.bool_)):raise ValueError("allowed must be boolean")
        if offset is not None:offset=_finite_scalar(offset,"control offset")
        self.nodes=np.asarray(nodes,float); k=np.asarray(kappa,float)
        if self.nodes.shape!=(32,) or k.shape!=(32,) or not np.isfinite(self.nodes).all() or not np.isfinite(k).all() or np.any(np.diff(self.nodes)<=0): raise ValueError('32 increasing finite nodes required')
        self.a=self.nodes[0];self.b=self.nodes[-1];self.offset=self.a if offset is None else float(offset)
        k=np.clip(k,0,np.log(3)) if allowed else np.zeros(32)
        raw=PchipInterpolator(self.nodes,k,extrapolate=False)
        def duration(g): return quad(lambda x:np.exp(g*raw(x)),self.a,self.b,epsabs=1e-12,epsrel=1e-12,points=self.nodes[1:-1],limit=200)[0]
        cap=2*(self.b-self.a)
        self.gamma=brentq(lambda g:duration(g)-cap,0,1,xtol=1e-13) if duration(1)>cap else 1.
        self.kappa=PchipInterpolator(self.nodes,self.gamma*k,extrapolate=False)
        self.end=self.forward(self.b)
    def _check(self,t):
        t=np.asarray(t,float)
        if not np.isfinite(t).all() or np.any(t<self.a) or np.any(t>self.b): raise ValueError('time outside episode')
        return t
    def stretch(self,t):return np.exp(self.kappa(self._check(t)))
    def forward(self,t):
        t=self._check(t)
        def one(x): return self.offset+quad(lambda u:np.exp(self.kappa(u)),self.a,float(x),epsabs=1e-12,epsrel=1e-12,points=self.nodes[(self.nodes>self.a)&(self.nodes<x)],limit=200)[0]
        return np.vectorize(one,otypes=[float])(t)
    def inverse(self,tau):
        tau=np.asarray(tau,float)
        if not np.isfinite(tau).all() or np.any(tau<self.offset) or np.any(tau>self.end):raise ValueError('control time outside episode')
        return np.vectorize(lambda x:brentq(lambda t:float(self.forward(t))-x,self.a,self.b,xtol=1e-14),otypes=[float])(tau)
    def derivatives(self,t,qt,qtt):
        t=self._check(t);s=self.stretch(t);st=s*self.kappa.derivative()(t)
        while s.ndim<np.ndim(qt):s=s[...,None];st=st[...,None]
        return qt/s,qtt/s**2-qt*st/s**3


def original_baseline_budget_check(original,candidate,translation_cap,rotation_cap,width_cap,tolerance=1e-9):
    """Check cumulative edits against original baseline, never previous candidate."""
    tolerance=_finite_scalar(tolerance,'tolerance',True)
    def validate_reference(reference):
        pm=np.asarray(reference.pose_mask);wm=np.asarray(reference.width_mask)
        p=np.asarray(reference.position);r=np.asarray(reference.rotation);w=np.asarray(reference.width)
        if pm.ndim!=3 or pm.shape[1:]!=(2,2) or pm.dtype!=bool or wm.shape!=pm.shape[:2] or wm.dtype!=bool:raise ValueError('invalid component masks')
        n=len(pm)
        if p.shape!=(n,2,3) or r.shape!=(n,2,3,3) or w.shape!=(n,2):raise ValueError('invalid reference shapes')
        if any(x.dtype.kind not in 'iuf' for x in (p,r,w)):raise ValueError('reference must be numeric')
        if not np.isfinite(p[pm[...,0]]).all() or not np.isfinite(r[pm[...,1]]).all() or not np.isfinite(w[wm]).all():raise ValueError('nonfinite active reference')
        valid=r[pm[...,1]]
        if not np.allclose(np.swapaxes(valid,-1,-2)@valid,np.eye(3),atol=1e-8) or not np.allclose(np.linalg.det(valid),1,atol=1e-8):raise ValueError('active rotation not SO3')
        return pm,wm
    pm,wm=validate_reference(original);cm,cw=validate_reference(candidate)
    if not np.array_equal(pm,cm) or not np.array_equal(wm,cw):raise ValueError('original masks changed')
    def validate_cap(cap):
        a=np.asarray(cap)
        if a.dtype.kind not in 'iuf' or not np.isfinite(a).all() or np.any(a<0):raise ValueError('invalid physical budget')
        try:return np.broadcast_to(a,pm.shape[:2])
        except ValueError as error:raise ValueError('budget not broadcast-compatible') from error
    translation_cap=validate_cap(translation_cap);rotation_cap=validate_cap(rotation_cap);width_cap=validate_cap(width_cap)
    dp=np.linalg.norm(candidate.position-original.position,axis=-1)
    dr=np.full(pm.shape[:2],np.nan);valid=pm[...,1]
    dr[valid]=Rotation.from_matrix(np.swapaxes(original.rotation[valid],-1,-2)@candidate.rotation[valid]).magnitude()
    dw=np.abs(candidate.width-original.width)
    failed=(pm[...,0]&(dp>translation_cap+tolerance))|(pm[...,1]&(dr>rotation_cap+tolerance))|(wm&(dw>width_cap+tolerance))
    return {'status':'REJECTED' if np.any(failed) else 'WITHIN_ORIGINAL_REFERENCE_BUDGET','failed':failed,'translation_m':dp,'rotation_rad':dr,'opening_m':dw,'physical_status':'NOT_RUN'}


def fit_normalized_target(t,target_values,envelopes,edit_mask,bounds,fit_tolerance=1e-4):
    """Fit 14 normalized channels after caller's exact F^-1 and SO3 log.

    target_values physical [N,14], envelopes same units/shape; zero budgets
    require zero target. Preserve teacher and reject clip-as-truth.
    """
    from scipy.optimize import minimize
    target=np.asarray(target_values,float);env=np.asarray(envelopes,float)
    if target.shape!=(len(t),14) or env.shape!=target.shape or not np.isfinite(target).all() or not np.isfinite(env).all() or np.any(env<0):raise ValueError('target fit shapes/values')
    if np.any((env==0)&(np.abs(target)>1e-12)):return {'status':'OUT_OF_PROFILE','teacher':target.copy()}
    normalized=np.divide(target,env,out=np.zeros_like(target),where=env>0)
    for k in (0,3,7,10):
        if np.any(np.linalg.norm(normalized[:,k:k+3],axis=-1)>1+1e-8):return {'status':'OUT_OF_PROFILE','teacher':target.copy()}
    if np.any(np.abs(normalized[:,[6,13]])>1+1e-8):return {'status':'OUT_OF_PROFILE','teacher':target.copy()}
    B=spline_basis(t,bounds);mask=np.asarray(edit_mask)
    if mask.shape!=(32,15) or mask.dtype!=bool:raise ValueError('fit edit mask')
    initial=np.zeros((32,15));initial[:,:14]=np.linalg.lstsq(B,normalized,rcond=None)[0];initial=project_coefficients(initial,mask)
    active=np.flatnonzero(mask[:,:14].ravel())
    def unpack(x):
        z=np.zeros((32,15));v=z[:,:14].copy();v.flat[active]=x;z[:,:14]=v;return z
    def objective(x):return np.sum(((B@unpack(x)[:,:14]-normalized)*env)**2)
    def domain(x):
        z=unpack(x);return np.concatenate([1-np.linalg.norm(z[:,k:k+3],axis=-1) for k in (0,3,7,10)]+[1-np.abs(z[:,6]),1-np.abs(z[:,13])])
    if len(active):
        result=minimize(objective,initial[:,:14].ravel()[active],method='SLSQP',constraints=[{'type':'ineq','fun':domain}],options={'maxiter':200,'ftol':1e-12});coeff=unpack(result.x);converged=result.success
    else:coeff=initial;converged=True
    residual=float(np.max(np.abs((B@coeff[:,:14])*env-target)))
    return {'status':'FITTED' if converged and residual<=fit_tolerance else 'OUT_OF_REPRESENTATION','coefficients':coeff,'target_fit_residual':residual,'teacher':target.copy(),'solver_converged':bool(converged)}


def translation_derivatives(t,coefficients,bounds,F,F_t,F_tt,D,D_t,D_tt,p0_t,p0_tt):
    """Exact product rule, including moving basis and envelope derivatives.

    All F arrays [N,3,3], D arrays [N,3]; coefficients [32,3].
    Baseline and basis derivative provenance/continuity remain caller obligations.
    """
    z=spline_basis(t,bounds)@coefficients;zt=spline_basis(t,bounds,1)@coefficients;ztt=spline_basis(t,bounds,2)@coefficients
    v=D*z;vt=D_t*z+D*zt;vtt=D_tt*z+2*D_t*zt+D*ztt
    apply=lambda A,x:np.einsum('nij,nj->ni',A,x)
    return p0_t+apply(F_t,v)+apply(F,vt),p0_tt+apply(F_tt,v)+2*apply(F_t,vt)+apply(F,vtt)
