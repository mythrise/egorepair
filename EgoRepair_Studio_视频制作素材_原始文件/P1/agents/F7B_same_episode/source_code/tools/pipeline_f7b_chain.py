"""Actual whole-source no-edit connectivity; never learned repair benefit."""
import argparse,json
from pathlib import Path
from a4x import SCHEMA_VERSION
from a4x.paths import WORKSPACE,RunDirectory
from a4x.provenance import artifact_ref
from a4x.cli import pipeline_stage
from a4x.pipeline import episode_ledger

def dispatch_recorded(config, package_path, job):
    """Keep pre-worker admission/validation failures in the actual chain receipt."""
    try:
        return pipeline_stage(config, package_path, job)
    except (ValueError, OSError, KeyError, TypeError) as error:
        return {'stage': config['_dispatch_stage'], 'status': 'FAILED',
                'outputs': [], 'denominators': {},
                'reason': type(error).__name__ + ': ' + str(error),
                'execution_outcome': 'NOT_EXECUTED_OR_UNKNOWN_RETAIN_LEDGER'}

def run(args):
    writer=RunDirectory(args.run_dir);source_ref=artifact_ref(WORKSPACE/'runs/implementation_20261005/F2b_20261005T121819_657861/attempt_05/execution.json');source=json.loads(Path(source_ref['path']).read_text());receipt_ref=artifact_ref(args.projection_receipt);receipt=json.loads(Path(receipt_ref['path']).read_text());result_ref=artifact_ref(args.projection_result)
    old_candidate_ref=artifact_ref(WORKSPACE/'runs/implementation_20261005/F7_noedit_connectivity_20261006T0550/repair/output/m4-round2-0.json');candidate=json.loads(Path(old_candidate_ref['path']).read_text());candidate.update(projection_input=receipt['input'],object_registered_parent=old_candidate_ref,experiment_scope='NO_EDIT_CONNECTIVITY_ABLATION',repair_benefit='NOT_CLAIMED')
    # Exact unchanged original recipe fields; only registered object lineage added.
    import numpy as np
    original=json.loads(Path(old_candidate_ref['path']).read_text())['projection_input']
    with np.load(original['path'],allow_pickle=False) as a,np.load(receipt['input']['path'],allow_pickle=False) as b:
        if any(not np.array_equal(a[k],b[k]) for k in a.files):raise ValueError('No-edit candidate original coefficients/baseline/masks drift')
        if np.any(b['z']):raise ValueError('This chain is explicitly zero-edit connectivity only')
    candidate_ref=writer.write_json('CandidateWithObjectLineage.json',candidate);context_ref=candidate['input_context'];scene_ref=artifact_ref(Path(source_ref['path']).parent/'parameters.json');results={};package=None
    def stage(node,name,inputs,profile=None):
        nonlocal package
        package=dict(schema='a4x.pipeline.package.v1',schema_version=SCHEMA_VERSION,stage=name,source_ref=source_ref,context_ref=context_ref,inputs=inputs,profile=profile or {})
        ref=writer.write_json(node+'.package.json',package);job=RunDirectory(writer.path/node);value=dispatch_recorded({'_dispatch_stage':name,'allowed_input_roots':[str(WORKSPACE/'runs')]},ref['path'],job);job.write_json('StageResult.json',value);results[node]=value;writer.write_json(node+'.receipt.json',{'stage_result':artifact_ref(job.path/'StageResult.json')});print(json.dumps({'node':node,'status':value['status'],'denominators':value['denominators'],'reason':value.get('reason')}),flush=True);return value
    full=dict(projection_profile='FULL_EPISODE_DEVELOPMENT',experiment_scope='NO_EDIT_CONNECTIVITY_ABLATION');resume=None
    if args.resume_run:
        from a4x.provenance import verify_artifact
        resume=artifact_ref(Path(args.resume_run)/'F7BChain.json');prior=json.loads(verify_artifact(resume,[WORKSPACE/'runs']).read_text())
        if prior['source_ref']!=source_ref or prior['scope']!='NO_EDIT_CONNECTIVITY_ABLATION':raise ValueError('Resume original source/scope mismatch')
        for node in ('CommandCompilation','WholeCandidateReplay'):
            value=prior['results'][node]
            if value['status']!='EXECUTED':raise ValueError('Resume requires actual completed command/M6 stages')
            for output in value['outputs']:verify_artifact(output,[WORKSPACE/'runs'])
            results[node]=value
        adopt=results['CommandCompilation']
    else:adopt=stage('CommandCompilation','adopt-projection',dict(projection_result=result_ref,projection_receipt=receipt_ref,candidate=candidate_ref),full)
    stop='COMMAND_COMPILATION_NOT_EXECUTED'
    if adopt['status']=='EXECUTED':
        replay=results['WholeCandidateReplay'] if resume else stage('WholeCandidateReplay','replay-candidate',{'commands':adopt['outputs'][1],'scene_parameters':scene_ref},full);stop='M6_NOT_EXECUTED'
        if replay['status']=='EXECUTED':
            qualified=stage('CandidateDataset','build-pairs',dict(execution=replay['outputs'][0],summary=replay['outputs'][1],execution_lineage=replay['outputs'][2]),dict(full,split='train'));stop='DATA_NOT_EXECUTED'
            if qualified['status']=='EXECUTED':
                raw=stage('OriginalDataset','build-pairs',dict(execution=source_ref,summary=artifact_ref(Path(source_ref['path']).parent/'summary.json')),{'split':'train'});export=stage('DatasetReadback','export-dataset',{'dataset_receipt':qualified['outputs'][0]});stop='CANDIDATE_NOT_TRAINING_QUALIFIED'
                if qualified.get('denominators',{}).get('accepted_training_rows')==len(source['commands']) and raw['status']=='EXECUTED':
                    recipe=writer.write_json('training_spec.json',{'updates':1,'batch_size':8,'lr':.0001,'seeds':[17],'validation_every':1,'selection':'DEV_NO_VAL_FIXED_LAST','scope':'DEVELOPMENT_IN_SAMPLE'});cfg=dict(observation_dim=107,action_dim=6,hidden=32,heads=4,encoder_layers=1,decoder_layers=1,sampling_steps=2,diffusion_steps=8)
                    for family in ('ACT','DIFFUSION_POLICY'):
                        pi0=stage(family+'Pi0','pretrain',dict(train_dataset=raw['outputs'][0],training_spec=recipe),dict(allow_training=True,family=family,model_config=cfg,experiment_scope='NO_EDIT_CONNECTIVITY_ABLATION'))
                        if pi0['status']!='EXECUTED':stop=family+'_PI0_FAILED';break
                        reports=json.loads(Path(pi0['outputs'][0]['path']).read_text());checkpoint=reports['17']['checkpoint'];trained=stage(family+'MatchedPosttrain','posttrain',dict(train_dataset=qualified['outputs'][0],raw_dataset=raw['outputs'][0],control_dataset=raw['outputs'][0],pi0=checkpoint,training_spec=recipe),dict(allow_training=True,family=family,experiment_scope='NO_EDIT_CONNECTIVITY_ABLATION'))
                        if trained['status']!='EXECUTED':stop=family+'_POSTTRAIN_FAILED';break
                        reports=json.loads(Path(trained['outputs'][0]['path']).read_text());eval_profiles={'steps':len(source['commands']),'evaluation_scope':'IN_SAMPLE_NOT_GENERALIZATION','experiment_scope':'NO_EDIT_CONNECTIVITY_ABLATION'}
                        outcomes=[stage(family+arm+'Evaluation','evaluate',dict(checkpoint=reports[arm]['checkpoint'],scene_parameters=scene_ref),eval_profiles) for arm in ('raw','qualified','matched_control')]
                        stop='MATCHED_TRAIN_EVAL_EXECUTED_SCOPE_ONLY' if all(value['status']=='EXECUTED' for value in outcomes) else family+'_EVALUATION_INCOMPLETE'
                        if any(value['status']!='EXECUTED' for value in outcomes):break
    report=writer.write_json('F7BChain.json',dict(scope='NO_EDIT_CONNECTIVITY_ABLATION',resume_parent=resume,source_ref=source_ref,original_commands=len(source['commands']),original_states=len(source['states']),results=results,stop_reason=stop,source_totals=episode_ledger(package).totals(),nonzero_M4_failure_receipt=artifact_ref(WORKSPACE/'runs/implementation_20261005/F7_full_cpu_20261006T0540/FullCPUChain.json'),pi0_evaluation='NOT_RUN_OLD_TWO_SOURCE_ROLLOUTS_REMAIN_SPENT_SIX_REMAINING_USED_FOR_MATCHED_ARMS',repair_benefit='NOT_CLAIMED',formal_research='NOT_RUN',RGB_POLICY='NOT_RUN_NUMERIC_SIM_STATE_V1',full_M5_optimization='NOT_RUN_PARENT_FEASIBILITY_ONLY'));print(json.dumps(report),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--projection-result',required=True);p.add_argument('--projection-receipt',required=True);p.add_argument('--run-dir',required=True);p.add_argument('--resume-run');run(p.parse_args())
