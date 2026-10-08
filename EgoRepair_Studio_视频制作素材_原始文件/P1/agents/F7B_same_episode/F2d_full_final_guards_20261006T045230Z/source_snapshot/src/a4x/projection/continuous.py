"""Continuous polynomial qualification; discrete samples are not certificates."""
from dataclasses import dataclass
import hashlib,time
import numpy as np
from scipy.interpolate import CubicSpline

def real(value, shape=None):
    a=np.asarray(value)
    def leaves(x):
        if isinstance(x,np.ndarray):return x.dtype.kind in "fiu" and np.all(np.isfinite(x))
        if isinstance(x,(list,tuple)): return all(leaves(v) for v in x)
        return not isinstance(x,(bool,np.bool_)) and isinstance(x,(int,float,np.integer,np.floating))
    if not leaves(value) and not isinstance(value,np.ndarray): raise ValueError('Non-real quantity')
    if a.dtype.kind not in 'fiu' or not np.all(np.isfinite(a)): raise ValueError('Invalid physical quantity')
    if shape is not None and a.shape!=shape: raise ValueError('Shape mismatch')
    return a.astype(float)

class JointCurve:
    """One global C2 interpolant, with exact span-extrema derivative bounds."""
    def __init__(self,t,q):
        self.t=real(t);self.q=real(q)
        if self.t.ndim!=1 or len(self.t)<2 or self.q.ndim!=2 or len(self.q)!=len(self.t) or np.any(np.diff(self.t)<=0):raise ValueError('Invalid curve clock')
        self.spline=CubicSpline(self.t,self.q,axis=0,bc_type=((1,np.zeros(self.q.shape[1])),(1,np.zeros(self.q.shape[1]))))
        self.digest=self._signature()
    def _signature(self):return hashlib.sha256(self.t.tobytes()+self.q.tobytes()+self.spline.x.tobytes()+self.spline.c.tobytes()+repr((self.spline.axis,self.spline.extrapolate)).encode()).hexdigest()
    def _guard(self):
        if self._signature()!=self.digest:raise ValueError('CURVE_SOURCE_DRIFT')
    def __call__(self,t,order=0):
        self._guard();return self.spline(t,nu=order)
    def bounds(self,a,b,order=0):
        self._guard()
        if not self.t[0]<=a<=b<=self.t[-1]:raise ValueError('Outside curve')
        lo=np.full(self.q.shape[1],np.inf);hi=-lo
        poly=self.spline.derivative(order)
        for i in range(len(self.t)-1):
            left=max(a,self.t[i]);right=min(b,self.t[i+1])
            if left>right:continue
            for j in range(self.q.shape[1]):
                c=poly.c[:,i,j]; points=[left-self.t[i],right-self.t[i]]
                for r in np.roots(np.polyder(c)):
                    if abs(r.imag)<1e-10 and points[0]<=r.real<=points[1]:points.append(r.real)
                v=np.polyval(c,points);lo[j]=min(lo[j],min(v));hi[j]=max(hi[j],max(v))
        return lo,hi

@dataclass(frozen=True)
class ContinuousProfile:
    numeric_error_m:float=1e-6
    clearance_m:float=0.
    max_depth:int=16
    max_distance_calls:int=20000
    max_wall_s:float=120.
    def __post_init__(self):
        for value in (self.numeric_error_m,self.clearance_m,self.max_wall_s):
            if isinstance(value,(bool,np.bool_)) or not isinstance(value,(int,float,np.integer,np.floating)) or not np.isfinite(value) or value<0:raise ValueError('Invalid continuous distance profile')
        for value in (self.max_depth,self.max_distance_calls):
            if isinstance(value,(bool,np.bool_)) or not isinstance(value,(int,np.integer)) or value<0:raise ValueError('Invalid continuous budget')

def qualify(curve,limits,velocity,acceleration,oracle,profile=ContinuousProfile()):
    """Oracle returns signed distances and per-pair conservative displacement bounds.

    Missing evidence is UNKNOWN. Motion bounds must cover the actual whole interval.
    """
    limits=real(limits,(curve.q.shape[1],2));velocity=real(velocity,(curve.q.shape[1],));acceleration=real(acceleration,(curve.q.shape[1],))
    if np.any(limits[:,0]>limits[:,1]) or np.any(velocity<=0) or np.any(acceleration<=0):raise ValueError('Invalid derivative limits')
    a,b=curve.t[[0,-1]];low,high=curve.bounds(a,b)
    failures=[]
    if np.any(low<limits[:,0]) or np.any(high>limits[:,1]):failures.append('JOINT_POSITION')
    for order,cap,name in [(1,velocity,'JOINT_VELOCITY'),(2,acceleration,'JOINT_ACCELERATION')]:
        l,h=curve.bounds(a,b,order)
        if np.any(np.maximum(abs(l),abs(h))>cap):failures.append(name)
    calls=0;start=time.monotonic();unknown=[];witness=[];stack=[(float(a),float(b),0)]
    while stack:
        left,right,depth=stack.pop();mid=(left+right)/2
        if time.monotonic()-start>=profile.max_wall_s:unknown.extend([[l,r,'WALL_BUDGET'] for l,r,d in [(left,right,depth)]+stack]);break
        if calls+getattr(oracle,'distance_cost',1)>profile.max_distance_calls:unknown.append([left,right,'DISTANCE_BUDGET']);continue
        try: distances=oracle.distances(curve(mid),time_s=mid) if getattr(oracle,'supports_time',False) else oracle.distances(curve(mid))
        except (ValueError,NotImplementedError) as e:unknown.append([left,right,str(e)]);continue
        calls+=len(distances)
        if not distances:unknown.append([left,right,'EMPTY_PAIR_SCOPE']);continue
        l,h=curve.bounds(left,right,1);dq=(right-left)/2*np.maximum(abs(l),abs(h))
        unresolved=False
        interval_bounds=None
        if callable(getattr(oracle,'interval_displacement_bounds',None)):
            try:interval_bounds=oracle.interval_displacement_bounds(dq,left,right)
            except (ValueError,NotImplementedError):interval_bounds={}
        for pair,distance in distances.items():
            if not np.isfinite(distance):unknown.append([left,right,'NONFINITE_DISTANCE']);unresolved=True;continue
            clearance=oracle.clearance_for(pair,profile.clearance_m) if callable(getattr(oracle,'clearance_for',None)) else profile.clearance_m
            try:clearance=float(real(clearance,()))
            except ValueError:
                unknown.append([left,right,'MALFORMED_CLEARANCE']);unresolved=True;continue
            known_collision=oracle.is_known_collision(pair,clearance) if callable(getattr(oracle,'is_known_collision',None)) else distance<clearance
            if known_collision:
                failures.append('COLLISION');witness.append({'time_s':mid,'pair':pair,'distance_m':distance});break
            try:bound=interval_bounds.get(pair,np.inf) if interval_bounds is not None else oracle.displacement_bound(pair,dq,left,right)
            except (ValueError,NotImplementedError):bound=np.inf
            try:
                bound=float(real(bound,()))
                if bound<0:raise ValueError('Negative displacement bound')
            except ValueError:
                unknown.append([left,right,'MALFORMED_OR_MISSING_DISPLACEMENT_BOUND']);unresolved=True;continue
            if distance-bound-profile.numeric_error_m<=clearance:unresolved=True
        if 'COLLISION' in failures:
            stack.clear();break
        if unresolved:
            if depth>=profile.max_depth:unknown.append([left,right,'UNRESOLVED_LOWER_BOUND'])
            else:stack.extend([(left,mid,depth+1),(mid,right,depth+1)])
    from .distance import NativeDistance
    scope='CONTINUOUS_MODEL_ONLY_M6_NOT_RUN' if type(oracle) is NativeDistance else 'ANALYTICAL_ORACLE_ASSUMPTION_NOT_PHYSICAL_MODEL_QUALIFICATION'
    return {'status':'FAIL' if failures else 'UNKNOWN' if unknown else 'PASS','failures':sorted(set(failures)),'unknown_intervals':unknown,'witnesses':witness,'distance_calls':calls,'wall_s':time.monotonic()-start,'curve_sha256':curve.digest,'scope':scope,'oracle_scope':getattr(oracle,'scope',None),'model_sha256':getattr(oracle,'model_digest',None),'actual_native_distance_calls_cumulative':getattr(oracle,'actual_distance_calls',None),'oracle_cache_hits_cumulative':getattr(oracle,'cache_hits',None)}
