#!/usr/bin/env python3
"""Fresh-host Compose operator. No credentials in argv, output, or Git."""
import argparse
import datetime as dt
import getpass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import secrets
import sqlite3
import subprocess
import tarfile
from urllib.parse import quote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'deploy/replica'
PRIVATE = ROOT / '.private/replica'
PG_IMAGE = 'postgres:17-bookworm@sha256:665dc7b37ac52a17e298511414c21d23ffa4e6a6ef6225b3e5d59c7afb35e994'


def run(args, *, data=None, output=None, check=True):
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith(('REPLICA_', 'COMPOSE_'))}
    result = subprocess.run(args, input=data, stdout=output or subprocess.PIPE,
                            stderr=subprocess.PIPE, cwd=ROOT, env=environment)
    if check and result.returncode:
        # Tool output can contain DSNs, cookies or request URLs. Never echo it.
        raise RuntimeError('Operation failed: ' + ' '.join(args[:2]) +
                           '. Inspect the service privately; credentials were not printed.')
    return result


def write_private(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise ValueError('Refusing symlink for private configuration')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
        stream.write(value)


def env_text(values):
    for key, value in values.items():
        if not re.fullmatch(r'[A-Z][A-Z0-9_]*', key) or any(c in str(value) for c in '\r\n\0'):
            raise ValueError('Invalid environment assignment')
    # app/database env files are read with Compose format: raw (2.30+).
    return ''.join(f'{key}={value}\n' for key, value in values.items())


def identifier(value):
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,47}', value):
        raise ValueError('Database names/users must be lowercase identifiers')
    return value


def origin_parts(value, proxy='nginx'):
    u = urlsplit(value)
    if (u.scheme != ('http' if proxy == 'direct' else 'https') or not u.hostname or u.username or u.password or u.query
            or u.fragment or u.path not in ('', '/') or not re.fullmatch(r'[A-Za-z0-9.:-]+', u.netloc)):
        raise ValueError('Use the selected mode\'s origin, without credentials or a path')
    port = u.port or (80 if proxy == 'direct' else 443)
    if proxy == 'direct':
        if u.hostname != '127.0.0.1':
            raise ValueError('Direct HTTP is loopback-only; use an SSH tunnel for remote access')
        return u, port
    if port != 443 and u.hostname not in ('localhost', '127.0.0.1'):
        raise ValueError('Public replicas use HTTPS port 443')
    return u, port


def trusted_database_network(name, owner, pinned=None):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', name or '') or not owner:
        raise ValueError('Database network needs a name and explicit Compose owner project')
    network = json.loads(run(['docker', 'network', 'inspect', name]).stdout)[0]
    labels = network.get('Labels') or {}
    if (not network.get('Internal') or network.get('Driver') != 'bridge'
            or network.get('Scope') != 'local'
            or labels.get('com.docker.compose.project') != owner
            or labels.get('com.docker.compose.network') != 'database'
            or pinned and network['Id'] != pinned):
        raise ValueError('Database network must be the pinned internal database network of the selected Compose owner')
    return dict(name=name, owner=owner, id=network['Id'])


def initialize(args):
    if os.name != 'posix':
        raise ValueError('Run setup on Linux/WSL so private files have real Unix permissions')
    if PRIVATE.exists():
        raise ValueError('Private replica directory already exists; nothing was overwritten')
    spec = json.loads((HERE / 'app.json').read_text())
    proxy = getattr(args, 'proxy', None) or ('none' if spec['kind'] == 'scraper' else 'nginx')
    if proxy not in ('nginx', 'direct', 'none'):
        raise ValueError('Unsupported proxy mode')
    if (spec['kind'] == 'scraper') != (proxy == 'none'):
        raise ValueError('Scraper uses --proxy none; web apps use --proxy nginx or direct')
    if args.with_browser and proxy != 'nginx':
        raise ValueError('Browser/demo gateway requires Nginx mode')
    if not args.origin:
        web_port = {'acc': 8080, 'job': 5173, 'decision': 3000, 'scraper': 8443}[spec['kind']]
        args.origin = f'http://127.0.0.1:{web_port}' if proxy == 'direct' else 'https://localhost:8443'
    project = args.project or spec['project']
    if not re.fullmatch(r'[a-z][a-z0-9-]{2,39}', project):
        raise ValueError('Invalid Compose project name')
    network = None
    if getattr(args, 'db_network', None):
        if args.database != 'existing':
            raise ValueError('--db-network is only for existing database mode')
        network = trusted_database_network(args.db_network, getattr(args, 'db_network_owner', None))
    u, port = origin_parts(args.origin, proxy)
    requested_api_port = getattr(args, 'direct_api_port', None)
    api_port = (8002 if spec['kind'] == 'decision' else 8001) if requested_api_port is None else requested_api_port
    if not 1024 <= api_port <= 65535 or proxy == 'direct' and spec['kind'] in ('job', 'decision') and port == api_port:
        raise ValueError('Direct API port must be 1024-65535 and different from the web port')
    database = identifier(args.db_name or spec['database'])
    user = identifier(args.db_user or spec['db_user'])
    if spec['kind'] == 'scraper' and user != 'vehicle_scraper':
        raise ValueError('Scraper runtime role must be vehicle_scraper')
    if not 1 <= args.db_port <= 65535 or args.database == 'new' and args.db_port != 5432:
        raise ValueError('Invalid database port (new private PostgreSQL uses 5432)')
    host = args.db_host if args.database == 'existing' else 'db'
    if not host or not re.fullmatch(r'[A-Za-z0-9._:-]+', host):
        raise ValueError('Existing mode requires --db-host reachable from Docker')
    password = getpass.getpass('Existing application DB password (hidden): ') if args.database == 'existing' else secrets.token_hex(32)
    if not password or any(c in password for c in '\r\n\0'):
        raise ValueError('Database password is required and must be one line')
    needs_access_password = spec['kind'] in ('acc', 'decision') or spec['kind'] == 'job' and proxy == 'nginx'
    access_password = getpass.getpass('NEW replica admin/access password (12+ characters, hidden): ') if needs_access_password else secrets.token_hex(24)
    if not 12 <= len(access_password) <= 128:
        raise ValueError('Use a new access password of 12-128 characters')
    if spec['kind'] == 'decision' and len(access_password.encode()) > 72:
        raise ValueError('Decision Engine bcrypt passwords may contain at most 72 UTF-8 bytes')
    runtime = dict(PGHOST=host, PGPORT=str(args.db_port), PGDATABASE=database, PGUSER=user,
                   PGPASSWORD=password, PGCONNECT_TIMEOUT='10', PGSSLMODE=args.db_sslmode,
                   TZ='Asia/Jakarta', PYTHONDONTWRITEBYTECODE='1', PYTHONUNBUFFERED='1')
    owner_password, owner_user = password, user
    if args.database == 'new':
        owner_user, owner_password = 'replica_admin', secrets.token_hex(32)
    elif args.db_admin_user:
        owner_user = identifier(args.db_admin_user)
        owner_password = getpass.getpass('Existing migration/backup DB owner password (hidden): ')
        if not owner_password:
            raise ValueError('Database owner password is required')
    elif spec['kind'] == 'scraper':
        raise ValueError('Existing scraper database needs --db-admin-user for additive schema migration')
    db_env = dict(runtime, PGUSER=owner_user, PGPASSWORD=owner_password)
    compose = dict(REPLICA_PROJECT=project, REPLICA_ORIGIN=args.origin.rstrip('/'),
                   REPLICA_DIRECT_WEB_PORT=str(port), REPLICA_DIRECT_API_PORT=str(api_port),
                   REPLICA_DIRECT_API_ORIGIN=f'http://127.0.0.1:{api_port}',
                   REPLICA_OPERATOR_UID=str(os.getuid() or 10001), REPLICA_OPERATOR_GID=str(os.getgid() or 10001),
                   REPLICA_BIND=f'{"127.0.0.1" if u.hostname in ("localhost", "127.0.0.1") else "0.0.0.0"}:{port}:8443',
                   REPLICA_DB_NAME=database, REPLICA_DB_USER=owner_user,
                   REPLICA_DOCKER_GID=str(Path('/var/run/docker.sock').stat().st_gid) if Path('/var/run/docker.sock').exists() else '0')
    driver = 'asyncpg' if spec['kind'] == 'decision' else 'psycopg'
    # SQLAlchemy/asyncpg uses ssl= rather than libpq sslmode=.
    ssl_query = ('ssl' if driver == 'asyncpg' else 'sslmode') + '=' + args.db_sslmode
    dsn = f'postgresql+{driver}://{quote(user, safe="")}:{quote(password, safe="")}@{host}:{args.db_port}/{database}?{ssl_query}'
    if spec['kind'] == 'job':
        runtime.update(OSCAR_ENV='production', OSCAR_DATABASE_URL=dsn,
                       OSCAR_API_KEY=secrets.token_hex(32), OPENAI_API_KEY='',
                       OSCAR_STORAGE_DIR='/data/pdfs', OSCAR_LOG_DIR='/data/logs',
                       OSCAR_CORS_ORIGINS=args.origin.rstrip('/'))
    elif spec['kind'] == 'decision':
        runtime.update(OSCAR_ENVIRONMENT='production', OSCAR_DATABASE_URL=dsn,
                       OSCAR_JWT_SECRET=secrets.token_hex(48), OSCAR_ENABLE_DEMO_SEED='false',
                       OSCAR_CORS_ORIGINS=json.dumps([args.origin.rstrip('/')]))
    elif spec['kind'] == 'scraper':
        runtime.update(SCRAPING_BROWSER_BACKEND='direct', BRIGHTDATA_BROWSER_WS_ENDPOINT='',
                       BRIGHTDATA_LOCATION='auto', BRIGHTDATA_MAX_BYTES='20971520',
                       SCRAPING_EMAIL_ENABLED='0', SMTP_USERNAME='', SMTP_APP_PASSWORD='',
                       SCRAPING_STATE_DIR='/scheduler', SCRAPING_MAX_ITEMS='3',
                       SCRAPING_SCHEDULER_OWNER='standalone')
    else:
        salt = secrets.token_hex(16)
        hashed = hashlib.scrypt(access_password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1, dklen=32).hex()
        runtime.update(ACC_MODE='docker', ACC_ADMIN_USER='oscar',
                       ACC_ADMIN_PASSWORD_HASH=f'scrypt:{salt}:{hashed}', ACC_AGENT_TOKEN=secrets.token_hex(48),
                       ACC_PUBLIC_ORIGIN=args.origin.rstrip('/'), ACC_AGENT_URL='http://agent:9090',
                       ACC_WEB_STATE='/state', ACC_AGENT_STATE='/state', ACC_CATALOG='/config/catalog.json',
                       ACC_POLICY='/config/policy.json', ACC_INSTALLED_CATALOG='/registry/installed-apps.json')
    PRIVATE.mkdir(parents=True, mode=0o700)
    write_private(PRIVATE / 'app.env', env_text(runtime))
    write_private(PRIVATE / 'database.env', env_text(db_env))
    write_private(PRIVATE / 'compose.env', env_text(compose))
    write_private(PRIVATE / 'database_password', owner_password)
    metadata = dict(kind=spec['kind'], project=project, database_mode=args.database,
                    database=database, db_user=user, origin=args.origin.rstrip('/'), with_browser=args.with_browser,
                    proxy=proxy, direct_api_port=api_port)
    if network:
        metadata['database_network'] = network
    write_private(PRIVATE / 'settings.json', json.dumps(metadata, indent=2) + '\n')
    if network:
        write_private(PRIVATE / 'networks.json', json.dumps({'networks': {'database': {
            'external': True, 'internal': False, 'name': network['name']}}}) + '\n')
    if proxy == 'nginx':
        (PRIVATE / 'tls').mkdir(mode=0o700)
    if proxy == 'nginx' and os.getuid() == 0:
        os.chown(PRIVATE / 'tls', 10001, 10001)
    if spec['kind'] == 'job' and proxy == 'nginx':
        hashed = run(['openssl', 'passwd', '-6', '-stdin'], data=access_password.encode()).stdout.decode().strip()
        write_private(PRIVATE / 'htpasswd', 'oscar:' + hashed + '\n')
        if os.getuid() == 0:
            os.chown(PRIVATE / 'htpasswd', 10001, 10001)
    if spec['kind'] == 'job':
        write_private(PRIVATE / 'web.env', env_text(dict(API_BASE_URL='http://api:8000/api/v1',
                     API_KEY=runtime['OSCAR_API_KEY'], OSCAR_APP_MODE='production', ORIGIN=args.origin.rstrip('/'), HOST='0.0.0.0', PORT='5173')))
    if spec['kind'] == 'decision':
        write_private(PRIVATE / 'admin.json', json.dumps({'username': 'oscar', 'password': access_password}))
    if args.database == 'new':
        # Only executed by the official image on a new, empty named volume.
        sql = f"CREATE ROLE {user} LOGIN PASSWORD '{password}';\nALTER DATABASE {database} OWNER TO {user};\nALTER SCHEMA public OWNER TO {user};\n"
        if spec['kind'] == 'scraper':
            sql = f"CREATE ROLE vehicle_scraper LOGIN PASSWORD '{password}';\nCREATE ROLE acc_owner NOLOGIN;\n"
        write_private(PRIVATE / 'init.sql', sql)
        # Parent directory is 0700; PostgreSQL's unprivileged initializer must read this bind mount.
        (PRIVATE / 'init.sql').chmod(0o644)
    if spec['kind'] == 'acc':
        catalogue = json.loads((ROOT / 'config/catalog.json').read_text())
        for app in catalogue:
            app.setdefault('availability', 'ready')
            app['public_url'] = args.origin.rstrip('/') + '/'
            if app['id'] == 'browser-automation' and not args.with_browser:
                app['availability'] = 'planned'
                for key in ('container', 'image', 'command', 'healthcheck_command', 'host_port'):
                    app[key] = None
                app['environment'] = {}
            if app.get('kind') == 'core':
                app['container'] = {'reverse-proxy': project + '-edge-1', 'control-center': project + '-web-1', 'runtime-agent': project + '-agent-1'}.get(app['id'], app.get('container'))
            if app['id'] == 'postgresql' and args.database == 'new':
                app['availability'] = 'ready'
                app['container'] = project + '-db-1'
            if proxy == 'direct' and (app.get('kind') in ('demo', 'scheduled') or app['id'] == 'reverse-proxy'):
                app['availability'] = 'disabled' if app['id'] == 'reverse-proxy' else 'planned'
                for key in ('container', 'image', 'command', 'healthcheck_command', 'host_port'):
                    app[key] = None
                app['environment'] = {}
        write_private(PRIVATE / 'catalog.json', json.dumps(catalogue, indent=2) + '\n')
        write_private(PRIVATE / 'policy.json', (ROOT / 'config/policy.json').read_text())
        (PRIVATE / 'registry').mkdir(mode=0o755)
        write_private(PRIVATE / 'registry/installed-apps.json', '[]\n')
        config = (ROOT / 'deploy/nginx.public.conf').read_text()
        config = config.replace('server_name PUBLIC_IP;', 'server_name PUBLIC_HOST;').replace('if ($host != PUBLIC_IP)', 'if ($host != PUBLIC_HOST)')
        config = config.replace('PUBLIC_WEB_BACKEND', 'web:8080').replace('PUBLIC_ORIGIN', args.origin.rstrip('/')).replace('PUBLIC_IP', u.netloc).replace('PUBLIC_HOST', u.hostname)
        # Existing auth, demo lease checks, opaque sandbox and WebSocket routes stay intact.
        write_private(PRIVATE / 'nginx.conf', config)
        # Nonsecret mounts are readable by the existing uid 10001 images.
        for name in ('catalog.json', 'policy.json', 'nginx.conf', 'registry/installed-apps.json'):
            (PRIVATE / name).chmod(0o644)
    print('Created private replica configuration. No existing configuration was replaced.')
    if proxy == 'nginx':
        print('Install TLS fullchain.pem and privkey.pem in .private/replica/tls, then run check/build/migrate/up.')
    else:
        print('Run check/build/migrate/up. Direct web ports bind only to 127.0.0.1; scraper has no web port.')


def configuration():
    if PRIVATE.is_symlink() or not (PRIVATE / 'settings.json').is_file():
        raise ValueError('Run init first')
    if os.name != 'posix' or PRIVATE.stat().st_mode & 0o077:
        raise ValueError('Private replica directory must be mode 0700 on Linux')
    for name in ('compose.env', 'app.env', 'database.env', 'database_password'):
        p = PRIVATE / name
        if p.is_symlink() or p.stat().st_mode & 0o077:
            raise ValueError('Private credential files must be regular, mode 0600')
    settings = json.loads((PRIVATE / 'settings.json').read_text())
    if settings.get('database_network'):
        n = settings['database_network']
        trusted_database_network(n['name'], n['owner'], n['id'])
    elif (PRIVATE / 'networks.json').exists():
        raise ValueError('Unregistered database network override')
    return settings


def command(settings):
    cmd = ['docker', 'compose', '--project-directory', str(ROOT), '--env-file', str(PRIVATE / 'compose.env'),
           '-p', settings['project'], '-f', str(HERE / 'compose.yaml')]
    if settings['database_mode'] == 'new':
        cmd += ['--profile', 'database']
    proxy = settings.get('proxy', 'none' if settings['kind'] == 'scraper' else 'nginx')
    if proxy == 'nginx':
        cmd += ['--profile', 'nginx']
    elif proxy == 'direct':
        cmd += ['-f', str(HERE / 'compose.direct.yaml')]
    if settings.get('database_network'):
        cmd += ['-f', str(PRIVATE / 'networks.json')]
    return cmd


def db_run(cmd, args, **kwargs):
    return run(cmd + ['run', '--rm', '--no-deps', '-T', 'db-tools'] + args, **kwargs)


def fresh_only(settings):
    existing = run(['docker', 'ps', '-aq', '--filter', 'label=com.docker.compose.project=' + settings['project']]).stdout.strip()
    if existing:
        raise ValueError('Project already has containers. Refusing an implicit upgrade/restart; back up and review the upgrade separately.')


def prepare_acc(cmd, settings):
    catalog_path = PRIVATE / 'catalog.json'
    catalog = json.loads(catalog_path.read_text())
    image = run(cmd + ['images', '-q', 'web']).stdout.decode().strip()
    if not image:
        image = run(['docker', 'image', 'inspect', settings['project'] + '-acc:local', '--format', '{{.Id}}']).stdout.decode().strip()
    ledger_path = PRIVATE / 'provision.json'
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {'networks': {}, 'containers': {}}
    def save_ledger():
        temporary = PRIVATE / 'provision.new'
        with temporary.open('w') as stream:
            json.dump(ledger, stream)
        temporary.chmod(0o600)
        os.replace(temporary, ledger_path)
    managed = [app for app in catalog if app.get('kind') in ('demo', 'scheduled') and app.get('availability') == 'ready']
    for app in managed:
        if app['id'] != 'browser-automation':
            app['image'] = image
        existing = run(['docker', 'inspect', app['container']], check=False)
        if existing.returncode == 0:
            value = json.loads(existing.stdout)[0]
            if ledger['containers'].get(app['container']) != value['Id']:
                raise ValueError('An existing managed container belongs to another ACC deployment')
    network_specs = {app['container']: (app['id'], app.get('network_internal', True)) for app in managed}
    # Ingress has a browser interface even when the optional runtime is not installed.
    network_specs.setdefault('acc-demo-browser-automation', ('browser-automation', False))
    for name, (app_id, internal) in network_specs.items():
        result = run(['docker', 'network', 'inspect', name], check=False)
        if result.returncode:
            args = ['docker', 'network', 'create', '--label', 'acc.app=' + app_id,
                    '--label', 'oscar.replica.project=' + settings['project']]
            if internal:
                args += ['--internal']
            ledger['networks'][name] = run(args + [name]).stdout.decode().strip()
            save_ledger()
        else:
            network = json.loads(result.stdout)[0]
            labels = network.get('Labels') or {}
            if (ledger['networks'].get(name) != network['Id']
                    or labels.get('oscar.replica.project') != settings['project']
                    or labels.get('acc.app') != app_id or bool(network.get('Internal')) != internal):
                raise ValueError('A managed network belongs to another ACC deployment')
    catalog_path.write_text(json.dumps(catalog, indent=2) + '\n')
    run(['docker', 'run', '--rm', '--network', 'none', '--read-only', '--cap-drop', 'ALL',
         '--security-opt', 'no-new-privileges', '--group-add', str(Path('/var/run/docker.sock').stat().st_gid),
         '-v', '/var/run/docker.sock:/var/run/docker.sock', '-v', str(catalog_path) + ':/config/catalog.json:ro',
         image, 'python', '-m', 'acc.provision', '--apply'])
    for app in managed:
        value = json.loads(run(['docker', 'inspect', app['container']]).stdout)[0]
        ledger['containers'][app['container']] = value['Id']
    save_ledger()


def migrate(cmd, settings):
    if settings['database_mode'] == 'new':
        run(cmd + ['up', '-d', '--wait', 'db'])
    if settings['kind'] == 'scraper':
        sql = (ROOT / 'deploy/scraping/schema.sql').read_text().replace('ON DATABASE server_internal', 'ON DATABASE "' + settings['database'] + '"')
        db_run(cmd, ['psql', '-X', '-v', 'ON_ERROR_STOP=1', '--single-transaction'], data=sql.encode())
    elif settings['kind'] in ('job', 'decision'):
        run(cmd + ['run', '--rm', '--no-deps', '-T', 'api', 'python', '-m', 'alembic', 'upgrade', 'head'])
    else:
        db_run(cmd, ['psql', '-X', '-v', 'ON_ERROR_STOP=1', '-Atqc', 'SELECT 1'])
    print('Database migration/connectivity check completed; existing databases/volumes were retained.')
    (PRIVATE / 'migration-completed').touch(mode=0o600)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def backup(cmd, settings):
    target = ROOT / 'backups/replica' / (dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + secrets.token_hex(3))
    target.mkdir(parents=True, mode=0o700)
    with (target / 'database.dump').open('xb') as stream:
        db_run(cmd, ['pg_dump', '-Fc', '--no-owner', '--no-acl'], output=stream)
    if settings['kind'] == 'acc':
        for service, name in (('web', 'auth'), ('agent', 'controller')):
            script = "import sqlite3,tempfile,sys,pathlib; p=tempfile.mktemp(); s=sqlite3.connect('/state/" + name + ".sqlite3'); d=sqlite3.connect(p); s.backup(d); d.close(); s.close(); sys.stdout.buffer.write(pathlib.Path(p).read_bytes()); pathlib.Path(p).unlink()"
            with (target / (name + '.sqlite3')).open('xb') as stream:
                run(cmd + ['exec', '-T', service, 'python', '-c', script], output=stream)
        with tarfile.open(target / 'config.tar.gz', 'w:gz') as archive:
            for name in ('catalog.json', 'policy.json', 'registry/installed-apps.json'):
                archive.add(PRIVATE / name, arcname=name)
    elif settings['kind'] == 'job':
        script = "import tarfile,sys; t=tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz'); t.add('/data/pdfs',arcname='pdfs'); t.close()"
        with (target / 'documents.tar.gz').open('xb') as stream:
            run(cmd + ['exec', '-T', 'api', 'python', '-c', script], output=stream)
    manifest = dict(version=1, kind=settings['kind'], project=settings['project'], database=settings['database'], files={p.name: digest(p) for p in target.iterdir()})
    for p in target.iterdir():
        p.chmod(0o600)
    write_private(target / 'manifest.json', json.dumps(manifest, indent=2) + '\n')
    print('Backup saved to', target.relative_to(ROOT), '(contains private application data; encrypt before off-host storage).')


def verify_backup(target):
    manifest = json.loads((target / 'manifest.json').read_text())
    if manifest.get('version') != 1 or not manifest.get('files') or 'database.dump' not in manifest['files']:
        raise ValueError('Invalid backup manifest')
    for name, checksum in manifest['files'].items():
        if Path(name).name != name or name in ('.', '..'):
            raise ValueError('Invalid backup path')
        p = target / name
        if p.is_symlink() or digest(p) != checksum:
            raise ValueError('Backup checksum mismatch')
        if p.suffix == '.sqlite3':
            with sqlite3.connect('file:' + str(p) + '?mode=ro', uri=True) as db:
                if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError('SQLite integrity check failed')
        if name.endswith('.tar.gz'):
            with tarfile.open(p) as archive:
                for member in archive:
                    path = PurePosixPath(member.name)
                    windows = PureWindowsPath(member.name)
                    if path.is_absolute() or windows.root or windows.drive or '..' in path.parts or '..' in windows.parts or not (member.isfile() or member.isdir()):
                        raise ValueError('Unsafe backup archive member')
    return manifest


def restore_check(target):
    verify_backup(target)
    name = 'replica-restore-' + secrets.token_hex(10)
    created_id = None
    try:
        created_id = run(['docker', 'run', '-d', '--name', name, '--network', 'none', '--memory', '384m', '--cpus', '0.3',
                          '--label', 'oscar.replica.restore=' + name, '-e', 'POSTGRES_HOST_AUTH_METHOD=trust', PG_IMAGE]).stdout.decode().strip()
        import time
        for _ in range(60):
            # The image's temporary init server has only a Unix socket. TCP
            # readiness waits for the final server, avoiding a restart race.
            if run(['docker', 'exec', name, 'pg_isready', '-h', '127.0.0.1', '-U', 'postgres'], check=False).returncode == 0:
                break
            time.sleep(1)
        else:
            raise ValueError('Isolated restore database did not start')
        run(['docker', 'exec', name, 'createdb', '-h', '127.0.0.1', '-U', 'postgres', 'restore_check'])
        with (target / 'database.dump').open('rb') as stream:
            result = subprocess.run(['docker', 'exec', '-i', name, 'pg_restore', '-U', 'postgres', '-d', 'restore_check', '--exit-on-error', '--no-owner', '--no-acl'], stdin=stream, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if result.returncode:
            raise ValueError('Restore into isolated database failed')
        print('Backup restored successfully into an isolated temporary PostgreSQL; production was not changed.')
    finally:
        if created_id:
            inspected = json.loads(run(['docker', 'inspect', name]).stdout)[0]
            if inspected['Id'] != created_id or inspected['Config']['Labels'].get('oscar.replica.restore') != name:
                raise ValueError('Refusing cleanup: restore container identity changed')
            run(['docker', 'rm', '-fv', name])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['init', 'check', 'build', 'migrate', 'bootstrap-admin', 'up', 'status', 'backup', 'restore-check'])
    p.add_argument('--origin')
    p.add_argument('--proxy', choices=['nginx', 'direct', 'none'])
    p.add_argument('--direct-api-port', type=int)
    p.add_argument('--project')
    p.add_argument('--database', choices=['new', 'existing'], default='new')
    p.add_argument('--db-host')
    p.add_argument('--db-network')
    p.add_argument('--db-network-owner')
    p.add_argument('--db-name')
    p.add_argument('--db-user')
    p.add_argument('--db-admin-user')
    p.add_argument('--db-port', type=int, default=5432)
    p.add_argument('--db-sslmode', choices=['disable', 'require', 'verify-full'], default='require')
    p.add_argument('--with-browser', action='store_true')
    p.add_argument('--backup-dir', type=Path)
    args = p.parse_args()
    if args.action == 'init':
        if args.database == 'new':
            args.db_sslmode = 'disable'  # Private Docker network, no host port.
        initialize(args)
        return
    if args.action == 'restore-check':
        if not args.backup_dir:
            p.error('--backup-dir is required')
        restore_check(args.backup_dir.resolve())
        return
    settings = configuration()
    cmd = command(settings)
    run(cmd + ['config', '--quiet'])
    if args.action == 'check':
        print('Compose and private permissions valid. No containers were changed.')
    elif args.action == 'build':
        run(cmd + ['build', '--pull'])
    elif args.action == 'migrate':
        migrate(cmd, settings)
    elif args.action == 'bootstrap-admin':
        if settings['kind'] != 'decision':
            raise ValueError('Only Decision Engine uses bootstrap-admin')
        data = (PRIVATE / 'admin.json').read_bytes()
        run(cmd + ['run', '--rm', '--no-deps', '-T', 'api', 'python', '/operator/bootstrap_admin.py'], data=data)
        (PRIVATE / 'admin.json').unlink()
        print('Created first administrator and canonical RBAC; no demo policy/users were seeded.')
    elif args.action == 'up':
        # migrate may already have created only the database/one-off containers.
        raw = run(cmd + ['ps', '-a', '--format', 'json']).stdout.decode().strip()
        services = json.loads(raw) if raw.startswith('[') else [json.loads(line) for line in raw.splitlines()]
        if any(s.get('Service') != 'db' for s in services):
            raise ValueError('Refusing an implicit restart of existing application containers')
        if not (PRIVATE / 'migration-completed').is_file():
            raise ValueError('Run migrate before starting the application')
        proxy = settings.get('proxy', 'none' if settings['kind'] == 'scraper' else 'nginx')
        if proxy == 'nginx':
            for name in ('fullchain.pem', 'privkey.pem'):
                if not (PRIVATE / 'tls' / name).is_file():
                    raise ValueError('Install TLS certificates before starting HTTPS')
        if settings['kind'] == 'acc' and proxy == 'nginx':
            prepare_acc(cmd, settings)
        run(cmd + ['up', '-d', '--no-build', '--wait', '--wait-timeout', '120'])
        print('Replica started. Verify the selected mode and application access before declaring deployment complete.')
    elif args.action == 'status':
        print(run(cmd + ['ps']).stdout.decode(), end='')
    elif args.action == 'backup':
        backup(cmd, settings)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError) as error:
        raise SystemExit(str(error))
