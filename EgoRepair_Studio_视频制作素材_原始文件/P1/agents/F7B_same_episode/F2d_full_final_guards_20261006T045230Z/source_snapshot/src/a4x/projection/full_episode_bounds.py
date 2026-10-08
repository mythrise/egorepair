"""Indexed exact polynomial extrema for full episode development gates.

Polynomial source is guarded on every query. Roots are precomputed, never
replaced by sampling. Only overlapping spans are visited.
"""
import hashlib
import numpy as np

class IndexedPolynomialBounds:
    def __init__(self,poly):
        self.poly=poly;self.signature=self._signature();self.cache={}
    def _signature(self):
        return hashlib.sha256(self.poly.c.tobytes()+self.poly.x.tobytes()).digest()
    def bounds(self,a,b,order=0):
        if self._signature()!=self.signature:raise ValueError('INDEXED_POLYNOMIAL_SOURCE_DRIFT')
        p=self.poly.derivative(order);x=p.x;size=int(np.prod(p.c.shape[2:])) or 1
        if not x[0]<=a<=b<=x[-1]:raise ValueError('Outside curve')
        if order not in self.cache:
            roots={}
            for i in range(len(x)-1):
                for j,c in enumerate(p.c[:,i].reshape((len(p.c),size)).T):
                    roots[i,j]=[r.real for r in np.roots(np.polyder(c)) if abs(r.imag)<1e-10]
            self.cache[order]=roots
        roots=self.cache[order];lo=np.full(size,np.inf);hi=-lo
        first=max(0,int(np.searchsorted(x,a,side='left'))-1);last=min(len(x)-2,int(np.searchsorted(x,b,side='right'))-1)
        for i in range(first,last+1):
            left=max(a,x[i])-x[i];right=min(b,x[i+1])-x[i]
            if left>right:continue
            for j,c in enumerate(p.c[:,i].reshape((len(p.c),size)).T):
                points=[left,right]+[r for r in roots[i,j] if left<=r<=right];v=np.polyval(c,points);lo[j]=min(lo[j],np.min(v));hi[j]=max(hi[j],np.max(v))
        return lo,hi
    def derivative_norm(self,a,b):
        lo,hi=self.bounds(a,b,1);return float(np.linalg.norm(np.maximum(abs(lo),abs(hi))))

def accelerate(curve,target):
    """Bind equivalent indexed extrema locally; no global accepted API mutation."""
    from .f1_target import FixedFrameF1Target
    q=IndexedPolynomialBounds(curve.spline)
    def joint_bounds(a,b,order=0):curve._guard();return q.bounds(a,b,order)
    curve.bounds=joint_bounds
    p=IndexedPolynomialBounds(target.position_curve);w=IndexedPolynomialBounds(target.width_curve)
    r=IndexedPolynomialBounds(target.rotation_curve.interpolator);f=IndexedPolynomialBounds(target.frame_curve.interpolator)
    def target_bounds(a,b):
        if target._digest()!=target.immutable_digest:raise ValueError('MOVING_F1_RECIPE_DRIFT')
        if not target.support_a<=a<=b<=target.support_b:raise ValueError('Outside target')
        translation,rotation,width=FixedFrameF1Target.bounds(target,a,b);half=(b-a)/2
        translation+=half*(p.derivative_norm(a,b)+f.derivative_norm(a,b)*max(target.D)*float(np.max(np.linalg.norm(target.effective[:,7*target.hand:7*target.hand+3],axis=1))))
        rotation+=half*r.derivative_norm(a,b);width+=half*w.derivative_norm(a,b)
        return translation,rotation,width
    target.bounds=target_bounds

def tighten_native_ancestor_bounds(oracle):
    """Per-ancestor serial hinge triangle bounds, preserving full native geometry.

    For each ancestor hinge, only its descendant offsets enter the distance
    to that hinge axis. The common upstream base offsets do not enter that
    lever length. Every descendant pivot contributes twice its offset, from
    p + R(q)(x-p); the ancestor pivot itself contributes once.
    """
    from .source_geometry import verify_native_robot
    import mujoco
    verify_native_robot(oracle.model);m=oracle.model
    for geom,old in oracle.weights.items():
        body=int(m.geom_bodyid[geom]);path=[]
        while body:path.append(body);body=int(m.body_parentid[body])
        weights=old.copy()
        for index,j in enumerate(oracle.adapter.joint_ids):
            ancestor=int(m.jnt_bodyid[j])
            if ancestor not in path:continue
            if int(m.jnt_type[j])!=int(mujoco.mjtJoint.mjJNT_HINGE):raise ValueError('Non-hinge ancestor unsupported')
            descendants=path[:path.index(ancestor)]
            pivots=[k for b in descendants for k in range(m.body_jntadr[b],m.body_jntadr[b]+m.body_jntnum[b])]
            radius=oracle.radius[geom]+np.linalg.norm(m.geom_pos[geom])+np.linalg.norm(m.jnt_pos[j])+sum(np.linalg.norm(m.body_pos[b]) for b in descendants)+sum(2*np.linalg.norm(m.jnt_pos[k]) for k in pivots)
            weights[index]=min(weights[index],radius)
        oracle.weights[geom]=weights
    oracle.model_digest=oracle._signature()

def seal_owned_native_model(oracle):
    """Read-only owned MuJoCo model; full content hash retained at both boundaries.

    Scope is an owned numeric worker with native mj_forward only, not arbitrary
    callbacks or a hostile same-UID memory writer. Array identity, readonly
    flags, pointer, shape, strides and dtype remain checked every query.
    """
    if hasattr(oracle,'sealed_model_arrays'):raise ValueError('Already sealed')
    full=oracle._signature();sealed={}
    for prefix,owner in [('model',oracle.model),('opt',oracle.model.opt)]:
        for name in sorted(dir(owner)):
            array=getattr(owner,name)
            if not isinstance(array,np.ndarray):continue
            array.flags.writeable=False
            if getattr(owner,name) is not array or getattr(owner,name).flags.writeable:
                # Fresh native scalar/vector getter views cannot be cached safely.
                # Keep full byte hashing on every query for this field.
                continue
            descriptor=(array.__array_interface__['data'][0],array.shape,array.strides,array.dtype.str)
            sealed[prefix+'.'+name]=(array,hashlib.sha256(array.tobytes()).digest(),descriptor)
    oracle.sealed_model_arrays=sealed;oracle.model_digest=oracle._signature();oracle.full_content_signature_before_seal=full
    return {'policy':'OWNED_NATIVE_FORWARD_ONLY_READONLY_ARRAY_CONTENT_CACHE','full_content_sha256_before':full,'array_count':len(sealed),'hostile_same_uid_memory_scope':False}

def verify_owned_native_model_seal(oracle):
    oracle._signature() # Verify all views/flags/context and small mutable metadata.
    sealed=oracle.sealed_model_arrays;del oracle.sealed_model_arrays
    try:full=oracle._signature()
    finally:oracle.sealed_model_arrays=sealed
    if full!=oracle.full_content_signature_before_seal:raise ValueError('SEALED_MODEL_FULL_CONTENT_DRIFT')
    return {'full_content_sha256_after':full,'matches_before':True}
