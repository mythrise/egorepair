"""One global accepted F1 clock; no window-local clocks or state rewrites."""
import hashlib
import numpy as np
from a4x.repair.math import CommonRetiming
from .continuous import JointCurve

class RetimedCurve:
    def __init__(self,source_curve,clock):
        if not isinstance(source_curve,JointCurve) or not isinstance(clock,CommonRetiming):raise ValueError('Explicit global curve and F1 clock required')
        if not clock.a<=source_curve.t[0]<source_curve.t[-1]<=clock.b:raise ValueError('Clock/source episode mismatch')
        self.source=source_curve;self.clock=clock;self.q=source_curve.q.copy();self.t=clock.forward(source_curve.t);self.digest=self._digest()
    def _digest(self):return hashlib.sha256(self.source.digest.encode()+self.q.tobytes()+self.t.tobytes()+self.clock.nodes.tobytes()+self.clock.kappa.x.tobytes()+self.clock.kappa.c.tobytes()+repr((self.clock.a,self.clock.b,self.clock.end,self.clock.offset,self.clock.gamma,self.clock.kappa.axis,self.clock.kappa.extrapolate)).encode()).hexdigest()
    def _check(self):
        if self._digest()!=self.digest:raise ValueError('GLOBAL_CLOCK_DRIFT')
    def __call__(self,t,order=0):
        self._check();source_t=self.clock.inverse(t)
        if order==0:return self.source(source_t)
        first,second=self.clock.derivatives(source_t,self.source(source_t,1),self.source(source_t,2))
        if order==1:return first
        if order==2:return second
        raise ValueError('Unsupported derivative')
    def bounds(self,a,b,order=0):
        self._check();left,right=self.clock.inverse(np.array([a,b]));lo,hi=self.source.bounds(left,right,order)
        if order==0:return lo,hi
        # kappa>=0 so s>=1; conservative bounds retain nonmonotone source movement.
        vmax=np.maximum(abs(lo),abs(hi))
        if order==1:return -vmax,vmax
        if order!=2:raise ValueError('Unsupported derivative')
        derivative=self.clock.kappa.derivative();bound=0.
        for i in range(len(derivative.x)-1):
            l=max(left,derivative.x[i]);r=min(right,derivative.x[i+1])
            if l>r:continue
            poly=derivative.c[:,i];points=[l-derivative.x[i],r-derivative.x[i]]
            for root in np.roots(np.polyder(poly)):
                if abs(root.imag)<1e-10 and points[0]<=root.real<=points[1]:points.append(root.real)
            bound=max(bound,float(np.max(abs(np.polyval(poly,points)))))
        vlow,vhigh=self.source.bounds(left,right,1);vmax+=np.maximum(abs(vlow),abs(vhigh))*bound
        return -vmax,vmax

class RetimedF1Target:
    def __init__(self,source,clock):
        from .f1_target import FixedFrameF1Target
        from .moving_target import MovingFrameF1Target
        if type(source) not in (FixedFrameF1Target,MovingFrameF1Target) or not isinstance(clock,CommonRetiming):raise ValueError('Unsupported global reference clock recipe')
        if source.a!=clock.a or source.b!=clock.b:raise ValueError('Original episode mismatch')
        self.source=source;self.clock=clock;self.immutable_digest=self._digest()
    def _digest(self):return hashlib.sha256(self.source._digest().encode()+self.clock.nodes.tobytes()+self.clock.kappa.c.tobytes()+self.clock.kappa.x.tobytes()+repr((self.clock.a,self.clock.b,self.clock.offset,self.clock.end,self.clock.gamma,self.clock.kappa.axis,self.clock.kappa.extrapolate)).encode()).hexdigest()
    def _check(self):
        if self._digest()!=self.immutable_digest:raise ValueError('RETIME_REFERENCE_DRIFT')
    def __call__(self,tau):self._check();return self.source(float(self.clock.inverse(tau)))
    def bounds(self,a,b):
        self._check();left,right=self.clock.inverse(np.array([a,b]));return tuple(2*x for x in self.source.bounds(left,right))
