"""Model-defined G/P tool semantics from native sites/pad geometry only."""
import numpy as np
import mujoco
NATIVE_SITE='SO101_NATIVE_SITE_G_EQUALS_P_V1'
PAD_MIDPOINT='SO101_NATIVE_PAD_MIDPOINT_AXES_P_V1'

def task_fk(adapter,q,semantics):
    position,R=adapter.fk(q)
    if semantics==NATIVE_SITE:return position,R
    if semantics!=PAD_MIDPOINT:raise NotImplementedError('Tool geometry semantic not registered')
    ids=[mujoco.mj_name2id(adapter.model,mujoco.mjtObj.mjOBJ_GEOM,name) for name in ('fixed_jaw_box4','moving_jaw_box2')]
    if min(ids)<0:raise ValueError('Native model pad geometry absent')
    return adapter._fk_data.geom_xpos[ids].mean(axis=0).copy(),R

def compile_gp(adapter,width,semantics):
    gripper=adapter.opening_to_joint(width);q=np.mean(adapter.command_limits,axis=1);q[adapter.gripper_index]=gripper
    P,R=adapter.fk(q);G,_=task_fk(adapter,q,semantics);T_PG=np.eye(4);T_PG[:3,3]=R.T@(G-P);T_GP=np.eye(4);T_GP[:3,3]=-T_PG[:3,3]
    return {'T_PG':T_PG,'T_GP':T_GP,'gripper_joint_rad':gripper,'G_axes':'NATIVE_P_AXES','G_origin':semantics,'opening':'NATIVE_TIP_SURFACE_DISTANCE_NONNEGATIVE_HINGE_BRANCH','qualification':'MODEL_GEOMETRY_NOT_MEASURED_CONTACT_PATCH'}

def opening_joint(adapter,width,counter=None):
    """Same native gap/branch as frozen adapter, with exact query accounting."""
    from scipy.optimize import brentq
    from .continuous import real
    width=float(real(width));q=np.mean(adapter.limits,axis=1);g=adapter.gripper_index;lo=max(0.,adapter.command_limits[g,0]);hi=adapter.command_limits[g,1]
    def gap(value):
        q[g]=value
        if counter is not None:counter()
        return adapter.opening_m(q)
    a,b=gap(lo),gap(hi)
    if not min(a,b)<=width<=max(a,b):raise ValueError('Native model opening unsupported')
    return float(brentq(lambda value:gap(value)-width,lo,hi,maxiter=100))
