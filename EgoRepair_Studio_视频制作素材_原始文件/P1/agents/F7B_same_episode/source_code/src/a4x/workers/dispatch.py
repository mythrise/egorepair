"""Shared completion readback and process ownership for CLI and localhost jobs."""
import time
import uuid
from a4x import SCHEMA_VERSION
from a4x.agents.ledger import canonical,checked_path
from a4x.provenance import verify_artifact,IntegrityError
from .registry import PROFILES

def supervised_argv(run,job_id,target_argv,deadline_seconds=180):
    if type(deadline_seconds) is not int or deadline_seconds not in (180,3780,7380):raise ValueError("Registered owned-worker deadline required")
    run.write_json('ProcessPolicy.json',{'job_id':job_id,'job_run':str(run.path),'owner_nonce':str(uuid.uuid4()),'deadline_utc_epoch':time.time()+deadline_seconds})
    return [str(PROFILES['foundation']),'-B','-m','a4x.workers.supervise','--command-json',canonical(target_argv),'--job-run',str(run.path)]

def validate_stage_result(stage,result,run):
    if not isinstance(result,dict) or result.get('stage')!=stage or result.get('schema_version')!=SCHEMA_VERSION or result.get('status') not in {'EXECUTED','FAILED','REJECTED','NOT_READY'}:raise IntegrityError('StageResult identity/schema mismatch')
    refs=result.get('outputs');counts=result.get('denominators')
    if not isinstance(refs,list) or not isinstance(counts,dict) or any(type(v) is not int or v<0 for v in counts.values()):raise IntegrityError('Malformed output/count contract')
    if result['status']=='EXECUTED' and not refs:raise IntegrityError('Completed stage requires actual output artifacts')
    for ref in refs:
        checked_path(run,ref['path']);verify_artifact(ref,[run.path])
    return result
