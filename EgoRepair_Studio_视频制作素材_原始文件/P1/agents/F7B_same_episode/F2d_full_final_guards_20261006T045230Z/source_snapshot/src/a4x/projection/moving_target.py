"""Whole-episode C2 baseline/moving SO3 basis recipe; no window splicing.

Interpolants are explicit reference-model definitions, not certificates of sensor
accuracy. Motion bounds use polynomial extrema and ||J_SO3||<=1, since the
SO3 exponential Jacobian is an integral of rotations with operator norm one.
"""
import hashlib
import numpy as np
from scipy.interpolate import CubicSpline
from scipy.spatial.transform import Rotation,RotationSpline
from a4x.repair.math import decode_reference
from .f1_target import FixedFrameF1Target
from .continuous import real

def derivative_bound(poly,a,b):
    derivative=poly.derivative();size=int(np.prod(derivative.c.shape[2:])) or 1;maximum=np.zeros(size)
    for i in range(len(derivative.x)-1):
        left=max(a,derivative.x[i]);right=min(b,derivative.x[i+1])
        if left>right:continue
        coefficients=derivative.c[:,i].reshape((derivative.c.shape[0],size))
        for j in range(size):
            c=coefficients[:,j];points=[left-derivative.x[i],right-derivative.x[i]]
            for r in np.roots(np.polyder(c)):
                if abs(r.imag)<1e-10 and points[0]<=r.real<=points[1]:points.append(r.real)
            maximum[j]=max(maximum[j],float(np.max(abs(np.polyval(c,points)))))
    return float(np.linalg.norm(maximum))

class MovingFrameF1Target(FixedFrameF1Target):
    def __init__(self,*,source_time,position_nodes,rotation_nodes,width_nodes,frame_nodes,**kwargs):
        t=real(source_time);p=real(position_nodes,(len(t),3));R=real(rotation_nodes,(len(t),3,3));w=real(width_nodes,(len(t),));F=real(frame_nodes,(len(t),3,3))
        if len(t)<2 or np.any(np.diff(t)<=0) or not kwargs['bounds'][0]<=t[0]<t[-1]<=kwargs['bounds'][1]:raise ValueError('Whole episode source clock mismatch')
        for matrices in (R,F):
            if any(not np.allclose(x.T@x,np.eye(3),atol=1e-8) or not np.isclose(np.linalg.det(x),1,atol=1e-8) for x in matrices):raise ValueError('Invalid moving SO3 input')
        super().__init__(position=p[0],rotation=R[0],width=w[0],F=F[0],**kwargs)
        if np.any(w<self.width_limits[0]) or np.any(w>self.width_limits[1]):raise ValueError('Original width outside range')
        if self.source_ref is not None:
            from a4x.provenance import verify_artifact
            path=verify_artifact(self.source_ref,[self.allowed_root])
            with np.load(path,allow_pickle=False) as payload:
                for key,value in [('time_s',t),('position_m',p),('rotation',R),('opening_m',w),('F_world',F)]:
                    if not np.array_equal(payload[key],value):raise ValueError('Moving baseline/source clock differs from preregistered source')
        self.source_time=t;self.support_a=float(t[0]);self.support_b=float(t[-1]);self.position_curve=CubicSpline(t,p,axis=0);self.width_curve=CubicSpline(t,w);self.rotation_curve=RotationSpline(t,Rotation.from_matrix(R));self.frame_curve=RotationSpline(t,Rotation.from_matrix(F));self.immutable_digest=self._digest()
        for i in range(len(t)-1):
            c=self.width_curve.c[:,i];points=[0.,t[i+1]-t[i]]
            for root in np.roots(np.polyder(c)):
                if abs(root.imag)<1e-10 and 0<=root.real<=points[1]:points.append(root.real)
            values=np.polyval(c,points)
            if min(values)<self.width_limits[0] or max(values)>self.width_limits[1]:raise ValueError('Continuous original width outside limits')
    def _digest(self):
        base=super()._digest()
        if not hasattr(self,'source_time'):return base
        arrays=[self.source_time,self.position_curve.c,self.position_curve.x,self.width_curve.c,self.width_curve.x,self.rotation_curve.interpolator.c,self.rotation_curve.interpolator.x,self.rotation_curve.times,self.frame_curve.interpolator.c,self.frame_curve.interpolator.x,self.frame_curve.times,self.rotation_curve.rotations.as_quat(),self.frame_curve.rotations.as_quat()]
        return hashlib.sha256(base.encode()+repr((self.support_a,self.support_b,self.position_curve.axis,self.position_curve.extrapolate,self.width_curve.axis,self.width_curve.extrapolate,self.rotation_curve.interpolator.axis,self.rotation_curve.interpolator.extrapolate,self.frame_curve.interpolator.axis,self.frame_curve.interpolator.extrapolate)).encode()+b''.join(x.tobytes() for x in arrays)).hexdigest()
    def __call__(self,t):
        if self._digest()!=self.immutable_digest:raise ValueError('MOVING_F1_RECIPE_DRIFT')
        if not self.support_a<=t<=self.support_b:raise ValueError('Outside episode')
        e=self.envelope(np.array([t]));p=np.tile(self.position_curve(t),(1,2,1));R=np.tile(self.rotation_curve(t).as_matrix(),(1,2,1,1));w=np.full((1,2),self.width_curve(t));F=np.tile(self.frame_curve(t).as_matrix(),(1,2,1,1));D=np.tile(self.D,(1,2,1))*e[:,None,None]
        decoded=decode_reference(np.array([t]),self.z,p,R,w,F,D,np.full((1,2),self.br)*e[:,None],np.full((1,2),self.bw)*e[:,None],self.mask,np.ones((1,2,2),bool),np.ones((1,2),bool),self.width_limits,episode_bounds=(self.a,self.b))
        return decoded.position[0,self.hand],decoded.rotation[0,self.hand],decoded.width[0,self.hand]
    def bounds(self,a,b):
        if not self.support_a<=a<=b<=self.support_b:raise ValueError('Reference support absent outside interval')
        translation,rotation,width=super().bounds(a,b);half=(b-a)/2
        translation+=half*(derivative_bound(self.position_curve,a,b)+derivative_bound(self.frame_curve.interpolator,a,b)*max(self.D)*float(np.max(np.linalg.norm(self.effective[:,7*self.hand:7*self.hand+3],axis=1))))
        rotation+=half*derivative_bound(self.rotation_curve.interpolator,a,b)
        width+=half*derivative_bound(self.width_curve,a,b)
        return translation,rotation,width
