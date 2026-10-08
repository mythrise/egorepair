"""Whole-original-episode native parent diagnostics, additive to accepted M5.

This executable does not assert that parent feasibility is an optimization result.
It reports independent continuous task and scene failures, preserving source EEF.
"""
import argparse, hashlib, json, time, shutil
from pathlib import Path
import numpy as np
import mujoco
from a4x.projection.continuous import JointCurve, ContinuousProfile, qualify
from a4x.projection.distance import NativeDistance, native_pairs
from a4x.projection.moving_target import MovingFrameF1Target
from a4x.projection.task import qualify_task
from a4x.projection.object_motion import ObjectMotion
from a4x.provenance import artifact_ref,verify_artifact
from a4x.sim.environment import SO101Env

def _main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--output',required=True);ap.add_argument('--profile',choices=['FULL_EPISODE_DEVELOPMENT'],default='FULL_EPISODE_DEVELOPMENT');ap.add_argument('--contact-source');ap.add_argument('--gate',choices=['all','task','scene'],default='all');args=ap.parse_args()
    root=Path(__file__).resolve().parents[1];source=Path(args.input).resolve();out=Path(args.output).resolve()
    if not source.is_relative_to(root) or not out.is_relative_to(root):raise ValueError('Outside project')
    out.mkdir(parents=True,exist_ok=False);start=time.monotonic()
    native_queries={'forward':0,'distance':0};native_forward=mujoco.mj_forward;native_distance=mujoco.mj_geomDistance
    def counted_forward(*a,**kw):
        if native_queries['forward']>=profile['solver']['max_fk_calls']:raise RuntimeError('AGGREGATE_NATIVE_FORWARD_BUDGET_EXHAUSTED')
        if time.monotonic()-start>=profile['aggregate_wall_s']:raise RuntimeError('AGGREGATE_WALL_BUDGET_EXHAUSTED')
        native_queries['forward']+=1;return native_forward(*a,**kw)
    def counted_distance(*a,**kw):
        if time.monotonic()-start>=profile['aggregate_wall_s']:raise RuntimeError('AGGREGATE_WALL_BUDGET_EXHAUSTED')
        if native_queries['distance']>=profile['continuous']['max_distance_calls']+profile['solver']['max_distance_calls']:raise RuntimeError('AGGREGATE_NATIVE_DISTANCE_BUDGET_EXHAUSTED')
        native_queries['distance']+=1;return native_distance(*a,**kw)
    mujoco.mj_forward=counted_forward;mujoco.mj_geomDistance=counted_distance
    profile_path=root/'protocols/full_episode_development_m5.json';profile=json.loads(profile_path.read_text());ref=artifact_ref(source)
    snapshot=out/'source_snapshot';snapshot.mkdir();source_refs=[]
    for producer in list((root/'src/a4x/projection').glob('*.py'))+[Path(__file__).resolve(),root/'tools/projection_run.py',profile_path,root/'src/a4x/repair/math.py',root/'src/a4x/robot/so101.py',root/'src/a4x/robot/adapter.py',root/'src/a4x/sim/environment.py',root/'src/a4x/sim/gates.py',root/'src/a4x/provenance.py']:
        copied=snapshot/producer.relative_to(root);copied.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(producer,copied);source_refs.append(artifact_ref(copied))
    (out/'SourceSHA.json').write_text(json.dumps(source_refs,indent=2))
    with np.load(source,allow_pickle=False) as data:d={k:data[k].copy() for k in data.files}
    t=d['time_s'];bounds=d['episode_bounds_s']
    if not np.array_equal(t[[0,-1]],bounds):raise ValueError('Whole original episode required')
    target=MovingFrameF1Target(source_time=t,position_nodes=d['position_m'],rotation_nodes=d['rotation'],width_nodes=d['opening_m'],frame_nodes=d['F_world'],bounds=bounds,D=d['D_m'],rotation_cap=d['beta_rotation_rad'],width_cap=d['beta_width_m'],z=d['z'],edit_mask=d['edit_mask'],source_sha256=ref['sha256'],source_ref=ref,pose_mask=d['pose_mask'],width_mask=d['width_mask'],retiming_allowed=d['retiming_allowed'].item(),tool_semantics=str(d['tool_semantics']))
    if not d['pose_mask'].all() or not d['width_mask'].all():raise ValueError('Partial task components require separate EEF retained NOT_READY route')
    if np.any(target.effective[:,7:15]):raise ValueError('Other arm or retiming not supported by fixed native parent warm start')
    if max(target.D)>float(d['translation_cap_m']) or target.br>float(d['rotation_cap_rad']) or target.bw>float(d['width_cap_m']):raise ValueError('Original source modification caps exceeded')
    curve=JointCurve(t,d['parent_q_rad'])
    from a4x.projection.full_episode_bounds import accelerate
    accelerate(curve,target)
    env=SO101Env();motions=[]
    if 'object_motion_joint' in d:
        motions=[ObjectMotion(str(d['object_motion_joint']),d['object_motion_time_s'],d['object_motion_position_m'],d['object_motion_quaternion_wxyz'],ref)]
    contract=None
    if args.contact_source:
        from a4x.projection.contact_contract import SourceContactContract
        contract=SourceContactContract(artifact_ref(Path(args.contact_source).resolve()),env.model,root,bounds)
        contact_lineage=contract.bind_recipe(d)
    oracle=NativeDistance(env.adapter,pairs=native_pairs(env.model),scope='FULL_EPISODE_SCENE_A_SOURCE_DEFINED_OBJECT_MODEL_REFERENCE_NOT_M6',fixed_qpos=env.data.qpos,object_motions=motions,allow_scene_a_support=True,contact_contract=contract,first_separating_axis=True)
    from a4x.projection.full_episode_bounds import tighten_native_ancestor_bounds
    tighten_native_ancestor_bounds(oracle)
    from a4x.projection.full_episode_bounds import seal_owned_native_model,verify_owned_native_model_seal
    model_seal=seal_owned_native_model(oracle)
    continuous_args=dict(profile['continuous']);continuous_args['max_wall_s']=min(continuous_args['max_wall_s'],max(0.,profile['aggregate_wall_s']-(time.monotonic()-start)))
    physical=qualify(curve,env.adapter.command_limits,np.full(6,3.),np.full(6,100.),oracle,ContinuousProfile(**continuous_args)) if args.gate!='task' else {'status':'NOT_RUN','distance_calls':0}
    # Persist real geometry evidence before potentially costly independent task gate.
    model_seal.update(verify_owned_native_model_seal(oracle))
    if contract is not None:verify_artifact(contract.source_ref,[root])
    verify_artifact(ref,[root]);physical['owned_model_seal']=model_seal
    (out/'Physical.json').write_text(json.dumps(physical,indent=2,allow_nan=False))
    task_args=dict(profile['task']);task_args['max_wall_s']=min(task_args['max_wall_s'],max(0.,profile['aggregate_wall_s']-(time.monotonic()-start)))
    task=qualify_task(curve,env.adapter,target,**task_args) if args.gate!='scene' else {'status':'NOT_RUN','fk_calls':0}
    result={'status':'FAIL' if 'FAIL' in (physical['status'],task['status']) else 'UNKNOWN' if 'UNKNOWN' in (physical['status'],task['status']) else 'PARENT_WARM_START_CONTINUOUS_MODEL_FEASIBLE' if args.gate=='all' else 'PARTIAL_GATE_DIAGNOSTIC_ONLY','whole_original_episode_covered':True,'source_interval_s':t[[0,-1]].tolist(),'states':len(t),'continuous_model':physical,'continuous_task':task,'M6_status':'NOT_RUN','neural_repair':'NOT_CLAIMED','optimization':'NOT_RUN_DIAGNOSTIC_ONLY','source':ref,'source_snapshot':artifact_ref(out/'SourceSHA.json'),'contact_source':None if contract is None else contract.source_ref,'profile':artifact_ref(snapshot/profile_path.relative_to(root)),'gate':args.gate,'elapsed_s':time.monotonic()-start,'cost':{'native_distance_calls':oracle.actual_distance_calls,'scene_native_forward_calls':oracle.forward_calls,'task_native_forward_calls':2*task['fk_calls']},'EEF_retained':True}
    rows=[target(float(value)) for value in t]
    from a4x.projection.tool import task_fk
    from scipy.spatial.transform import Rotation
    residuals=[]
    for q,row in zip(curve.q,rows):
        p,R=task_fk(env.adapter,q,target.tool_semantics);w=env.adapter.opening_m(q)
        residuals.append([float(np.linalg.norm(p-row[0])),float(Rotation.from_matrix(row[1].T@R).magnitude()),float(abs(w-row[2]))])
    result['cost']['node_diagnostic_native_forward_calls']=2*len(t)
    result['cost']['native_forward_calls_total']=native_queries['forward'];result['cost']['native_geomDistance_calls_total']=native_queries['distance']
    result['cost']['setup_native_forward_calls']=native_queries['forward']-result['cost']['scene_native_forward_calls']-result['cost']['task_native_forward_calls']-2*len(t)
    result['cost']['fk_calls']=native_queries['forward'];result['cost']['ik_calls']=0;result['cost']['sqp_iterations']=0;result['cost']['distance_calls']=native_queries['distance']
    result['contact_source_lineage']=None if contract is None else contact_lineage
    result['parent_warm_start_deltas']={'q_delta_rad_max':0.,'raw_task_vs_native_parent_residuals_m_rad_m':residuals,'effective_coefficient_norm':float(np.linalg.norm(target.effective)),'intended_nonzero_correction_applied':False,'objective_optimality_claimed':False,'global_infeasibility_proven':False}
    admitted=args.gate=='all' and physical['status']=='PASS' and task['status']=='PASS'
    result.update(status='PASS' if admitted else 'FAIL' if 'FAIL' in (physical['status'],task['status']) else 'UNKNOWN',full_M5_status='PASS_MODEL_REFERENCE_ONLY' if admitted else 'FAIL' if 'FAIL' in (physical['status'],task['status']) else 'UNKNOWN',C_raw_nn={'position':[r[0].tolist() for r in rows],'rotation':[r[1].tolist() for r in rows],'width':[float(r[2]) for r in rows],'source_clock':t.tolist(),'target_sha256':target.immutable_digest},C_projected={'status':'PROJECTED_REFERENCE_ONLY','q':curve.q.tolist(),'curve':{'time_s':curve.t.tolist(),'q_rad':curve.q.tolist(),'coefficients':curve.spline.c.tolist(),'sha256':curve.digest},'cost':result['cost'],'solver_exit':'SOURCE_NATIVE_PARENT_WARM_START_FEASIBILITY_GATE_NOT_OPTIMUM'},C_executed={'status':'NOT_RUN'},full_scene_qualification=physical,common_retiming=None)
    verify_artifact(ref,[root])
    if contract is not None:verify_artifact(contract.source_ref,[root])
    verify_owned_native_model_seal(oracle)
    for producer_ref in source_refs:verify_artifact(producer_ref,[root])
    (out/'Result.json').write_text(json.dumps(result,indent=2,allow_nan=False));(out/'Receipt.json').write_text(json.dumps({'input':ref,'output':artifact_ref(out/'Result.json'),'source_snapshot_files':source_refs,'source_snapshot':artifact_ref(out/'SourceSHA.json'),'profile':result['profile'],'contact_source':result['contact_source'],'elapsed_seconds':result['elapsed_s'],'candidate_origin':'SOURCE_NATIVE_PARENT_WARM_START_NOT_NEURAL_OPTIMIZATION'},indent=2));print(json.dumps({'status':result['status'],'physical':physical['status'],'task':task['status'],'elapsed_s':result['elapsed_s']}))
def main():
    forward,distance=mujoco.mj_forward,mujoco.mj_geomDistance
    try:return _main()
    finally:mujoco.mj_forward=forward;mujoco.mj_geomDistance=distance

if __name__=='__main__':main()
