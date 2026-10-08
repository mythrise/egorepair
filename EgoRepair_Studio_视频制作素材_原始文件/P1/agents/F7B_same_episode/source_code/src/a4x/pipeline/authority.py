"""Append-only audited origin/counter migration; V1 remains read-only."""
import json,sqlite3
from a4x.paths import WORKSPACE,RunDirectory
from a4x.provenance import artifact_ref,IntegrityError
from a4x.agents import BudgetLedger
from a4x.agents.ledger import canonical,digest,DEFAULT_LIMITS
from a4x.server.paths import existing_run

def source_registration(ref):
    from .source_registry import PINNED_SOURCE_SHAS
    if ref['sha256'] in PINNED_SOURCE_SHAS and ref['sha256'] not in ('dfddd806dd6bf57fbf38e2e556561881eebb5b7987f030b0bb54257208ca6132','0fde2decd3c5620b0db99abe3ee6fb9f2f742d6fd39d3fc1d02547abf2f58db4'):
        return {'canonical_identity':{'sha256':ref['sha256'],'kind':PINNED_SOURCE_SHAS[ref['sha256']]},'context_hash':digest({'source':ref['sha256'],'kind':PINNED_SOURCE_SHAS[ref['sha256']]})}
    from a4x.models.source_registration import verify_registered_source
    return verify_registered_source(ref)

def episode_authority(package):
    registration=source_registration(package['source_ref']);identity=registration['canonical_identity'];key=identity['sha256']
    root=WORKSPACE/'.runtime/pipeline_episode_authority/v2'/key
    try:run=RunDirectory(root)
    except FileExistsError:run=existing_run(root)
    limits=dict(DEFAULT_LIMITS)
    if 'model_policy' in registration:limits['spatial']=registration['model_policy']['spatial_calls']
    ledger=BudgetLedger(run,key,registration['context_hash'],limits)
    old=WORKSPACE/'.runtime/pipeline_episode_authority'/key/'ledger.sqlite3'
    # Preserve original rows and evidence: map only demonstrated host stage
    # admissions to cost events. Unknown origin is quarantined, never refunded.
    if old.is_file():
        with sqlite3.connect('file:'+str(old)+'?mode=ro',uri=True) as db:
            rows=db.execute('SELECT key,request,resources,state,receipt_id,costs,output FROM reservations').fetchall()
        quarantine=[]
        for row in rows:
            oldkey,request,resources,state,receipt,costs,output=row;resources=json.loads(resources);request=json.loads(request)
            nested=request.get('request');host=isinstance(nested,dict) and (nested.get('stage') or isinstance(nested.get('request'),dict) and nested['request'].get('stage')) and oldkey.startswith('stage')
            recognized=host or oldkey.startswith(('policy-evaluation:','m5:','m4-round','baseline-replay:','candidate-replay:'))
            if state!='DENIED' and not recognized:quarantine.append(oldkey)
            mapped={} if host and resources=={'tools':1} else resources
            costs=json.loads(costs or '{}')
            if host and 'wall_seconds' in costs:costs['host_inclusive_wall_seconds']=costs.pop('wall_seconds')
            proof={'schema':'a4x.counter_migration.v2','origin_path':str(old),'raw_row':list(row),'mapping':'HOST_OPERATION_NO_TOOL_DISPATCH' if host else 'PRESERVED_UNKNOWN_ORIGIN_QUARANTINE','v1_row_sha256':digest(list(row))}
            _import(ledger,'v1:'+oldkey,mapped,state,costs,proof)
        if quarantine:raise IntegrityError('V1_UNKNOWN_ORIGIN_QUARANTINE: '+','.join(quarantine))
    if identity['kind'] in ('ORIGINAL_EXECUTION','PROJECT_EXECUTION','PUBLIC_IMAGE') or registration.get('legacy_frozen'):
        from a4x.models.source_registration import readonly_spent_resources
        spent=readonly_spent_resources(package['source_ref'])
        for admission in spent['admissions']:
            _import(ledger,'spatial:'+admission['admission_id'],{'spatial':1},admission['state'],admission['known_cost'],{'schema':'a4x.spatial_import.v2','origin':admission,'counter_semantics':'SPATIAL_NOT_COORDINATOR_RESPONSES'})
    return ledger

def _import(ledger,key,resources,state,costs,proof):
    if state=='DENIED':return
    req=canonical({'resources':resources,'request':proof,'reserved_costs':None});out=canonical(proof)
    with ledger.transaction() as db:
        existing=db.execute('SELECT request FROM reservations WHERE key=?',(key,)).fetchone()
        if existing:
            if existing[0]!=req:raise IntegrityError('Audited migration origin changed; quarantine')
            return
        db.execute('INSERT INTO reservations VALUES (?,?,?,?,?,?,?)',(key,req,canonical(resources),state,key+':origin' if state=='SETTLED' else None,canonical(costs) if costs else None,out if state=='SETTLED' else None))
