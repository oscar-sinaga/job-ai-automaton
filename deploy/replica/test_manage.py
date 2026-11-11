"""Security and recovery tests for the standalone operator (no production access)."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('replica_manage', Path(__file__).with_name('manage.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class ReplicaTests(unittest.TestCase):
    def test_direct_http_origin_is_canonical_loopback_only(self):
        self.assertEqual(m.origin_parts('http://127.0.0.1:5173','direct')[1],5173)
        for value in ('http://0.0.0.0:5173','http://150.109.17.147:5173',
                      'https://127.0.0.1:5173','http://localhost:5173'):
            with self.subTest(origin=value), self.assertRaises(ValueError):
                m.origin_parts(value,'direct')
    def test_database_network_requires_owner_isolation_and_pinned_identity(self):
        network={'Id':'pinned-id','Internal':True,'Driver':'bridge','Scope':'local',
                 'Labels':{'com.docker.compose.project':'db-owner','com.docker.compose.network':'database'}}
        from types import SimpleNamespace
        with patch.object(m,'run',return_value=SimpleNamespace(stdout=json.dumps([network]).encode())):
            self.assertEqual(m.trusted_database_network('owner_database','db-owner','pinned-id')['id'],'pinned-id')
            for owner,pin in (('another-owner','pinned-id'),('db-owner','changed-id')):
                with self.assertRaises(ValueError):
                    m.trusted_database_network('owner_database',owner,pin)
            network['Internal']=False
        with patch.object(m,'run',return_value=SimpleNamespace(stdout=json.dumps([network]).encode())):
            with self.assertRaises(ValueError):
                m.trusted_database_network('owner_database','db-owner','pinned-id')
    def test_shell_compose_settings_cannot_override_selected_replica(self):
        with patch.dict(m.os.environ, {'COMPOSE_PROFILES':'database','REPLICA_BIND':'0.0.0.0:5432:5432'}), patch.object(m.subprocess,'run') as call:
            call.return_value.returncode=0
            m.run(['docker','compose','config','--quiet'])
            environment=call.call_args.kwargs['env']
            self.assertNotIn('COMPOSE_PROFILES',environment)
            self.assertNotIn('REPLICA_BIND',environment)
    def test_origins_reject_non_https_paths_and_injection(self):
        for origin in ('http://example.com', 'https://u:p@example.com', 'https://host/a',
                       'https://host?q=x', 'https://example.com:8443', 'https://host;evil'):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                m.origin_parts(origin)
        self.assertEqual(m.origin_parts('https://localhost:8443')[1], 8443)
        self.assertEqual(m.origin_parts('https://example.com')[1], 443)

    def test_sql_identifiers(self):
        self.assertEqual(m.identifier('oscar_jobs'), 'oscar_jobs')
        for value in ('db;DROP', 'db-name', '', 'a"b'):
            with self.assertRaises(ValueError):
                m.identifier(value)

    def test_literal_secret_characters(self):
        self.assertEqual(m.env_text({'PASSWORD': '$value#with spaces="x"'}), 'PASSWORD=$value#with spaces="x"\n')
        for value in ('x\nMALICIOUS=1', 'x\r', '\0'):
            with self.assertRaises(ValueError):
                m.env_text({'PASSWORD': value})

    def test_private_files_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'credential'
            m.write_private(p, 'first')
            with self.assertRaises(FileExistsError):
                m.write_private(p, 'second')
            self.assertEqual(p.read_text(), 'first')

    def test_manifest_detects_tampering_and_path_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            (p / 'database.dump').write_bytes(b'fixture dump')
            manifest = {'version': 1, 'files': {'database.dump': m.digest(p/'database.dump')}}
            (p/'manifest.json').write_text(json.dumps(manifest))
            m.verify_backup(p)
            (p/'database.dump').write_bytes(b'tampered')
            with self.assertRaises(ValueError):
                m.verify_backup(p)
            manifest['files'] = {'../outside': 'bad', 'database.dump': 'bad'}
            (p/'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                m.verify_backup(p)

    def test_restore_rejects_tar_traversal_and_links(self):
        for name, link in (('../escape', False), ('/absolute', False), ('symlink', True)):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                p = Path(directory)
                (p/'database.dump').write_bytes(b'fixture')
                with tarfile.open(p/'documents.tar.gz','w:gz') as archive:
                    member=tarfile.TarInfo(name)
                    if link:
                        member.type=tarfile.SYMTYPE
                        member.linkname='/etc/passwd'
                    else:
                        member.size=1
                    archive.addfile(member, None if link else io.BytesIO(b'x'))
                (p/'manifest.json').write_text(json.dumps({'version':1,'files':{n:m.digest(p/n) for n in ('database.dump','documents.tar.gz')}}))
                with self.assertRaises(ValueError):
                    m.verify_backup(p)


if __name__ == '__main__':
    unittest.main()
