"""Explicit source-bound model-reference object motion, never physics evidence."""
import hashlib,json
from pathlib import Path
import numpy as np
from a4x.provenance import verify_artifact
from .continuous import JointCurve,real
from scipy.spatial.transform import Rotation,RotationSpline
from .moving_target import derivative_bound
class ObjectMotion:
    def __init__(self,joint_name,time_s,position_m,quaternion_wxyz,source_ref):
        self.joint_name=str(joint_name);self.curve=JointCurve(time_s,position_m);self.quaternion=real(quaternion_wxyz)
        if self.quaternion.shape not in ((4,),(len(self.curve.t),4)):raise ValueError('Object quaternion shape')
        if self.curve.q.shape[1]!=3 or not np.allclose(np.linalg.norm(self.quaternion,axis=-1),1,atol=1e-8):raise ValueError('Invalid object model-reference motion')
        self.rotation_curve=None if self.quaternion.shape==(4,) else RotationSpline(self.curve.t,Rotation.from_quat(self.quaternion[:,[1,2,3,0]]))
        self.ref=dict(source_ref);self.root=Path(__file__).resolve().parents[3];path=verify_artifact(self.ref,[self.root])
        if path.suffix=='.npz':
            with np.load(path,allow_pickle=False) as data:record={k:data[k].copy() for k in ('object_motion_joint','object_motion_time_s','object_motion_position_m','object_motion_quaternion_wxyz','object_motion_kind','object_motion_frame')}
        else:record=json.loads(path.read_text())
        if str(record['object_motion_kind'])!='SOURCE_DEFINED_MODEL_REFERENCE_NOT_M6_ACTUAL_MOTION' or str(record['object_motion_frame'])!='WORLD_METRE' or str(record['object_motion_joint'])!=self.joint_name or not np.array_equal(real(record['object_motion_time_s']),self.curve.t) or not np.array_equal(real(record['object_motion_position_m']),self.curve.q) or not np.array_equal(real(record['object_motion_quaternion_wxyz']),self.quaternion):raise ValueError('Object curve not bound to actual source bytes')
        self.digest=self._digest();self.qualification='SOURCE_DEFINED_MODEL_REFERENCE_NOT_M6_ACTUAL_MOTION'
    def _digest(self):
        verify_artifact(self.ref,[self.root]);return hashlib.sha256(self.curve.digest.encode()+self.curve.spline.c.tobytes()+self.quaternion.tobytes()+(b'' if self.rotation_curve is None else self.rotation_curve.interpolator.c.tobytes()+self.rotation_curve.interpolator.x.tobytes()+self.rotation_curve.rotations.as_quat().tobytes()+repr((self.rotation_curve.interpolator.axis,self.rotation_curve.interpolator.extrapolate,self.rotation_curve.times.tolist())).encode())+repr((self.ref,self.joint_name)).encode()).hexdigest()
    def pose(self,time_s):
        if self._digest()!=self.digest:raise ValueError('OBJECT_CURVE_DRIFT')
        if not self.curve.t[0]<=time_s<=self.curve.t[-1]:raise ValueError('OBJECT_CLOCK_OUTSIDE_SUPPORT')
        quaternion=self.quaternion
        if self.rotation_curve is not None:
            xyzw=self.rotation_curve(time_s).as_quat();quaternion=xyzw[[3,0,1,2]]
        return np.r_[self.curve(time_s),quaternion]
    def motion_bound(self,a,b):
        if self._digest()!=self.digest:raise ValueError('OBJECT_CURVE_DRIFT')
        lo,hi=self.curve.bounds(a,b,1);return (b-a)/2*float(np.linalg.norm(np.maximum(abs(lo),abs(hi))))

    def angular_bound(self,a,b):
        if self._digest()!=self.digest:raise ValueError('OBJECT_CURVE_DRIFT')
        return 0. if self.rotation_curve is None else (b-a)/2*derivative_bound(self.rotation_curve.interpolator,a,b)
