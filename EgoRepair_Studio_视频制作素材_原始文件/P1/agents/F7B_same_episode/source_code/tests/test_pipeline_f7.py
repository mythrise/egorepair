"""Package and real CPU worker contracts; original source is an actual failed/success trace, not invented success."""
import copy,json,time,uuid
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from a4x import SCHEMA_VERSION
from a4x.paths import WORKSPACE,RunDirectory
from a4x.provenance import artifact_ref
from a4x.pipeline import read_package,episode_ledger,package_readiness
from a4x.server.api import create_app
SOURCE=WORKSPACE/'runs/implementation_20261005/F2b_20261005T121819_657861/attempt_05/execution.json'
CONTEXT=json.loads((WORKSPACE/'runs/implementation_20261005/F7_chain_20261006T0140/context.json').read_text())

def package(tmp_path,stage='build-graph'):
    writer=RunDirectory(WORKSPACE/'runs/implementation_20261005'/('F7_test_'+str(uuid.uuid4())))
    context=writer.write_json('context.json',CONTEXT)
    value=dict(schema='a4x.pipeline.package.v1',schema_version=SCHEMA_VERSION,stage=stage,source_ref=artifact_ref(SOURCE),context_ref=context,inputs={},profile={})
    return writer,value

def test_original_source_aliases_share_durable_quota_and_context_cannot_reset(tmp_path):
    writer,p=package(tmp_path);original=episode_ledger(p);before=original.totals()
    alias=writer.write_json('one.json',p);p2=read_package(alias)[0]
    assert episode_ledger(p2).path==original.path and episode_ledger(p2).totals()==before
    changed=copy.deepcopy(CONTEXT);changed['frame']='OTHER'
    p2['context_ref']=writer.write_json('bad_context.json',changed)
    with pytest.raises(ValueError):read_package(writer.write_json('two.json',p2))

def test_stage_extra_input_and_truthy_authorization_fail_closed(tmp_path):
    w,p=package(tmp_path);p['profile']['public_text_authorized']='false'
    with pytest.raises(ValueError):read_package(w.write_json('truthy.json',p))
    p['profile']={};p['inputs']['arbitrary_command']=artifact_ref(SOURCE)
    with pytest.raises(ValueError):read_package(w.write_json('command.json',p))

def test_reference_extra_secret_rejected_without_http_echo(tmp_path):
    w,p=package(tmp_path);ref=w.write_json('ok.json',p);ref['api_key']='CONTROLLED_FAKE_TEST_SECRET'
    with TestClient(create_app(tmp_path/'server',sources={})) as c:
        r=c.post('/packages',json={'artifact':ref,'label':'本地输入'})
        assert r.status_code==400 and 'CONTROLLED_FAKE_TEST_SECRET' not in r.text
        assert c.get('/sources').json()==[]

def test_formal_risk_cannot_be_granted_by_caller_declared_cohort(tmp_path):
    w,p=package(tmp_path,'certify-risk');assert package_readiness(p)['status']=='NOT_READY'

def test_registered_actual_package_worker_and_verified_output(tmp_path):
    w,p=package(tmp_path);ref=w.write_json('input.json',p)
    with TestClient(create_app(tmp_path/'server',sources={})) as c:
        registered=c.post('/packages',json={'artifact':ref,'label':'实际回放证据'}).json()
        assert registered['readiness']['status']=='READY_TO_RUN'
        req={'stage':'build-graph','source_id':registered['id'],'context':registered['context'],'idempotency_key':'real-graph'}
        job=c.post('/jobs',json=req).json()
        assert c.post('/jobs',json=req).json()['id']==job['id']
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            final=c.get('/jobs/'+job['id']).json()
            if final['state'] not in ('QUEUED','RUNNING'):break
            time.sleep(.1)
        assert final['state']=='COMPLETED_SCOPE',final
        graph=c.get('/jobs/'+job['id']+'/artifacts/0').json()
        assert graph['source_ref']==p['source_ref'] and graph['denominators']['source_states']==281
        bad=dict(req,stage='repair',idempotency_key='wrongstage')
        assert c.post('/jobs',json=bad).status_code==400

def test_counter_nan_bool_and_forged_new_source_do_not_register(tmp_path):
    w,p=package(tmp_path)
    for i,value in enumerate([True,float('nan'),-1,401]):
        candidate=copy.deepcopy(p);candidate['profile']['steps']=value
        path=w.path/('bad'+str(i)+'.json');path.write_text(json.dumps(candidate))
        with pytest.raises(ValueError):read_package(artifact_ref(path))
    candidate=copy.deepcopy(p);fake=w.write_json('fake_source.json',{'schema':'a4x.execution.v1','command_count':0,'state_count':1,'commands':[],'states':[{'time_s':0.}],'robot_profile':{'robot':'SO101'}})
    candidate['source_ref']=fake
    with pytest.raises(ValueError,match='authority not registered'):read_package(w.write_json('fake.package.json',candidate))

def test_new_ui_javascript_compiles_without_browser_global_cache(tmp_path):
    from a4x.server.ui import PAGE
    from a4x.workers.runtime import local_environment
    import subprocess
    node=next((WORKSPACE/'.venv-browser/lib').glob('python*/site-packages/playwright/driver/node'))
    path=tmp_path/'ui.js';path.write_text(PAGE.split('<script>')[1].split('</script>')[0])
    p=subprocess.run([str(node),'--check',str(path)],capture_output=True,text=True,env=local_environment(cache_root=tmp_path/'node_cache'))
    assert p.returncode==0,p.stderr
