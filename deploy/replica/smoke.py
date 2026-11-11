"""Opt-in real Docker test of one replica package, using disposable owned resources."""
import argparse
import base64
import contextlib
import getpass
import importlib.util
import io
import json
import os
from pathlib import Path
import secrets
import shutil
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from unittest.mock import patch

PASSWORD='fixture-'+secrets.token_hex(16)


def load(path):
    spec=importlib.util.spec_from_file_location('replica_operator',path)
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def source_copy(root,target):
    names=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=root).decode().split('\0')
    for name in sorted(set(names)-{''}):
        if name.startswith(('.private/','.env','backups/','artifacts/')) or '/.env' in name:
            continue
        p=root/name
        if not p.is_file() or p.is_symlink():
            continue
        dest=target/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(p,dest)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-disposable-docker',action='store_true')
    parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--proxy',choices=['nginx','direct','none'],default='nginx')
    args=parser.parse_args()
    if not args.allow_disposable_docker:
        parser.error('Requires --allow-disposable-docker; never run against production Docker')
    root=args.repo.resolve()
    original=load(root/'deploy/replica/manage.py')
    kind=json.loads((root/'deploy/replica/app.json').read_text())['kind']
    proxy='none' if kind=='scraper' else args.proxy
    if proxy=='none' and kind!='scraper':
        parser.error('Web apps use nginx or direct')
    original.run([sys.executable,str(root/'deploy/replica/test_manage.py')])
    work=Path(tempfile.mkdtemp(prefix='oscar-replica-test-'))
    checkout=work/'source'
    source_copy(root,checkout)
    m=load(checkout/'deploy/replica/manage.py')
    project='rep-test-'+kind+'-'+secrets.token_hex(5)
    # Ephemeral loopback port, not a public listener.
    import socket
    with socket.socket() as s:
        s.bind(('127.0.0.1',0))
        port=s.getsockname()[1]
    with socket.socket() as s:
        s.bind(('127.0.0.1',0))
        api_port=s.getsockname()[1]
    if api_port==port:
        raise RuntimeError('Temporary web/API port collision; rerun the disposable test')
    origin=f'http://127.0.0.1:{port}' if proxy=='direct' else f'https://localhost:{port}'
    api_origin=f'http://127.0.0.1:{api_port}' if proxy=='direct' else origin
    init=argparse.Namespace(project=project,origin=origin,database='new',db_name=None,db_user=None,
                            db_host=None,db_port=5432,db_sslmode='disable',db_admin_user=None,with_browser=False,
                            proxy=proxy,direct_api_port=api_port)
    with patch.object(getpass,'getpass',return_value=PASSWORD), contextlib.redirect_stdout(io.StringIO()):
        m.initialize(init)
    settings=m.configuration()
    cmd=m.command(settings)
    # Fixture suppresses navigation only in this disposable scheduler container.
    # Production entrypoint and configuration are validated independently below.
    if kind=='scraper':
        override={'services':{'scheduler':{'entrypoint':['python','-c',
                 'import scheduled_scraping.daily as d; d.due_day=lambda now: None; d.main()']}}}
        f=work/'offline-scheduler.json'
        f.write_text(json.dumps(override))
        cmd+=['-f',str(f)]
    report={'kind':kind,'proxy':proxy,'new_database':False,'existing_database':False,'https':False,'http_loopback':False,
            'backup_restore':False,'resource_enforced':False,'production_changed':False}
    e,ec=None,None
    try:
        resolved=json.loads(m.run(cmd+['config','--format','json']).stdout)
        for name,service in resolved['services'].items():
            assert service.get('mem_limit') and service.get('cpus') and service.get('pids_limit'),name
            if proxy=='direct' and name in ('web','api'):
                assert all(p['host_ip']=='127.0.0.1' for p in service.get('ports',[])),name
            elif name!='edge':
                assert not service.get('ports'),name
        if proxy=='direct':
            assert 'edge' not in resolved['services']
        if proxy=='nginx':
            tls=m.PRIVATE/'tls'
            m.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=localhost',
                   '-addext','subjectAltName=DNS:localhost','-keyout',str(tls/'privkey.pem'),'-out',str(tls/'fullchain.pem')])
            (tls/'privkey.pem').chmod(0o600)
            if os.getuid()==0:
                for f in tls.iterdir():
                    os.chown(f,10001,10001)
        print(kind+': building actual images',flush=True)
        # Build has no runtime credentials/build secrets. Preserve only sanitized failure details.
        result=subprocess.run(cmd+['build'],cwd=checkout,capture_output=True)
        if result.returncode:
            print(result.stderr.decode(errors='replace')[-5000:],file=sys.stderr)
            raise RuntimeError('Replica image build failed')
        m.migrate(cmd,settings)
        report['new_database']=True
        if kind=='decision':
            m.run(cmd+['run','--rm','--no-deps','-T','api','python','/operator/bootstrap_admin.py'],data=(m.PRIVATE/'admin.json').read_bytes())
            # A second bootstrap must refuse and leave the first administrator intact.
            assert m.run(cmd+['run','--rm','--no-deps','-T','api','python','/operator/bootstrap_admin.py'],data=(m.PRIVATE/'admin.json').read_bytes(),check=False).returncode!=0
        if kind=='scraper':
            m.run(cmd+['up','-d','--no-build','--wait','--wait-timeout','150'])
        else:
            m.run([sys.executable,str(checkout/'deploy/replica/manage.py'),'up'])
        if kind=='job':
            m.run(cmd+['exec','-T','api','python','-c',"from pathlib import Path; Path('/data/pdfs/replica-fixture.pdf').write_bytes(b'Synthetic backup fixture')"])
        if kind!='scraper':
            context=ssl.create_default_context(cafile=str(m.PRIVATE/'tls/fullchain.pem')) if proxy=='nginx' else None
            import http.cookiejar
            cookies=http.cookiejar.CookieJar()
            opener=urllib.request.build_opener(urllib.request.HTTPSHandler(context=context),urllib.request.HTTPCookieProcessor(cookies))
            def request(path,data=None,headers=None,base=None):
                h={'Origin':origin,**(headers or {})}
                if data is not None:
                    h['Content-Type']='application/json'
                req=urllib.request.Request((base or origin)+path,data=json.dumps(data).encode() if data is not None else None,headers=h)
                with opener.open(req,timeout=30) as response:
                    return response.status,response.read()
            if kind=='job':
                header={}
                if proxy=='nginx':
                    try:
                        request('/jobs')
                        raise AssertionError('Anonymous Job AI access was allowed')
                    except urllib.error.HTTPError as error:
                        assert error.code==401
                    header={'Authorization':'Basic '+base64.b64encode(('oscar:'+PASSWORD).encode()).decode()}
                assert request('/jobs',headers=header)[0]==200
                key=next(line.split('=',1)[1] for line in (m.PRIVATE/'app.env').read_text().splitlines() if line.startswith('OSCAR_API_KEY='))
                assert request('/api/v1/jobs',headers={**header,'X-API-Key':key},base=api_origin)[0]==200
                if proxy=='direct':
                    try:
                        request('/api/v1/jobs',base=api_origin)
                        raise AssertionError('Direct API accepted a request without an API key')
                    except urllib.error.HTTPError as error:
                        assert error.code==401
            elif kind=='decision':
                assert request('/login')[0]==200
                path='/v1/auth/login' if proxy=='direct' else '/backend/v1/auth/login'
                status,payload=request(path,{'username':'oscar','password':PASSWORD},base=api_origin)
                assert status==200 and json.loads(payload)['access_token']
                if proxy=='direct':
                    preflight=urllib.request.Request(api_origin+'/v1/auth/login',method='OPTIONS',headers={
                        'Origin':origin,'Access-Control-Request-Method':'POST',
                        'Access-Control-Request-Headers':'content-type,authorization'})
                    with opener.open(preflight,timeout=15) as response:
                        assert response.headers['Access-Control-Allow-Origin']==origin
            else:
                assert request('/healthz')[0]==200
                try:
                    request('/api/admin/users')
                    raise AssertionError('Anonymous admin access was allowed')
                except urllib.error.HTTPError as error:
                    assert error.code in (401,403)
                assert request('/api/auth/login',{'username':'oscar','password':PASSWORD})[0]==200
                assert request('/api/admin/users')[0]==200
                assert request('/api/state')[0]==200
            report['https']=proxy=='nginx'
            report['http_loopback']=proxy=='direct'
        else:
            result=m.db_run(cmd,['psql','-X','-Atqc',"SELECT count(*) FROM information_schema.tables WHERE table_schema='scraping'"])
            assert int(result.stdout)==10
            report['scheduler_offline_health']=True
        service='scheduler' if kind=='scraper' else 'api' if kind in ('job','decision') else 'agent'
        identifier=m.run(cmd+['ps','-q',service]).stdout.decode().strip()
        # Operator-only read works even when the service uid cannot inspect sysfs.
        capped=m.run(['docker','exec','--user','0',identifier,'python','-c',
                      'from pathlib import Path; p=Path("/sys/fs/cgroup/memory.max"); p=p if p.exists() else Path("/sys/fs/cgroup/memory/memory.limit_in_bytes"); print(p.read_text())'],check=False)
        expected=int(resolved['services'][service]['mem_limit'])
        report['resource_enforced']=capped.returncode==0 and capped.stdout.strip()==str(expected).encode()
        if os.getenv('REPLICA_REQUIRE_CGROUP')=='1':
            assert report['resource_enforced'],'Kernel did not enforce the Docker memory cgroup'
        m.backup(cmd,settings)
        backup=next((checkout/'backups/replica').iterdir())
        m.restore_check(backup)
        report['backup_restore']=True
        # Existing mode reuses the first project's DB and applies idempotent migrations.
        first_id=m.run(cmd+['ps','-q','db']).stdout.decode().strip()
        existing=work/'existing'
        source_copy(root,existing)
        e=load(existing/'deploy/replica/manage.py')
        values={}
        for line in (m.PRIVATE/'app.env').read_text().splitlines():
            key,_,value=line.partition('='); values[key]=value
        owner={}
        for line in (m.PRIVATE/'database.env').read_text().splitlines():
            key,_,value=line.partition('='); owner[key]=value
        ei=argparse.Namespace(**vars(init))
        ei.database='existing'; ei.project=project+'-existing'; ei.db_host='db'
        ei.db_network=project+'_database'; ei.db_network_owner=project
        ei.db_admin_user=owner['PGUSER'] if kind=='scraper' else None
        answers=[values['PGPASSWORD']]
        if kind in ('acc','decision') or kind=='job' and proxy=='nginx':
            answers.append(PASSWORD)
        if kind=='scraper':
            answers.append(owner['PGPASSWORD'])
        with patch.object(getpass,'getpass',side_effect=answers),contextlib.redirect_stdout(io.StringIO()):
            e.initialize(ei)
        ec=e.command(e.configuration())
        e.run(ec+['config','--quiet'])
        e.migrate(ec,e.configuration())
        assert m.run(cmd+['ps','-q','db']).stdout.decode().strip()==first_id
        report['existing_database']=True
        # Existing apps cannot be accidentally restarted through the fresh-host helper.
        before=m.run(cmd+['ps','-q']).stdout
        refusal=m.run([sys.executable,str(checkout/'deploy/replica/manage.py'),'up'],check=False)
        assert refusal.returncode!=0
        assert m.run(cmd+['ps','-q']).stdout==before
        print(json.dumps(report),flush=True)
        artifact=root/'artifacts'/('replica-smoke-'+proxy+'.json')
        artifact.parent.mkdir(exist_ok=True)
        artifact.write_text(json.dumps(report,indent=2)+'\n')
    except BaseException:
        print('Replica smoke failed for '+kind+'. Disposable source: '+str(checkout),file=sys.stderr)
        # IDs/status contain no environment values or application payloads.
        print(m.run(cmd+['ps','-a'],check=False).stdout.decode(),file=sys.stderr)
        if proxy=='nginx':
            # The edge logs no request URLs/auth values and has no application secrets.
            print(m.run(cmd+['logs','--no-color','--tail','20','edge'],check=False).stdout.decode(),file=sys.stderr)
        raise
    finally:
        # Cleanup is limited to this random disposable project and validated demo IDs.
        if ec is not None:
            e.run(ec+['down','--volumes','--remove-orphans'],check=False)
        ledger_path=m.PRIVATE/'provision.json'
        ledger=json.loads(ledger_path.read_text()) if ledger_path.exists() else {'containers':{},'networks':{}}
        for name,owned_id in ledger['containers'].items():
            assert name.startswith(('acc-demo-','acc-scheduled-'))
            inspected=m.run(['docker','inspect',name],check=False)
            if inspected.returncode==0:
                value=json.loads(inspected.stdout)[0]
                assert value['Id']==owned_id
                assert value['Config']['Labels'].get('acc.managed')=='true'
                m.run(['docker','rm','-f',value['Id']])
        m.run(cmd+['down','--volumes','--remove-orphans'],check=False)
        if kind=='acc':
            for name,owned_id in ledger['networks'].items():
                value=json.loads(m.run(['docker','network','inspect',name]).stdout)[0]
                assert value['Id']==owned_id and value['Labels'].get('oscar.replica.project')==project
                m.run(['docker','network','rm',name],check=False)


if __name__=='__main__':
    main()
