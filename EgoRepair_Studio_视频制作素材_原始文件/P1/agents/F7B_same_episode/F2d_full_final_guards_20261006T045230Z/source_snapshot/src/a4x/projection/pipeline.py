"""Composed fixed-frame F1→SO101 M5 recipe. M6 remains a separate consumer."""
import numpy as np
from scipy.spatial.transform import Rotation
from .f1_target import FixedFrameF1Target
from .solver import project
from .continuous import qualify,ContinuousProfile,real
from .task import qualify_task

def _rejected(status,reason,target=None):
    return {'status':status,'reason':reason,'eef_retained':True,'C_raw_nn':{'source_ref':getattr(target,'source_ref',None),'recipe_sha256':getattr(target,'immutable_digest',None),'valid_EEF':'SOURCE_ARTIFACT_RETAINED'},'C_projected':{'status':status,'q':None},'C_executed':{'status':'NOT_RUN'}}

def project_recipe(adapter,target,t,parent_q,oracle,*,translation_cap_m,rotation_cap_rad,width_cap_m,velocity_limits,acceleration_limits,profile=ContinuousProfile(),solver_budget=None,task_profile=None):
    from .moving_target import MovingFrameF1Target
    if type(target) not in (FixedFrameF1Target,MovingFrameF1Target):return _rejected('NOT_READY','CONTINUOUS_REFERENCE_RECIPE_UNSUPPORTED',target)
    from .distance import NativeDistance
    if type(oracle) is not NativeDistance:return _rejected('NOT_READY','UNREGISTERED_DISTANCE_ORACLE',target)
    if adapter.profile.get('robot')!='SO101' or adapter.profile.get('tcp')!='official gripperframe':return _rejected('NOT_READY','MODEL_TOOL_MAPPING_UNSUPPORTED',target)
    other=7 if target.hand==0 else 0
    if np.any(target.effective[:,other:other+7]!=0):return _rejected('OUT_OF_REPRESENTATION','OTHER_ARM_REQUIRES_SEPARATE_BOUND_MODEL_AND_JOINT_PROJECTION',target)
    caps=[float(real(x)) for x in [translation_cap_m,rotation_cap_rad,width_cap_m]]
    if target.source_caps is not None and tuple(caps)!=target.source_caps:return _rejected('OUT_OF_PROFILE','ORIGINAL_SOURCE_PARENT_CAPS_CHANGED',target)
    if any(x<0 for x in caps):raise ValueError('Negative parent cap')
    # Convex hull of projected coefficients and exact C2 envelope in [0,1].
    # Rotation uses right SO3 exp; opening clamp is nonexpansive if baseline in range.
    if max(target.D)>caps[0] or target.br>caps[1] or target.bw>caps[2] or not target.width_limits[0]<=target.w<=target.width_limits[1]:return _rejected('OUT_OF_PROFILE','ORIGINAL_BASELINE_TRUST_BUDGET',target)
    t=real(t);parent=real(parent_q)
    if isinstance(target,MovingFrameF1Target) and not np.array_equal(t,target.source_time):return _rejected('OUT_OF_PROFILE','SOURCE_CLOCK_REWRITE_FORBIDDEN',target)
    if target.pose_mask.shape!=(len(t),2) or target.width_mask.shape!=(len(t),):raise ValueError('Source component mask clock mismatch')
    if not target.pose_mask.all() or not target.width_mask.all():return _rejected('NOT_READY_PARTIAL_COMPONENT_TARGET','NO_FAKE_ORIENTATION_OR_TOOL_FROM_MISSING_COMPONENTS',target)
    rows=[target(x) for x in t]
    raw={'position':np.array([x[0] for x in rows]),'rotation':np.array([x[1] for x in rows]),'width':np.array([x[2] for x in rows]),'source_clock':t.copy(),'target_sha256':target.immutable_digest,'effective_coefficients':target.effective.copy(),'raw_coefficients_ref':target.source_ref,'inactive_nonfinite_raw_count':int(np.sum(~np.isfinite(target.z)&~target.mask)),'pose_mask':target.pose_mask.copy(),'width_mask':target.width_mask.copy()}
    clock=None;task_target=target
    if np.any(target.effective[:,14]>0):
        if not target.retiming_allowed:return _rejected('OUT_OF_PROFILE','GLOBAL_RETIMING_NOT_AUTHORIZED',target)
        from a4x.repair.math import CommonRetiming
        from .retiming import RetimedF1Target
        clock=CommonRetiming(np.linspace(target.a,target.b,32),target.effective[:,14],allowed=True);task_target=RetimedF1Target(target,clock)
    projected=project(adapter,t,raw['position'],raw['rotation'],raw['width'],parent,velocity_limits=velocity_limits,acceleration_limits=acceleration_limits,geometry_oracle=oracle,task_curve=target,common_clock=clock,tool_semantics=target.tool_semantics,budget=solver_budget)
    from .tool import compile_gp,task_fk
    tool_rows=[compile_gp(adapter,float(width),target.tool_semantics) for width in raw['width']] if projected['status']=='PROJECTED_REFERENCE_ONLY' else []
    output={'C_raw_nn':raw,'C_projected':projected,'C_executed':{'status':'NOT_RUN'},'source_sha256':target.source,'tool_mapping':{'semantics':target.tool_semantics,'P':'official native gripperframe','per_node':tool_rows,'opening':'native tip surface distance; not physical pad gap'},'hardware':'NOT_VALIDATED','original_baseline_budget':'PASS_BY_BOUNDED_F1_RECIPE','scope':'SYNTHETIC_ANALYTICAL_REFERENCE_MODEL' if target.synthetic_fixture else 'REFERENCE_MODEL_ONLY', 'source_ref':target.source_ref}
    if projected['status']!='PROJECTED_REFERENCE_ONLY':output['status']=projected['status'];return output
    curve=projected['curve'];fk_rows=[adapter.fk(row) for row in projected['q']]
    g_rows=[task_fk(adapter,row,target.tool_semantics) for row in projected['q']];projected['G_position_m']=np.array([row[0] for row in g_rows]);projected['G_rotation']=np.array([row[1] for row in g_rows])
    projected['reference_G_position_m']=raw['position'].copy();projected['reference_G_rotation']=raw['rotation'].copy();projected['reference_opening_m']=raw['width'].copy();projected['reference_curve_sha256']=target.immutable_digest
    projected['fk_position_m']=np.array([row[0] for row in fk_rows]);projected['fk_rotation']=np.array([row[1] for row in fk_rows]);projected['opening_m']=np.array([adapter.opening_m(row) for row in projected['q']])
    physical=qualify(curve,adapter.command_limits,velocity_limits,acceleration_limits,oracle,profile);task=qualify_task(curve,adapter,task_target,**(task_profile or {}))
    output.update(continuous_model=physical,continuous_task=task,common_retiming=None if clock is None else {'source_nodes_s':clock.nodes.tolist(),'control_nodes_s':clock.forward(clock.nodes).tolist(),'kappa_coefficients':clock.kappa.c.tolist(),'gamma':clock.gamma,'duration_cap':2.,'source_time_immutable':True})
    output['status']='FAIL' if 'FAIL' in (physical['status'],task['status']) else 'UNKNOWN' if 'UNKNOWN' in (physical['status'],task['status']) else 'PASS'
    output['qualification_scope']=oracle.scope
    return output
