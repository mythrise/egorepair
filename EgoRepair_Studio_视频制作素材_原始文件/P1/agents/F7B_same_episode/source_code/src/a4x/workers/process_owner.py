"""Linux process identities/deadlines; never signal a reused or unrelated PID."""
import json
import os
import signal
import time
from pathlib import Path
from a4x.server.paths import existing_run
from a4x.agents.ledger import checked_path


def identity(pid):
    try:
        raw=Path('/proc/'+str(pid)+'/stat').read_text();parts=raw[raw.rfind(')')+2:].split()
        return {'pid':int(pid),'start_token':parts[19],'pgid':int(parts[2]),'session':int(parts[3]),'state':parts[0]}
    except (OSError,ValueError,IndexError):return None

def signal_exact(expected,sig):
    actual=identity(expected['pid'])
    if actual is None:return False
    if any(actual[key]!=expected[key] for key in ('pid','start_token','pgid','session')):return False
    # pidfd pins the exact kernel process, and identity is checked after opening too.
    fd=os.pidfd_open(actual['pid'])
    try:
        after=identity(actual['pid'])
        if after is None or any(after[k]!=actual[k] for k in ('pid','start_token','pgid','session')):return False
        signal.pidfd_send_signal(fd,sig)
        return True
    except ProcessLookupError:return False
    finally:os.close(fd)

def reconcile(run_path):
    run=existing_run(run_path);policy_path=checked_path(run,run.path/'ProcessPolicy.json')
    if not policy_path.is_file():return {'status':'NO_PROCESS_STARTED'}
    policy=json.loads(policy_path.read_text());report={'status':'RECONCILED','terminated':[],'deadline_utc_epoch':policy['deadline_utc_epoch']}
    child_path=checked_path(run,run.path/'WorkerProcess.json');supervisor_path=checked_path(run,run.path/'SupervisorProcess.json')
    if child_path.is_file():
        child=json.loads(child_path.read_text())
        if child.get('owner_nonce')!=policy['owner_nonce'] or child.get('job_run')!=str(run.path):raise ValueError('Process ownership receipt mismatch')
        if child['pgid']!=child['pid'] or child['session']!=child['pid']:raise ValueError('Worker was not created in an owned isolated session')
        current=identity(child['pid'])
        if current and all(current[k]==child[k] for k in ('pid','start_token','pgid','session')):
            # Descendants inherit the new isolated session/group. Snapshot each
            # exact identity and signal via pidfd, never bare killpg or PID alone.
            members=[]
            for p in Path('/proc').iterdir():
                if p.name.isdigit():
                    candidate=identity(int(p.name))
                    if candidate and candidate['pgid']==child['pgid'] and candidate['session']==child['session'] and candidate['pid']!=os.getpid():members.append(candidate)
            members.sort(key=lambda x:x['pid']==child['pid'])
            for member in members:
                if signal_exact(member,signal.SIGTERM):report['terminated'].append(member['pid'])
            end=time.monotonic()+2
            while time.monotonic()<end and identity(child['pid']) is not None:time.sleep(.02)
            for member in members:
                signal_exact(member,signal.SIGKILL)
    # Let supervisor reap its own direct child; then stop only its exact identity.
    if supervisor_path.is_file():
        owner=json.loads(supervisor_path.read_text())
        if owner.get('owner_nonce')!=policy['owner_nonce'] or owner.get('job_run')!=str(run.path):raise ValueError('Supervisor ownership mismatch')
        if owner['pid']!=os.getpid():signal_exact(owner,signal.SIGTERM)
    return report
