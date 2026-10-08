"""Persistent localhost jobs, fixed immutable input IDs and independent budgets."""
import contextlib
import os
import fcntl
import datetime
import json
import sqlite3
import subprocess
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from a4x.paths import RunDirectory,WORKSPACE
from a4x.agents import BudgetLedger
from a4x.agents.ledger import checked_path,canonical,digest
from a4x.provenance import verify_artifact,artifact_ref,IntegrityError
from a4x.workers.registry import command,readiness,PROFILES
from a4x.workers.process_owner import reconcile
from a4x.workers.dispatch import supervised_argv,validate_stage_result
from a4x.workers.runtime import local_environment
from a4x import SCHEMA_VERSION
from .paths import existing_run

class JobStore:
    def __init__(self,path,sources):
        path=Path(path).absolute()
        if path.exists():
            run=existing_run(path)
            checked_path(run,path/'RuntimeIdentity.json')
            if json.loads((path/'RuntimeIdentity.json').read_text())!={'schema':'a4x.local_workbench.v1','bind':'127.0.0.1'}:raise IntegrityError('Wrong server state identity')
        else:
            run=RunDirectory(path);run.write_json('RuntimeIdentity.json',{'schema':'a4x.local_workbench.v1','bind':'127.0.0.1'})
        self.run=run;self.sources=sources
        lockpath=checked_path(run,path/'server.lock')
        self.lock_fd=os.open(lockpath,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        try:fcntl.flock(self.lock_fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            os.close(self.lock_fd);raise IntegrityError('Server state already owned by another live process')
        self.pool=ThreadPoolExecutor(max_workers=2);self.path=checked_path(run,path/'jobs.sqlite3')
        try:
            (path/'jobs').mkdir(exist_ok=True)
            checked_path(run,path/'jobs'/'check')
            with self.db() as db:
                db.execute('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, idem TEXT UNIQUE, request TEXT, state TEXT, run TEXT, result TEXT, error TEXT)')
                db.execute('CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY, payload TEXT)')
                for source_id,payload in sources.items():
                    row=db.execute('SELECT payload FROM sources WHERE id=?',(source_id,)).fetchone()
                    if row and row['payload']!=canonical(payload):raise IntegrityError('Frozen source registry changed')
                    db.execute('INSERT OR IGNORE INTO sources VALUES(?,?)',(source_id,canonical(payload)))
                for row in db.execute('SELECT * FROM sources'):
                    self.sources[row['id']]=json.loads(row['payload'])
                db.execute('CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, job TEXT, time TEXT, state TEXT, note TEXT)')
                # Unfinished process may already have spent its resource budget; never rerun silently.
                for orphan in db.execute("SELECT * FROM jobs WHERE state IN ('RUNNING','QUEUED')").fetchall():
                    oldrun=existing_run(orphan['run'])
                    process_report=reconcile(oldrun.path)
                    oldrun.write_json('ProcessRecovery.json',process_report)
                    if (oldrun.path/'PipelineAdmission.json').is_file():
                        from a4x.workers.budget_scope import recover_identity
                        recover_identity(oldrun)
                    if (oldrun.path/'ledger.sqlite3').is_file():
                        context=json.loads(orphan['request'])['context']
                        BudgetLedger(oldrun,orphan['id'],context).recover()
                db.execute("UPDATE jobs SET state='UNKNOWN_INTERRUPTED',error='服务重启；需核对原工件和资源，不自动重新执行' WHERE state IN ('RUNNING','QUEUED')")
        except BaseException:
            self.pool.shutdown(wait=False)
            fcntl.flock(self.lock_fd,fcntl.LOCK_UN);os.close(self.lock_fd)
            raise
    @contextlib.contextmanager
    def db(self):
        checked_path(self.run,self.path)
        for suffix in ('-journal','-wal','-shm'):checked_path(self.run,str(self.path)+suffix)
        db=sqlite3.connect(self.path,timeout=30,isolation_level=None);db.row_factory=sqlite3.Row
        try:db.execute('BEGIN IMMEDIATE');yield db;db.commit()
        except BaseException:db.rollback();raise
        finally:db.close()
    def event(self,db,id,state,note=''):
        db.execute('INSERT INTO events VALUES(?,?,?,?,?)',(str(uuid.uuid4()),id,datetime.datetime.now(datetime.timezone.utc).isoformat(),state,note))
    def source(self,id):
        if id not in self.sources:raise ValueError('Unknown source ID')
        source=self.sources[id];verify_artifact(source['ref'],source['allowed_roots']);return source
    def register_package(self,ref,label):
        from a4x.pipeline import read_package,package_readiness
        from a4x.pipeline.packages import INPUT_ROOTS
        package,source,context=read_package(ref)
        id='package_'+ref['sha256']
        payload={'label':label,'ref':ref,'allowed_roots':[str(p) for p in INPUT_ROOTS],'kind':'pipeline_package','stage':package['stage']}
        with self.db() as db:
            row=db.execute('SELECT payload FROM sources WHERE id=?',(id,)).fetchone()
            if row and row['payload']!=canonical(payload):raise IntegrityError('Immutable package registration conflict')
            db.execute('INSERT OR IGNORE INTO sources VALUES(?,?)',(id,canonical(payload)))
        self.sources[id]=payload
        return {'id':id,'context':ref['sha256'],'stage':package['stage'],'readiness':package_readiness(package,source)}
    def create(self,request):
        source=self.source(request['source_id']) if request['source_id'] else None
        if source and source.get('kind')=='pipeline_package' and source['stage']!=request['stage']:raise ValueError('Registered package/stage mismatch')
        expected=source['ref']['sha256'] if source else 'offline-no-source-v1'
        if request['context']!=expected:raise ValueError('Frozen context mismatch')
        if request['stage']=='ingest' and source is None:raise ValueError('ingest needs source')
        if request['stage']=='data-policy-dev' and (source is None or source.get('kind')!='execution'):raise ValueError('Data development needs actual execution record')
        req=canonical(request);id=str(uuid.uuid4());runpath=self.run.path/'jobs'/id
        with self.db() as db:
            existing=db.execute('SELECT * FROM jobs WHERE idem=?',(request['idempotency_key'],)).fetchone()
            if existing:
                if existing['request']!=req:raise ValueError('Idempotency collision')
                payload=dict(existing)
                payload['request']=json.loads(payload['request']);payload['result']=json.loads(payload['result']) if payload['result'] else None
                return payload
            writer=RunDirectory(runpath)
            config={'schema_version':SCHEMA_VERSION,'allowed_input_roots':source['allowed_roots'] if source else [],'scope_dependencies':{}}
            writer.write_json('JobInput.json',{'stage':request['stage'],'context':expected,'input':source['ref'] if source else None,'config':config})
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',(id,request['idempotency_key'],req,'QUEUED',str(runpath),None,None));self.event(db,id,'QUEUED')
        self.pool.submit(self.execute,id)
        return self.get(id)
    def get(self,id):
        with self.db() as db:
            row=db.execute('SELECT * FROM jobs WHERE id=?',(id,)).fetchone()
            if row is None:raise KeyError(id)
            result=dict(row);result['result']=json.loads(result['result']) if result['result'] else None
            result['request']=json.loads(result['request']);return result
    def list(self):
        with self.db() as db:ids=[x['id'] for x in db.execute('SELECT id FROM jobs').fetchall()]
        return [self.get(id) for id in ids]
    def execute(self,id):
        job=self.get(id);request=job['request'];writer=existing_run(job['run'])
        try:
            package=None
            source=self.source(request['source_id']) if request['source_id'] else None
            if source and source.get('kind')=='pipeline_package':
                from a4x.pipeline import read_package,episode_ledger,package_readiness
                from a4x.workers.registry import package_profile
                package,actual,context=read_package(source['ref'])
                from a4x.workers.budget_scope import OwnedBudget
                ledger=OwnedBudget(episode_ledger(package),str(writer.path.relative_to(WORKSPACE)));ready=package_readiness(package,actual)
                ready.update(profile=package_profile(request['stage']),reason='; '.join(ready['missing_dependencies']))
            else:
                ledger=BudgetLedger(writer,id,request['context']);ready=readiness(request['stage'])
            admission='stage:'+id if package else 'stage' 
        except (ValueError,OSError,KeyError,TypeError) as error:
            failure={'stage':request['stage'],'status':'FAILED','outputs':[],'denominators':{},'reason':'INPUT_OR_AUTHORITY_INTEGRITY_FAILED: '+type(error).__name__}
            writer.write_json('StageResult.json',failure);self.finish(id,'FAILED',failure,failure['reason']);return
        if ready['status']!='READY_TO_RUN':
            result={'stage':request['stage'],'status':'NOT_READY','reason':ready['reason'],'outputs':[],'denominators':{},'physical_qualification':'NOT_RUN'}
            writer.write_json('StageResult.json',result);self.finish(id,'BLOCKED',result,ready['reason']);return
        try:
            if package is not None:
                from a4x.workers.budget_scope import record_identity
                record_identity(writer,ledger,str(writer.path.relative_to(WORKSPACE)))
            if not ledger.record_operation(admission,request=request):raise ValueError('Stage budget exceeded')
            with self.db() as db:
                changed=db.execute("UPDATE jobs SET state='RUNNING' WHERE id=? AND state='QUEUED'",(id,)).rowcount
                if not changed:return
                self.event(db,id,'RUNNING')
            started=time.monotonic()
            from a4x.workers.registry import worker_seconds
            deadline=worker_seconds(package)
            supervised=supervised_argv(writer,id,(command(request['stage'],writer.path,package=package) if package else command(request['stage'],writer.path)),**({'deadline_seconds':deadline} if deadline!=180 else {}))
            proc=subprocess.run(supervised,cwd=WORKSPACE,env=local_environment(cache_root=writer.path/'.runtime'),capture_output=True,text=True,timeout=deadline+5)
            logref=writer.write_json('WorkerLog.json',{'stdout':proc.stdout,'stderr':proc.stderr,'exit_code':proc.returncode,'interpreter_profile':ready['profile']})
            output=checked_path(writer,writer.path/'output'/'StageResult.json') if (writer.path/'output').is_dir() else writer.path/'output'/'StageResult.json'
            result=json.loads(output.read_text()) if output.is_file() else {'stage':request['stage'],'status':'FAILED','reason':'worker did not produce StageResult','outputs':[],'denominators':{}}
            readback_error=None
            try:
                self.validate_result(request['stage'],result,writer)
            except (ValueError,OSError,KeyError,TypeError) as error:
                readback_error=type(error).__name__+': '+str(error)
                result={'stage':request['stage'],'status':'FAILED','reason':'OUTPUT_READBACK_FAILED: '+readback_error,'outputs':[],'denominators':{}}
            result['worker_log_ref']=logref
            state='COMPLETED_SCOPE' if proc.returncode==0 and result['status']=='EXECUTED' else 'BLOCKED' if result['status']=='NOT_READY' else 'FAILED'
            ledger.settle(admission,admission+':receipt',{'host_inclusive_wall_seconds':time.monotonic()-started},{'exit_code':proc.returncode,'state':state,'result':result})
            if proc.returncode:ledger.recover()
            if request['stage']=='rollout' and state=='COMPLETED_SCOPE':
                for ref in result.get('outputs',[]):
                    source_id='execution_'+id
                    payload={'label':'实际 SO101 回放 '+id[:8],'ref':ref,'allowed_roots':[str(writer.path)],'kind':'execution'}
                    with self.db() as db:db.execute('INSERT INTO sources VALUES(?,?)',(source_id,canonical(payload)))
                    self.sources[source_id]=payload
            self.finish(id,state,result,result.get('reason'))
        except Exception as exc:
            reconcile(writer.path)
            ledger.recover()
            error=type(exc).__name__+': '+str(exc)
            writer.write_json('DispatcherFailure.json',{'status':'FAILED','reason':error,'resource_accounting':'UNKNOWN_RESERVATION_RETAINED'})
            self.finish(id,'FAILED',None,error)
    def validate_result(self,stage,result,writer):
        return validate_stage_result(stage,result,writer)
    def finish(self,id,state,result,error=None):
        with self.db() as db:
            db.execute('UPDATE jobs SET state=?,result=?,error=? WHERE id=?',(state,canonical(result) if result else None,error,id));self.event(db,id,state,error or '')
    def events(self,id):
        self.get(id)
        with self.db() as db:return [dict(x) for x in db.execute('SELECT * FROM events WHERE job=? ORDER BY time',(id,))]
    def artifacts(self,id):
        job=self.get(id);result=job['result'] or {};refs=[]
        for ref in result.get('outputs',[]):
            writer=existing_run(job['run'])
            checked_path(writer,ref['path']);verify_artifact(ref,[writer.path]);refs.append(ref)
        return refs
    def close(self):
        self.pool.shutdown(wait=True)
        fcntl.flock(self.lock_fd,fcntl.LOCK_UN);os.close(self.lock_fd)

    def logs(self,id):
        job=self.get(id);result=job['result'] or {};ref=result.get('worker_log_ref')
        if ref is None:return {'events':self.events(id),'worker_log':'NOT_RUN_OR_NOT_AVAILABLE'}
        run=existing_run(job['run']);checked_path(run,ref['path'])
        path=verify_artifact(ref,[run.path])
        return {'events':self.events(id),'worker_log':json.loads(path.read_text()),'ref':ref}
