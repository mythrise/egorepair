"""Profile/worker/lineage negatives; no simulated positive gates."""
import copy,json,uuid
import pytest
from a4x.paths import WORKSPACE,RunDirectory
from a4x.provenance import artifact_ref
from a4x.pipeline.full_profile import read_receipt_profile
from a4x.pipeline.candidate import certificate_semantics
from a4x.workers.registry import worker_seconds,PROFILES

RECEIPT=WORKSPACE/'runs/implementation_20261005/F2d_full_final_guards_20261006T045230Z/Receipt.json'
SOURCE=artifact_ref(WORKSPACE/'runs/implementation_20261005/F2b_20261005T121819_657861/attempt_05/execution.json')

def test_complete_profile_same_source_policy_and_copied_producer():
    receipt=json.loads(RECEIPT.read_text());profile=read_receipt_profile(receipt,SOURCE)
    assert profile['name']=='FULL_EPISODE_DEVELOPMENT' and profile['continuous']['max_depth']==24
    bad=copy.deepcopy(receipt);bad['contact_source']=dict(SOURCE,sha256='0'*64)
    with pytest.raises(ValueError,match='original source contact'):read_receipt_profile(bad,SOURCE)
    bad=copy.deepcopy(receipt);bad['source_snapshot_files']=[]
    with pytest.raises(ValueError,match='snapshot proof'):read_receipt_profile(bad,SOURCE)

def test_modified_profile_budget_cannot_be_borrowed_by_name():
    w=RunDirectory(WORKSPACE/'runs/implementation_20261005'/('F7B_profile_'+uuid.uuid4().hex));receipt=json.loads(RECEIPT.read_text());profile=json.loads(open(receipt['profile']['path']).read());profile['continuous']['max_depth']=99;receipt['profile']=w.write_json('profile.json',profile)
    with pytest.raises(ValueError,match='registered reviewed profile'):read_receipt_profile(receipt,SOURCE)

def test_deadline_profiles_are_fixed_and_default_preserved():
    assert worker_seconds()==180
    assert worker_seconds({'stage':'project','profile':{'projection_profile':'FULL_EPISODE_DEVELOPMENT'}})==7380
    assert worker_seconds({'stage':'replay-candidate','profile':{'projection_profile':'FULL_EPISODE_DEVELOPMENT'}})==3780
    assert worker_seconds({'stage':'pretrain','profile':{'projection_profile':'FULL_EPISODE_DEVELOPMENT'}})==180
    assert PROFILES['repair']==WORKSPACE/'.venv-data/bin/python'

def test_recomputed_curve_semantics_ignore_only_separate_measured_cost():
    a={'q_rad':[1.],'status':'PASS','full_scene':{'status':'PASS','wall_s':2.},'full_profile_registration':{'cost':{'native_forward_calls':10},'profile_ref':{'sha256':'x'}}}
    b=copy.deepcopy(a);b['full_scene']['wall_s']=4.;b['full_profile_registration']['cost']['native_forward_calls']=12
    assert certificate_semantics(a)==certificate_semantics(b)
    b['status']='UNKNOWN';assert certificate_semantics(a)!=certificate_semantics(b)


def test_full_readiness_uses_registered_numerical_acceptance():
    from a4x.pipeline.full_profile import verify_full_acceptance
    from a4x.pipeline.packages import package_readiness
    accepted=verify_full_acceptance()
    assert accepted['sha256']=='d73498134f47cc5c4bd49a2466354d5959bb58c3a26d2ed40b7c37479b1e1ea5'
    value=package_readiness({'stage':'adopt-projection','inputs':{'projection_result':{},'projection_receipt':{},'candidate':{}},'profile':{'projection_profile':'FULL_EPISODE_DEVELOPMENT'}})
    assert value['status']=='READY_TO_RUN'


def test_chain_entrypoint_is_syntactically_runnable():
    import ast
    ast.parse((WORKSPACE/'tools/pipeline_f7b_chain.py').read_text())


def test_other_pass_labeled_result_cannot_borrow_scoped_acceptance():
    from a4x.pipeline.full_profile import verify_full_acceptance
    with pytest.raises(ValueError,match='Unaccepted full projection result'):
        verify_full_acceptance(result_ref=dict(artifact_ref(RECEIPT.parent/'Result.json'),sha256='0'*64))
    with pytest.raises(ValueError,match='Unaccepted full projection receipt'):
        verify_full_acceptance(receipt_ref=dict(artifact_ref(RECEIPT),sha256='0'*64))


def test_chain_preworker_failure_is_retained_in_receipt(monkeypatch):
    import importlib.util
    spec=importlib.util.spec_from_file_location('f7b_entrypoint',WORKSPACE/'tools/pipeline_f7b_chain.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    def fail(*args):raise ValueError('source allocation exhausted')
    monkeypatch.setattr(module,'pipeline_stage',fail)
    value=module.dispatch_recorded({'_dispatch_stage':'evaluate'},'unused',None)
    assert value['status']=='FAILED' and value['outputs']==[]
    assert 'allocation exhausted' in value['reason']
