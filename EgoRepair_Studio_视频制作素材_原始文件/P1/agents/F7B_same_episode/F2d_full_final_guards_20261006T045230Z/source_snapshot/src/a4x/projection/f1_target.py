"""Exact F1 curve recipe for fixed baseline/frame with true-episode C2 envelopes.

Moving baseline/basis require another explicitly bounded recipe, not interpolation
of sampled decoded poses. This restricted recipe evaluates the accepted decoder.
"""
import hashlib,json
from pathlib import Path
from a4x.provenance import verify_artifact
import numpy as np
from scipy.interpolate import BSpline
from a4x.repair.math import decode_reference,c2_envelope,project_coefficients
from .continuous import real

class FixedFrameF1Target:
    def __init__(self,*,bounds,position,rotation,width,F,D,rotation_cap,width_cap,z,edit_mask,source_sha256,restrictions=(),protected=(),transition=.15,width_limits=(0.,.08),hand=0,source_ref=None,synthetic_fixture=False,pose_mask=None,width_mask=None,retiming_allowed=False,tool_semantics=None):
        self.a,self.b=real(bounds,(2,));self.p=real(position,(3,));self.R=real(rotation,(3,3));self.w=float(real(width));self.F=real(F,(3,3));self.D=real(D,(3,));self.br=float(real(rotation_cap));self.bw=float(real(width_cap));self.mask=np.asarray(edit_mask);raw_z=np.asarray(z)
        if self.mask.dtype!=bool or self.mask.shape!=(32,15) or raw_z.shape!=(32,15) or raw_z.dtype.kind not in 'fiu' or not np.isfinite(raw_z[self.mask]).all():raise ValueError('Invalid active coefficients or original edit mask')
        self.z=raw_z.astype(float)
        if self.mask.dtype!=bool or self.mask.shape!=(32,15) or hand not in (0,1) or self.a>=self.b or self.br<0 or self.bw<0 or np.any(self.D<0):raise ValueError('Invalid F1 recipe')
        if not isinstance(synthetic_fixture,bool):raise ValueError('Fixture flag must bool')
        if pose_mask is None or width_mask is None:
            if not synthetic_fixture:raise ValueError('Production requires original component masks')
            pose_mask=np.ones((2,2),bool);width_mask=np.ones(2,bool)
        self.pose_mask=np.asarray(pose_mask).copy();self.width_mask=np.asarray(width_mask).copy()
        if self.pose_mask.dtype!=bool or self.pose_mask.ndim!=2 or self.pose_mask.shape[1]!=2 or self.width_mask.dtype!=bool or self.width_mask.shape!=(len(self.pose_mask),):raise ValueError('Original Boolean component masks required')
        self.synthetic_fixture=synthetic_fixture;self.source_ref=None if source_ref is None else json.loads(json.dumps(source_ref));self.allowed_root=Path(__file__).resolve().parents[3]
        if self.source_ref is None and not synthetic_fixture:raise ValueError('Production target requires verified source artifact')
        if self.source_ref is not None:
            verify_artifact(self.source_ref,[self.allowed_root])
            if self.source_ref['sha256']!=source_sha256:raise ValueError('Source artifact digest mismatch')
        if not isinstance(retiming_allowed,(bool,np.bool_)):raise ValueError('Explicit Boolean retiming permission required')
        from .tool import NATIVE_SITE,PAD_MIDPOINT
        if tool_semantics is None:
            if not synthetic_fixture:raise ValueError('Explicit production G/P tool semantics required')
            tool_semantics=NATIVE_SITE
        if tool_semantics not in (NATIVE_SITE,PAD_MIDPOINT):raise ValueError('Unsupported G/P tool semantics')
        self.tool_semantics=tool_semantics
        self.retiming_allowed=bool(retiming_allowed)
        self.hand=hand;self.source=source_sha256;self.restrictions=tuple(tuple(x) for x in restrictions);self.protected=tuple(tuple(x) for x in protected);self.transition=float(real(transition));self.width_limits=tuple(real(width_limits,(2,)))
        if len(source_sha256)!=64 or self.transition<=0:raise ValueError('Unbound F1 recipe')
        self.source_caps=None
        if self.source_ref is not None:
            path=verify_artifact(self.source_ref,[self.allowed_root])
            if path.suffix!='.npz':raise ValueError('Production F1 recipe must bind explicit NPZ payload')
            with np.load(path,allow_pickle=False) as payload:
                fields={'episode_bounds_s':[self.a,self.b],'D_m':self.D,'beta_rotation_rad':self.br,'beta_width_m':self.bw,'z':self.z,'edit_mask':self.mask,'pose_mask':self.pose_mask,'width_mask':self.width_mask,'retiming_allowed':self.retiming_allowed,'tool_semantics':self.tool_semantics}
                for key in ('edit_mask','pose_mask','width_mask','retiming_allowed'):
                    if payload[key].dtype!=bool:raise ValueError('Original source Boolean fields must remain Boolean')
                for key in ('episode_bounds_s','D_m','beta_rotation_rad','beta_width_m','position_m','rotation','opening_m','F_world','time_s','translation_cap_m','rotation_cap_rad','width_cap_m'):
                    real(payload[key])
                if payload['z'].dtype.kind not in 'fiu':raise ValueError('Original source coefficient dtype invalid')
                if any(key not in payload.files or not np.array_equal(payload[key],value,equal_nan=True) if key=='z' else key not in payload.files or not np.array_equal(payload[key],value) for key,value in fields.items()):raise ValueError('F1 recipe differs from actual preregistered source payload')
                self.source_caps=tuple(float(real(payload[key])) for key in ('translation_cap_m','rotation_cap_rad','width_cap_m'))
                if type(self) is FixedFrameF1Target:
                    for key,value in [('position_m',self.p),('rotation',self.R),('opening_m',self.w),('F_world',self.F)]:
                        if not np.all(payload[key]==value):raise ValueError('Fixed original baseline differs from source payload')
        self.effective=project_coefficients(self.z,self.mask)
        knots=np.r_[np.repeat(self.a,4),np.linspace(self.a,self.b,30)[1:-1],np.repeat(self.b,4)]
        self.bs=BSpline(knots,self.effective,3)
        # Derivative B-spline convex hull gives a rigorous global component bound.
        derivative=self.bs.derivative();self.vdot=np.max(abs(derivative.c[:len(derivative.t)-derivative.k-1]),axis=0)
        self.vmax=np.max(abs(self.effective),axis=0)
        self.immutable_digest=self._digest()
    def _digest(self):
        if self.source_ref is not None:verify_artifact(self.source_ref,[self.allowed_root])
        arrays=[self.p,self.R,self.F,self.D,self.z,self.mask,self.effective,self.bs.t,self.bs.c,self.vdot,self.vmax,self.pose_mask,self.width_mask]
        h=hashlib.sha256(b''.join(x.tobytes() for x in arrays));h.update(repr((self.a,self.b,self.w,self.br,self.bw,self.hand,self.source,self.restrictions,self.protected,self.transition,self.width_limits,self.source_ref,self.synthetic_fixture,self.retiming_allowed,self.tool_semantics,self.source_caps,self.bs.k,self.bs.axis,self.bs.extrapolate)).encode());return h.hexdigest()
    def envelope(self,t):return c2_envelope(t,1.,self.restrictions,self.protected,self.transition,(self.a,self.b))
    def __call__(self,t):
        if self._digest()!=self.immutable_digest:raise ValueError('F1_RECIPE_DRIFT')
        e=self.envelope(np.array([t]));p=np.tile(self.p,(1,2,1));R=np.tile(self.R,(1,2,1,1));w=np.full((1,2),self.w);F=np.tile(self.F,(1,2,1,1));D=np.tile(self.D,(1,2,1))*e[:,None,None]
        decoded=decode_reference(np.array([t]),self.z,p,R,w,F,D,np.full((1,2),self.br)*e[:,None],np.full((1,2),self.bw)*e[:,None],self.mask,np.ones((1,2,2),bool),np.ones((1,2),bool),self.width_limits,episode_bounds=(self.a,self.b))
        return decoded.position[0,self.hand],decoded.rotation[0,self.hand],decoded.width[0,self.hand]
    def bounds(self,a,b):
        if not self.a<=a<=b<=self.b:raise ValueError('Outside F1 episode')
        # Product of factors in [0,1], each transition derivative <=1.875/epsilon.
        edot=(2+2*(len(self.restrictions)+len(self.protected)))*1.875/self.transition
        k=7*self.hand;half=(b-a)/2
        translation=half*np.linalg.norm(self.D*(self.vdot[k:k+3]+edot*self.vmax[k:k+3]))
        rotation=half*self.br*np.linalg.norm(self.vdot[k+3:k+6]+edot*self.vmax[k+3:k+6])
        width=half*self.bw*(self.vdot[k+6]+edot*self.vmax[k+6])
        return float(translation),float(rotation),float(width)
