"""Typed composition adapters; no changes to frozen F2 model adapters."""
from dataclasses import dataclass
from typing import Protocol
import numpy as np
from .continuous import real
from .distance import NativeDistance,native_pairs

@dataclass(frozen=True)
class RobotCapability:
    name:str
    status:str
    active_arm_dof:int|None
    full_dof:int|None
    six_dof_orientation_guaranteed:bool
    source:str

CAPABILITIES={
    'SO101':RobotCapability('SO101','READY_MODEL_REFERENCE',5,6,False,'PINNED_OFFICIAL_MENAGERIE'),
    'A1X':RobotCapability('A1X','NOT_READY_ASSETS_AND_TYPED_TOOL_MAPPING_REQUIRED',None,None,False,'NOT_MATERIALIZED_FOR_THIS_PROJECTION'),
    'ALLEX':RobotCapability('ALLEX','NOT_READY_ASSETS_AND_TYPED_TOOL_MAPPING_REQUIRED',None,None,False,'NOT_MATERIALIZED_FOR_THIS_PROJECTION'),
}
class ProjectionRobot(Protocol):
    def fk(self,q):...
    def task_error(self,q,target):...
    def limits(self):...
    def geometry(self,q):...
    def compile_tool(self,width_m):...
    def simulate(self,command):...

class SO101ProjectionAdapter:
    """G is explicitly the official site P, not a pad or calibrated physical TCP."""
    def __init__(self,native):
        if native.profile.get('robot')!='SO101' or native.profile.get('tcp')!='official gripperframe':raise ValueError('Wrong native model/tool')
        self.native=native;self.capability=CAPABILITIES['SO101'];self.oracle=NativeDistance(native,pairs=native_pairs(native.model),scope='NATIVE_SELF_TOOL')
    def fk(self,q):return self.native.fk(real(q,(6,)))
    def task_error(self,q,target):
        from scipy.spatial.transform import Rotation
        p,R=self.fk(q);tp,tR=target
        return np.r_[p-real(tp,(3,)),Rotation.from_matrix(real(tR,(3,3)).T@R).as_rotvec()]
    def limits(self):return {'joint_position_rad':self.native.command_limits.copy(),'source':'OFFICIAL_JOINT_AND_ACTUATOR_INTERSECTION','velocity':'NEEDS_DECLARED_PROFILE_NOT_HARDWARE_DEFAULT','acceleration':'NEEDS_DECLARED_PROFILE_NOT_HARDWARE_DEFAULT','mimic':'NONE_NATIVE_MODEL','q_full_mapping':'IDENTITY'}
    def geometry(self,q):return self.oracle.distances(real(q,(6,)))
    def compile_tool(self,width_m):
        width=float(real(width_m));joint=self.native.opening_to_joint(width)
        return {'T_GP':np.eye(4),'G':'OFFICIAL_MODEL_REFERENCE_GRIPPERFRAME','P':'SAME_NATIVE_SITE','gripper_joint_rad':joint,'width_m':width,'mapping':'NATIVE_TIP_SURFACE_DISTANCE_NOT_PAD_GAP','hardware':'NOT_VALIDATED'}
    def simulate(self,command):raise NotImplementedError('M6_REQUIRES_SEPARATE_FROZEN_UNASSISTED_ENVIRONMENT')

def capability(name):return CAPABILITIES.get(name,RobotCapability(str(name),'NOT_READY_UNREGISTERED_MODEL',None,None,False,'NONE'))
