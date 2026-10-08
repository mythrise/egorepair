"""Host-owned bounded immutable stage DAG. Completed scope never means FULL method."""
import json,sqlite3
from a4x.paths import RunDirectory,WORKSPACE
from a4x.provenance import artifact_ref,verify_artifact,IntegrityError
from a4x.agents.ledger import checked_path,canonical
from a4x.cli import pipeline_stage
from .packages import INPUT_ROOTS,STAGES,read_package


def run_graph(plan_ref,run_path):
    plan=json.loads(verify_artifact(plan_ref,INPUT_ROOTS).read_text())
    if set(plan)!={'schema','source_ref','context_ref','nodes'} or plan['schema']!='a4x.pipeline.graph.v1':raise ValueError('Exact registered graph schema required')
    nodes=plan['nodes']
    if not isinstance(nodes,list) or not 1<=len(nodes)<=20:raise ValueError('Bounded graph node count')
    seen=set()
    for node in nodes:
        if set(node)!={'id','stage','inputs','profile','dependencies'} or node['stage'] not in STAGES or not isinstance(node['id'],str) or not node['id'].isalnum() or len(node['id'])>40 or node['id'] in seen:raise ValueError('Registered unique node identity')
        if not isinstance(node['dependencies'],dict):raise ValueError('Typed dependency roles')
        for role,edge in node['dependencies'].items():
            if role not in STAGES[node['stage']] or set(edge)!={'node','output'} or edge['node'] not in seen or type(edge['output']) is not int or edge['output']<0:raise ValueError('Forward/unknown/unsafe graph dependency')
        seen.add(node['id'])
    writer=RunDirectory(run_path);writer.write_json('Plan.json',{'input_plan':plan_ref,'plan':plan,'scope':'REGISTERED_STAGES_ONLY_NOT_FULL_METHOD'})
    path=checked_path(writer,writer.path/'graph.sqlite3')
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE nodes(id TEXT PRIMARY KEY,state TEXT,result TEXT)')
        db.executemany('INSERT INTO nodes VALUES(?,?,NULL)',[(n['id'],'QUEUED') for n in nodes])
    results={};blocked=False
    for node in nodes:
        inputs=dict(node['inputs'])
        for role,edge in node['dependencies'].items():
            parent=results[edge['node']]
            if parent['status']!='EXECUTED':blocked=True;break
            if edge['output']>=len(parent['outputs']):raise IntegrityError('Parent output index not produced')
            inputs[role]=parent['outputs'][edge['output']]
        if blocked:
            value={'status':'NOT_READY','stage':node['stage'],'reason':'PREDECESSOR_NOT_EXECUTED','outputs':[],'denominators':{}}
        else:
            package={'schema':'a4x.pipeline.package.v1','schema_version':__import__('a4x').SCHEMA_VERSION,'stage':node['stage'],'source_ref':plan['source_ref'],'context_ref':plan['context_ref'],'inputs':inputs,'profile':node['profile']}
            package_ref=writer.write_json(node['id']+'.package.json',package)
            read_package(package_ref)
            job=RunDirectory(writer.path/node['id'])
            with sqlite3.connect(path) as db:db.execute('UPDATE nodes SET state=? WHERE id=?',('RUNNING',node['id']))
            value=pipeline_stage({'_dispatch_stage':node['stage'],'allowed_input_roots':[str(p) for p in INPUT_ROOTS]},package_ref['path'],job)
            job.write_json('StageResult.json',value)
        results[node['id']]=value
        with sqlite3.connect(path) as db:db.execute('UPDATE nodes SET state=?,result=? WHERE id=?',(value['status'],canonical(value),node['id']))
        blocked=blocked or value['status']!='EXECUTED'
    return writer.write_json('GraphResult.json',{'status':'INCOMPLETE_DEPENDENCY_SCOPE' if blocked else 'COMPLETED_REGISTERED_STAGES_SCOPE_ONLY','nodes':results,'full_method':'NOT_CLAIMED','formal_training':'NOT_IMPLIED','source_ref':plan['source_ref'],'context_ref':plan['context_ref']})

def recover_graph(run_path):
    """Reconcile exact owned process identities; retain admissions, never reexecute."""
    from a4x.server.paths import existing_run
    from a4x.workers.process_owner import reconcile
    from .packages import episode_ledger
    run=existing_run(run_path);plan_record=json.loads(checked_path(run,run.path/'Plan.json').read_text());verify_artifact(plan_record['input_plan'],INPUT_ROOTS)
    path=checked_path(run,run.path/'graph.sqlite3');reports=[]
    with sqlite3.connect(path) as db:
        for id, in db.execute("SELECT id FROM nodes WHERE state='RUNNING'").fetchall():
            report=reconcile(run.path/id)
            package,source,context=read_package(artifact_ref(run.path/(id+'.package.json')))
            from a4x.workers.budget_scope import OwnedBudget
            unknown=OwnedBudget(episode_ledger(package),str((run.path/id).relative_to(WORKSPACE))).recover()
            db.execute('UPDATE nodes SET state=?,result=? WHERE id=?',('UNKNOWN_INTERRUPTED',canonical({'process_recovery':report,'unresolved_reservations':unknown,'automatic_retry':False}),id))
            reports.append({'node':id,'process':report,'admission':'RETAINED_UNKNOWN'})
    return run.write_json('GraphRecovery.json',{'reports':reports,'automatic_retry':False})
