"""Adaptive FK/reference residual qualification with explicit trusted curve bounds."""
import time
import numpy as np
from scipy.spatial.transform import Rotation

def qualify_task(curve,adapter,target,position_tolerance=.002,rotation_tolerance=.035,width_tolerance=.0001,max_depth=14,max_calls=10000,fail_fast=False,max_wall_s=None,native_opening_bound=False):
    """target(t)->(p,R,w), target.bounds(a,b)->(p_motion,R_motion,w_motion).

    Bounds are whole-interval supremum displacement from midpoint, not samples.
    Missing trusted bounds yields UNKNOWN rather than task acceptance.
    """
    from .f1_target import FixedFrameF1Target
    from .moving_target import MovingFrameF1Target
    from .retiming import RetimedF1Target
    if type(target) not in (FixedFrameF1Target,MovingFrameF1Target,RetimedF1Target):return {'status':'UNKNOWN','reason':'UNREGISTERED_TASK_BOUND_RECIPE'}
    from .continuous import real
    position_tolerance=float(real(position_tolerance));rotation_tolerance=float(real(rotation_tolerance));width_tolerance=float(real(width_tolerance))
    if min(position_tolerance,rotation_tolerance,width_tolerance)<=0 or any(isinstance(x,bool) or not isinstance(x,int) or x<0 for x in (max_depth,max_calls)):raise ValueError('Invalid task profile')
    if not getattr(target,'immutable_digest',None) or not callable(getattr(target,'bounds',None)):return {'status':'UNKNOWN','reason':'TRUSTED_REFERENCE_BOUNDS_MISSING'}
    stack=[(curve.t[0],curve.t[-1],0)];calls=0;unknown=[];fail=[];started=time.monotonic()
    if not isinstance(fail_fast,bool) or (max_wall_s is not None and (isinstance(max_wall_s,bool) or not np.isfinite(max_wall_s) or max_wall_s<0)):raise ValueError("Invalid task execution budget")
    # Conservative serial hinge FK lever bound by model triangle inequalities.
    m=adapter.model;radius=sum(np.linalg.norm(x) for x in m.body_pos)+sum(2*np.linalg.norm(x) for x in m.jnt_pos)+np.linalg.norm(m.site_pos[adapter.site_id])+max(np.linalg.norm(x) for x in m.geom_pos)
    opening_radius=None
    if native_opening_bound:
        from .source_geometry import verify_native_robot,verify_adapter_bindings
        verify_adapter_bindings(adapter);verify_native_robot(m)
        fixed,moving=adapter.tip_ids;j=adapter.joint_ids[adapter.gripper_index];body=int(m.jnt_bodyid[j])
        if int(m.geom_bodyid[moving])!=body or int(m.geom_bodyid[fixed])!=int(m.body_parentid[body]) or int(m.body_jntnum[body])!=1:raise ValueError('Native opening relative hinge recipe unsupported')
        opening_radius=float(np.linalg.norm(m.geom_pos[moving]-m.jnt_pos[j]))
    while stack:
        a,b,depth=stack.pop();mid=(a+b)/2
        if max_wall_s is not None and time.monotonic()-started>=max_wall_s:
            unknown.append((float(a),float(b),"TASK_WALL_BUDGET"));break
        if calls>=max_calls:unknown.append((float(a),float(b),'TASK_BUDGET'));continue
        from .tool import task_fk
        semantics=target.source.tool_semantics if isinstance(target,RetimedF1Target) else target.tool_semantics
        q=curve(mid);p,R=task_fk(adapter,q,semantics);tp,tR,tw=target(mid);calls+=1
        pe=np.linalg.norm(p-tp);re=Rotation.from_matrix(tR.T@R).magnitude();we=abs(adapter.opening_m(q)-tw)
        if pe>position_tolerance or re>rotation_tolerance or we>width_tolerance:
            fail.append(float(mid))
            if fail_fast:break
            continue
        lo,hi=curve.bounds(a,b,1);motion=(b-a)/2*np.maximum(abs(lo),abs(hi));arm=np.sum(motion[adapter.arm_indices]);gp=radius*np.sum(motion);gr=arm
        try:bp,br,bw=target.bounds(a,b)
        except (ValueError,NotImplementedError):unknown.append((float(a),float(b),'REFERENCE_BOUND_UNAVAILABLE'));continue
        # Opening gap is the distance between two native surfaces; each endpoint motion bounded.
        gw=2*radius*np.sum(motion) if opening_radius is None else opening_radius*motion[adapter.gripper_index]
        if pe+gp+bp<=position_tolerance and re+gr+br<=rotation_tolerance and we+gw+bw<=width_tolerance:continue
        if depth>=max_depth:unknown.append((float(a),float(b),'TASK_LOWER_BOUND_UNRESOLVED'))
        else:stack.extend([(a,mid,depth+1),(mid,b,depth+1)])
    return {'status':'FAIL' if fail else 'UNKNOWN' if unknown else 'PASS','failure_times_s':fail,'unknown_intervals':unknown,'fk_calls':calls,'native_forward_calls':2*calls,'wall_s':time.monotonic()-started,'reference_sha256':target.immutable_digest,'curve_sha256':curve.digest,'opening_motion_bound':'GENERIC_ALL_JOINT_TRIANGLE' if opening_radius is None else 'NATIVE_RELATIVE_SINGLE_HINGE_RADIUS','opening_hinge_radius_m':opening_radius,'scope':'CONTINUOUS_MODEL_G_TASK_ONLY','position_tolerance_m':position_tolerance,'rotation_tolerance_rad':rotation_tolerance,'width_tolerance_m':width_tolerance}
