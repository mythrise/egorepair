"""Survives owner death, owns worker identity and enforces persisted deadline."""
import argparse,json,os,subprocess,sys,time
from a4x.server.paths import existing_run
from .process_owner import identity,reconcile
p=argparse.ArgumentParser();p.add_argument('--command-json',required=True);p.add_argument('--job-run',required=True);args=p.parse_args()
run=existing_run(args.job_run);policy=json.loads((run.path/'ProcessPolicy.json').read_text());argv=json.loads(args.command_json)
run.write_json('SupervisorProcess.json',dict(identity(os.getpid()),owner_nonce=policy['owner_nonce'],job_run=str(run.path)))
read_fd,write_fd=os.pipe()
child=subprocess.Popen([sys.executable,'-B','-m','a4x.workers.process_gate',str(read_fd),json.dumps(argv)],pass_fds=(read_fd,),start_new_session=True)
os.close(read_fd)
try:
    run.write_json('WorkerProcess.json',dict(identity(child.pid),owner_nonce=policy['owner_nonce'],job_run=str(run.path)))
    os.write(write_fd,b'R');os.close(write_fd);write_fd=None
    remaining=max(.01,policy['deadline_utc_epoch']-time.time())
    try:code=child.wait(timeout=remaining)
    except subprocess.TimeoutExpired:
        reconcile(run.path);child.wait(timeout=3);code=124
finally:
    if write_fd is not None:os.close(write_fd)
raise SystemExit(code)
