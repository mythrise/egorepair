"""Immutable original-baseline admission for projected references."""
from dataclasses import dataclass
import hashlib
import numpy as np
from scipy.spatial.transform import Rotation
from .continuous import real
@dataclass(frozen=True)
class Reference:
    time:np.ndarray
    position:np.ndarray
    rotation:np.ndarray
    width:np.ndarray
    mask:np.ndarray
    source_sha256:str
    frame:str='WORLD_METRE_MODEL_TCP'
    def __post_init__(self):
        t=real(self.time);p=real(self.position,(len(t),3));r=real(self.rotation,(len(t),3,3));w=real(self.width,(len(t),));m=np.asarray(self.mask)
        if t.ndim!=1 or len(t)<2 or np.any(np.diff(t)<=0) or m.dtype!=np.bool_ or m.shape!=(len(t),):raise ValueError('Clock/mask invalid')
        if len(self.source_sha256)!=64 or self.frame!='WORLD_METRE_MODEL_TCP':raise ValueError('Unbound source or frame')
        if any(not np.allclose(x.T@x,np.eye(3),atol=1e-7) or not np.isclose(np.linalg.det(x),1,atol=1e-7) for x in r):raise ValueError('Non-SO3')
        for name,value in [('time',t),('position',p),('rotation',r),('width',w),('mask',m.copy())]:value.setflags(write=False);object.__setattr__(self,name,value)
        object.__setattr__(self,'_seal',self.digest)
    def validate(self):
        if self.digest!=self._seal:raise ValueError('ORIGINAL_REFERENCE_DRIFT')
    @property
    def digest(self):return hashlib.sha256(b''.join(a.tobytes() for a in [self.time,self.position,self.rotation,self.width,self.mask])+self.source_sha256.encode()+self.frame.encode()).hexdigest()

def budget_gate(original,candidate,translation_m,rotation_rad,width_m,protected=None):
    original.validate();candidate.validate();n=len(original.time);translation_m=real(translation_m,(n,));rotation_rad=real(rotation_rad,(n,));width_m=real(width_m,(n,))
    if any(np.any(x<0) for x in [translation_m,rotation_rad,width_m]):raise ValueError('Negative trust budget')
    if original.source_sha256!=candidate.source_sha256 or original.frame!=candidate.frame or not np.array_equal(original.time,candidate.time) or not np.array_equal(original.mask,candidate.mask):return {'status':'OUT_OF_PROFILE','reason':'IMMUTABLE_BINDING_CHANGED'}
    protected=np.zeros(n,dtype=bool) if protected is None else np.asarray(protected)
    if protected.dtype!=np.bool_ or protected.shape!=(n,):raise ValueError('Protected mask must bool')
    active=original.mask;dp=np.linalg.norm(candidate.position-original.position,axis=1);dr=np.array([Rotation.from_matrix(a.T@b).magnitude() for a,b in zip(original.rotation,candidate.rotation)]);dw=abs(candidate.width-original.width)
    frozen=protected|~active
    violated=active&((dp>translation_m+1e-12)|(dr>rotation_rad+1e-12)|(dw>width_m+1e-12))
    violated|=frozen&((dp>1e-12)|(dr>1e-12)|(dw>1e-12))
    return {'status':'FAIL' if violated.any() else 'PASS','violating_nodes':np.flatnonzero(violated).tolist(),'original_sha256':original.digest,'candidate_sha256':candidate.digest,'scope':'NODE_REFERENCE_BUDGET_ONLY_CONTINUOUS_TASK_NOT_CERTIFIED'}
