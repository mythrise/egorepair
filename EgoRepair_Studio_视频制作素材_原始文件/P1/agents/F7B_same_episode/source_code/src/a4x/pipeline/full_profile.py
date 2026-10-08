"""Import reviewed full-episode gates/profile without rewriting numerical helpers."""
import json,time
from pathlib import Path
import numpy as np
from a4x.paths import WORKSPACE
from a4x.provenance import verify_artifact,artifact_ref
from .packages import INPUT_ROOTS
NAME='FULL_EPISODE_DEVELOPMENT'

def read_receipt_profile(receipt,source_ref):
    ref=receipt.get('profile');contact=receipt.get('contact_source')
    if ref is None:return None
    profile=json.loads(verify_artifact(ref,INPUT_ROOTS).read_text())
    if profile.get('name')!=NAME:raise ValueError('Unregistered full-episode profile')
    registered=artifact_ref(WORKSPACE/'protocols/full_episode_development_m5.json')
    if ref['sha256']!=registered['sha256']:raise ValueError('Copied numerical profile differs from registered reviewed profile')
    if contact!=source_ref:raise ValueError('Full profile requires exact original source contact binding')
    if not receipt.get('source_snapshot_files'):raise ValueError('Full numerical producer snapshot proof missing')
    for copied in receipt['source_snapshot_files']:
        path=verify_artifact(copied,INPUT_ROOTS);marker='/source_snapshot/'
        if marker not in str(path):raise ValueError('Full producer source snapshot missing')
        relative=Path(str(path).split(marker,1)[1])
        if relative.is_absolute() or '..' in relative.parts or artifact_ref(WORKSPACE/relative)['sha256']!=copied['sha256']:raise ValueError('Full producer/current numerical source mismatch')
    return profile

def qualify_command(curve,target,x,input_ref,source_ref,receipt):
    """Same whole-pair/source-contact/bounds/native-opening policy as M5."""
    import mujoco
    from a4x.sim.environment import SO101Env
    from a4x.projection.contact_contract import SourceContactContract
    from a4x.projection.distance import NativeDistance,native_pairs
    from a4x.projection.object_motion import ObjectMotion
    from a4x.projection.full_episode_bounds import accelerate,tighten_native_ancestor_bounds,seal_owned_native_model,verify_owned_native_model_seal
    from a4x.projection.continuous import qualify,ContinuousProfile
    from a4x.projection.task import qualify_task
    profile=read_receipt_profile(receipt,source_ref);start=time.monotonic();counts={'native_forward_calls':0,'native_distance_calls':0}
    forward,distance=mujoco.mj_forward,mujoco.mj_geomDistance
    def counted_forward(*a,**kw):
        if counts['native_forward_calls']>=profile['solver']['max_fk_calls'] or time.monotonic()-start>=profile['aggregate_wall_s']:raise ValueError('Full command aggregate budget exhausted')
        counts['native_forward_calls']+=1;return forward(*a,**kw)
    def counted_distance(*a,**kw):counts['native_distance_calls']+=1;return distance(*a,**kw)
    mujoco.mj_forward=counted_forward;mujoco.mj_geomDistance=counted_distance;env=None
    try:
        accelerate(curve,target);env=SO101Env();contract=SourceContactContract(source_ref,env.model,WORKSPACE,x['episode_bounds_s']);lineage=contract.bind_recipe(x)
        motion=ObjectMotion(str(x['object_motion_joint']),x['object_motion_time_s'],x['object_motion_position_m'],x['object_motion_quaternion_wxyz'],input_ref)
        oracle=NativeDistance(env.adapter,pairs=native_pairs(env.model),scope='FULL_EPISODE_SCENE_A_SOURCE_DEFINED_OBJECT_MODEL_REFERENCE_NOT_M6',fixed_qpos=env.data.qpos,object_motions=[motion],allow_scene_a_support=True,contact_contract=contract,first_separating_axis=True)
        tighten_native_ancestor_bounds(oracle);seal=seal_owned_native_model(oracle)
        args=dict(profile['continuous']);args['max_wall_s']=min(args['max_wall_s'],max(0.,profile['aggregate_wall_s']-(time.monotonic()-start)))
        physical=qualify(curve,env.adapter.command_limits,np.full(6,3.),np.full(6,100.),oracle,ContinuousProfile(**args));seal.update(verify_owned_native_model_seal(oracle));physical['owned_model_seal']=seal
        args=dict(profile['task']);args['max_wall_s']=min(args['max_wall_s'],max(0.,profile['aggregate_wall_s']-(time.monotonic()-start)))
        task=qualify_task(curve,env.adapter,target,**args)
        verify_artifact(source_ref,INPUT_ROOTS);verify_artifact(input_ref,INPUT_ROOTS)
        return physical,task,{'profile_ref':receipt['profile'],'contact_source_ref':source_ref,'source_contact_lineage':lineage,'contact_signature':contract.signature,'cost':dict(counts,scene_native_forward_calls=oracle.forward_calls,task_native_forward_calls=2*task['fk_calls'],wall_seconds=time.monotonic()-start),'all_native_pairs':len(oracle.pairs),'required_gate_policy':'ALL_PAIRS_JOINT_DERIVATIVES_AND_TASK_PASS'}
    finally:
        if env is not None:env.close()
        mujoco.mj_forward=forward;mujoco.mj_geomDistance=distance


def verify_full_acceptance(receipt_ref=None,result_ref=None):
    """Use root's immutable numeric acceptance, never a prose header keyword."""
    acceptance=WORKSPACE/'runs/implementation_20261005/F2D_acceptance_20261006T051429_418919Z/Acceptance.json'
    value=json.loads(acceptance.read_text())
    if value.get('module')!='F2D' or value.get('status')!='ACCEPTED_SCOPED' or value.get('scope')!='WHOLE_ORIGINAL_PARENT_WARMSTART_MODEL_REFERENCE_FEASIBILITY_ONLY':
        raise ValueError('Full producer lacks scoped independent acceptance')
    if artifact_ref(value['review'])['sha256']!=value['review_sha256']:
        raise ValueError('Independent review bytes differ from accepted review')
    result_path=Path(value['actual_full_result']); result=json.loads(result_path.read_text())
    receipt=json.loads((result_path.parent/'Receipt.json').read_text())
    if receipt['output']!=artifact_ref(result_path) or result.get('full_M5_status')!='PASS_MODEL_REFERENCE_ONLY':
        raise ValueError('Accepted numerical result/receipt is not actual full PASS')
    read_receipt_profile(receipt,receipt['contact_source'])
    if result_ref is not None and result_ref!=artifact_ref(result_path):
        raise ValueError('Unaccepted full projection result cannot borrow scoped acceptance')
    if receipt_ref is not None and receipt_ref!=artifact_ref(result_path.parent/'Receipt.json'):
        raise ValueError('Unaccepted full projection receipt cannot borrow scoped acceptance')
    return artifact_ref(acceptance)
