"""CPU bounded M5 on an explicit immutable NPZ reference recipe (not LeRobot)."""
import argparse,json,hashlib,shutil,time
from pathlib import Path
import numpy as np
from a4x.provenance import artifact_ref,verify_artifact
from a4x.robot.so101 import SO101Adapter
from a4x.sim.environment import SO101Env
from a4x.projection.moving_target import MovingFrameF1Target
from a4x.projection.pipeline import project_recipe
from a4x.projection.continuous import JointCurve,qualify
from a4x.projection.distance import NativeDistance,native_pairs

def main():
    started=time.monotonic();ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--output',required=True);ap.add_argument('--profile',choices=['RESTRICTED_DEVELOPMENT','FULL_EPISODE_DEVELOPMENT'],default='RESTRICTED_DEVELOPMENT');ap.add_argument('--contact-source');args=ap.parse_args()
    if args.profile=='FULL_EPISODE_DEVELOPMENT':
        from projection_full_preflight import main as full_main
        return full_main()
    root=Path(__file__).resolve().parents[1];path=Path(args.input).resolve();ref=artifact_ref(path);verify_artifact(ref,[root]);out=Path(args.output).resolve()
    if not out.is_relative_to(root) or out.is_symlink():raise ValueError('Output outside project')
    out.mkdir(parents=True,exist_ok=False)
    snapshot=out/'source_snapshot';snapshot.mkdir()
    source_files=list((root/'src/a4x/projection').glob('*.py'))+[root/'tools/projection_run.py',root/'src/a4x/repair/math.py',root/'src/a4x/robot/adapter.py',root/'src/a4x/robot/so101.py',root/'src/a4x/sim/environment.py',root/'src/a4x/sim/tasks.py',root/'src/a4x/provenance.py']
    snapshot_refs=[]
    for source in source_files:
        target=snapshot/source.relative_to(root);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target);snapshot_refs.append(artifact_ref(target))
    (snapshot/'SourceSnapshot.json').write_text(json.dumps(snapshot_refs,indent=2))
    with np.load(path,allow_pickle=False) as d:
        required={'time_s','position_m','rotation','opening_m','F_world','D_m','beta_rotation_rad','beta_width_m','z','edit_mask','parent_q_rad','translation_cap_m','rotation_cap_rad','width_cap_m','pose_mask','width_mask','retiming_allowed','tool_semantics','episode_bounds_s'}
        if not required.issubset(d.files):raise ValueError('Missing explicit reference fields')
        x={k:d[k].copy() for k in required}
        object_keys={'object_motion_joint','object_motion_time_s','object_motion_position_m','object_motion_quaternion_wxyz','object_motion_kind','object_motion_frame'}
        if object_keys&set(d.files) and not object_keys.issubset(d.files):raise ValueError('Incomplete object registration')
        object_data={k:d[k].copy() for k in object_keys} if object_keys.issubset(d.files) else None
    target=MovingFrameF1Target(source_time=x['time_s'],position_nodes=x['position_m'],rotation_nodes=x['rotation'],width_nodes=x['opening_m'],frame_nodes=x['F_world'],bounds=x['episode_bounds_s'],D=x['D_m'],rotation_cap=x['beta_rotation_rad'],width_cap=x['beta_width_m'],z=x['z'],edit_mask=x['edit_mask'],source_sha256=ref['sha256'],source_ref=ref,pose_mask=x['pose_mask'],width_mask=x['width_mask'],retiming_allowed=x['retiming_allowed'].item(),tool_semantics=str(x['tool_semantics']))
    robot=SO101Adapter.load();oracle=NativeDistance(robot,pairs=native_pairs(robot.model),scope='SO101_NATIVE_SELF_TOOL')
    result=project_recipe(robot,target,x['time_s'],x['parent_q_rad'],oracle,translation_cap_m=x['translation_cap_m'],rotation_cap_rad=x['rotation_cap_rad'],width_cap_m=x['width_cap_m'],velocity_limits=np.full(6,3.),acceleration_limits=np.full(6,100.))
    # Full immutable scenario scope is a separate gate. Free object's continuous
    # motion is not inferred from a sampled state or an identity reference.
    if result['C_projected']['status']=='PROJECTED_REFERENCE_ONLY':
        env=SO101Env();motions=[]
        if object_data is not None:
            from a4x.projection.object_motion import ObjectMotion
            motions=[ObjectMotion(str(object_data['object_motion_joint']),object_data['object_motion_time_s'],object_data['object_motion_position_m'],object_data['object_motion_quaternion_wxyz'],ref)]
        scene=NativeDistance(env.adapter,pairs=native_pairs(env.model),scope='SCENE_A_SELF_TOOL_TABLE_SOURCE_DEFINED_OBJECT_MODEL_REFERENCE_NOT_M6',fixed_qpos=env.data.qpos,object_motions=motions,allow_scene_a_support=True)
        from a4x.projection.continuous import ContinuousProfile
        result['full_scene_qualification']=qualify(result['C_projected']['curve'],env.adapter.command_limits,np.full(6,3.),np.full(6,100.),scene,ContinuousProfile(max_depth=2,max_distance_calls=5000))
    full=result.get('full_scene_qualification',{'status':'UNKNOWN'})
    result['source_interval_s']=[float(x['time_s'][0]),float(x['time_s'][-1])];result['original_episode_bounds_s']=x['episode_bounds_s'].tolist()
    result['whole_original_episode_covered']=bool(np.array_equal(x['time_s'][[0,-1]],x['episode_bounds_s']))
    result['full_M5_status']='FAIL' if 'FAIL' in (result['status'],full['status']) else 'PASS_MODEL_REFERENCE_ONLY' if result['whole_original_episode_covered'] and result['status']=='PASS' and full['status']=='PASS' else 'UNKNOWN';result['M6_status']='NOT_RUN';result['derivative_limit_source']='DEVELOPMENT_SIM_ASSUMPTION_3_RAD_S_100_RAD_S2_NOT_SDK'
    def serial(v):
        if isinstance(v,np.ndarray):return v.tolist()
        from a4x.projection.retiming import RetimedCurve
        if isinstance(v,RetimedCurve):return {'time_s':v.t.tolist(),'q_rad':v.q.tolist(),'source_time_s':v.source.t.tolist(),'source_coefficients':v.source.spline.c.tolist(),'sha256':v.digest,'clock_gamma':v.clock.gamma,'clock_kappa_coefficients':v.clock.kappa.c.tolist()}
        if isinstance(v,JointCurve):return {'time_s':v.t.tolist(),'q_rad':v.q.tolist(),'coefficients':v.spline.c.tolist(),'sha256':v.digest}
        if isinstance(v,dict):return {k:serial(x) for k,x in v.items()}
        if isinstance(v,(tuple,list)):return [serial(x) for x in v]
        if isinstance(v,np.bool_):return bool(v)
        if isinstance(v,(np.integer,np.floating)):return v.item()
        return v
    (out/'Result.json').write_text(json.dumps(serial(result),indent=2,allow_nan=False))
    refs={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'src/a4x/projection').glob('*.py')}
    (out/'Receipt.json').write_text(json.dumps({'input':ref,'output':artifact_ref(out/'Result.json'),'source_sha256':refs,'source_snapshot':artifact_ref(snapshot/'SourceSnapshot.json'),'source_snapshot_files':snapshot_refs,'elapsed_seconds':time.monotonic()-started,'candidate_origin':'EXPLICIT_NPZ_COEFFICIENTS_NOT_ASSUMED_NEURAL','command_profile':'REFERENCE_CURVE_NOT_M6_CONTROLLER','source_materialization':robot.profile},indent=2))
    print(json.dumps({'restricted_status':result['status'],'full_M5_status':result['full_M5_status'],'output':str(out)}))
if __name__=='__main__':
    try:main()
    except Exception as exc:
        import sys
        if '--output' in sys.argv:
            output=Path(sys.argv[sys.argv.index('--output')+1]).resolve();root=Path(__file__).resolve().parents[1]
            if output.is_relative_to(root) and output.is_dir():
                receipt=output/'FailureReceipt.json'
                with receipt.open('x') as stream:json.dump({'status':'UNKNOWN_UNPUBLISHED_RESULT','exception_type':type(exc).__name__,'M6_steps':0,'GPU_or_API_calls':0,'query_cost':'UNKNOWN_NOT_REFUNDED','source_snapshot':str(output/'source_snapshot/SourceSnapshot.json')},stream,indent=2)
        raise
