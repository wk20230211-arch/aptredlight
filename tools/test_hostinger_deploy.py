"""Local transaction regression tests. Never connect to SSH, HTTP, or production."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
from urllib.parse import urlsplit
from urllib.request import Request
import uuid

MODULE_PATH = Path(__file__).with_name('hostinger_deploy.py')
SPEC = importlib.util.spec_from_file_location('hostinger_deploy_under_test', MODULE_PATH)
DEPLOY = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = DEPLOY
SPEC.loader.exec_module(DEPLOY)

PROJECT = 'appgprj_6addb8c872b081918d711d7bc0c5cbf4'
ORIGIN = 'https://www.aptredlight.com'
SOURCE = 'https://aptredlight-wellness.wk20230211.chatgpt.site'
INDEX = 'hostinger-release-manifest.json'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def make_release(root, version=45, extra=None):
    root.mkdir(parents=True)
    files = {
        'index.html': b'<!doctype html><title>APTREDLIGHT fixture</title><script src="/app.js" defer></script>\n',
        'app.js': b'globalThis.syntheticRelease = 45;\n',
        'guides/buyer.html': b'<!doctype html><title>Synthetic buyer guide</title>\n',
    }
    files.update(extra or {})
    htaccess = b'Options -Indexes\nDirectoryIndex index.html\n'
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (root / '.htaccess').write_bytes(htaccess)
    raw = {
        'schema': 1, 'project_id': PROJECT, 'canonical_origin': ORIGIN,
        'files': [
            {'path': name, 'size': len(data), 'sha256': digest(data),
             **({'content': data.decode()} if name.endswith('.html') else {})}
            for name, data in sorted(files.items())
        ],
        'apache_htaccess': htaccess.decode(),
    }
    raw_bytes = json_bytes(raw)
    (root / 'release-manifest.json').write_bytes(raw_bytes)
    pointer = {
        'schema': 1, 'project_id': PROJECT, 'source_origin': SOURCE,
        'source_commit': ('a' if version == 45 else 'b') * 40,
        'sites_version': version, 'manifest_sha256': digest(raw_bytes),
        'canonical_origin': ORIGIN,
    }
    (root / 'source-release.json').write_bytes(json_bytes(pointer))
    manifest = rebuild_index(root, pointer)
    return pointer, manifest


def rebuild_index(root, pointer):
    files = []
    for path in sorted(root.rglob('*')):
        if path.is_file() and path.name != INDEX:
            data = path.read_bytes()
            files.append({'path': path.relative_to(root).as_posix(),
                          'size': len(data), 'sha256': digest(data)})
    manifest = {'schema': 1, 'project_id': PROJECT,
                'canonical_origin': ORIGIN, 'release': copy.deepcopy(pointer),
                'files': files}
    (root / INDEX).write_bytes(json_bytes(manifest))
    return manifest


def archive_release(root, archive, malicious=None):
    with tarfile.open(archive, 'w:gz') as handle:
        for path in sorted(root.rglob('*')):
            if path.is_file():
                handle.add(path, arcname=path.relative_to(root).as_posix(), recursive=False)
        if malicious is not None:
            entry, data = malicious
            handle.addfile(entry, io.BytesIO(data) if entry.isfile() else None)
    return archive


class HostingerDeployTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='apt-deploy-tests-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.release = self.root / 'release'
        self.pointer, self.manifest = make_release(self.release)
        self.web = self.root / 'domains' / 'aptredlight.com' / 'public_html'
        old = self.root / 'old-release'
        self.old_pointer, _ = make_release(old, 44, {'old-only.txt': b'old unrelated release file'})
        shutil.copytree(old, self.web)
        (self.web / 'index.html').write_bytes(b'old live HTML\n')
        (self.web / 'app.js').write_bytes(b'old live JavaScript\n')
        (self.web / '.htaccess').write_bytes(b'old live htaccess\n')
        (self.web / 'uploads').mkdir()
        (self.web / 'uploads' / 'keep.bin').write_bytes(b'Unrelated owner upload retained.\n')
        self.baseline = self.web_snapshot()
        self.archive = archive_release(self.release, self.root / 'release.tar.gz')
        self.transaction = uuid.uuid4().hex
        self.addCleanup(mock.patch.stopall)
        mock.patch('socket.create_connection', side_effect=AssertionError('Network forbidden in local tests')).start()

    def web_snapshot(self):
        return {p.relative_to(self.web).as_posix(): p.read_bytes()
                for p in self.web.rglob('*') if p.is_file() and not p.is_symlink()}

    def prepare(self, transaction=None, manifest=None, archive=None, **kwargs):
        transaction = self.transaction if transaction is None else transaction
        _, _, directory = DEPLOY.target_paths(self.web, transaction, strict_target=False)
        private_archive = directory / 'archive.tar'
        shutil.copyfile(archive or self.archive, private_archive)
        return DEPLOY.remote_prepare(self.web, transaction,
                                     manifest or self.manifest, private_archive,
                                     strict_target=False, **kwargs)

    def apply(self, transaction=None):
        return DEPLOY.remote_apply(self.web, transaction or self.transaction, strict_target=False)

    def rollback(self, transaction=None):
        return DEPLOY.remote_rollback(self.web, transaction or self.transaction, strict_target=False)

    def finalize(self, transaction=None):
        return DEPLOY.remote_finalize(self.web, transaction or self.transaction, strict_target=False)

    def assert_no_live_changes(self):
        self.assertEqual(self.web_snapshot(), self.baseline)

    def test_transaction_metadata_cannot_escape_backup_directory(self):
        self.prepare()
        _, base, directory = DEPLOY.target_paths(self.web, self.transaction, strict_target=False)
        path = directory / 'transaction.json'
        original = json.loads(path.read_text())
        corrupted = copy.deepcopy(original)
        corrupted['backup_path'] = str(self.root / 'different-private-directory')
        path.write_bytes(json_bytes(corrupted))
        with self.assertRaises(DEPLOY.DeployError):
            self.rollback()
        self.assert_no_live_changes()
        self.assertTrue((base / 'lock').is_dir())
        for field, value in [('existing', ['../outside']), ('missing', ['api/private.json']),
                             ('touched', ['unlisted.txt']), ('backup_hashes', {'other.txt': 'a' * 64})]:
            with self.subTest(field=field):
                corrupted = copy.deepcopy(original)
                corrupted[field] = value
                path.write_bytes(json_bytes(corrupted))
                with self.assertRaises(DEPLOY.DeployError):
                    self.rollback()
                self.assert_no_live_changes()
        path.write_bytes(json_bytes(original))
        self.assertEqual(self.rollback()['status'], 'rolled_back')

    def test_validate_release_hashes_and_complete_pointer(self):
        result = DEPLOY.validate_release(self.release, self.pointer)
        self.assertEqual(result, self.manifest)
        self.assertEqual(set(result), {'schema', 'project_id', 'canonical_origin', 'release', 'files'})
        self.assertNotIn(INDEX, [entry['path'] for entry in result['files']])
        self.assertTrue({'.htaccess', 'source-release.json', 'release-manifest.json', 'app.js'}
                        .issubset({entry['path'] for entry in result['files']}))

    def test_validate_actual_file_tampering(self):
        (self.release / 'app.js').write_bytes(b'tampered after manifest\n')
        with self.assertRaises(Exception):
            DEPLOY.validate_release(self.release, self.pointer)

    def test_full_source_pointer_is_typed_and_pinned(self):
        for field, value in [('project_id', 'foreign-project'),
                             ('canonical_origin', 'https://foreign.example.invalid'),
                             ('source_origin', 'https://foreign.example.invalid'),
                             ('source_commit', 'not-a-commit'),
                             ('sites_version', True), ('sites_version', -1)]:
            with self.subTest(field=field, value=value):
                pointer = copy.deepcopy(self.pointer)
                pointer[field] = value
                (self.release / 'source-release.json').write_bytes(json_bytes(pointer))
                rebuild_index(self.release, pointer)
                with self.assertRaises(Exception):
                    DEPLOY.validate_release(self.release, pointer)

    def test_validate_raw_manifest_and_htaccess_chain(self):
        for name in ['release-manifest.json', '.htaccess']:
            with self.subTest(name=name):
                original = (self.release / name).read_bytes()
                (self.release / name).write_bytes(original + b'\n')
                rebuild_index(self.release, self.pointer)
                with self.assertRaises(Exception):
                    DEPLOY.validate_release(self.release, self.pointer)
                (self.release / name).write_bytes(original)
                rebuild_index(self.release, self.pointer)

    def test_validate_missing_js_and_undeclared_file(self):
        (self.release / 'app.js').unlink()
        rebuild_index(self.release, self.pointer)
        with self.assertRaises(Exception):
            DEPLOY.validate_release(self.release, self.pointer)
        (self.release / 'app.js').write_bytes(b'globalThis.syntheticRelease = 45;\n')
        (self.release / 'unexpected.txt').write_bytes(b'not in raw source manifest')
        rebuild_index(self.release, self.pointer)
        with self.assertRaises(Exception):
            DEPLOY.validate_release(self.release, self.pointer)

    def test_validate_manifest_fields_duplicates_and_bad_paths(self):
        mutations = [
            lambda x: x.update(extra=True),
            lambda x: x.update(project_id='wrong-project'),
            lambda x: x.update(canonical_origin='https://foreign.example.invalid'),
            lambda x: x['files'].append(copy.deepcopy(x['files'][0])),
            lambda x: x['files'][0].update(path='../outside.txt'),
            lambda x: x['files'][0].update(path='/absolute.txt'),
            lambda x: x['files'][0].update(path='dir\\file.txt'),
            lambda x: x['files'][0].update(size=-1),
            lambda x: x['files'][0].update(sha256='not-a-hash'),
            lambda x: x['files'][0].update(extra='unsupported'),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate.__code__.co_firstlineno):
                value = copy.deepcopy(self.manifest)
                mutate(value)
                (self.release / INDEX).write_bytes(json_bytes(value))
                with self.assertRaises(Exception):
                    DEPLOY.validate_release(self.release, self.pointer)

    def test_private_paths_and_symlinks_rejected(self):
        for relative in ['.git/config', '.openai/private.json', '.env', 'server/index.js']:
            with self.subTest(relative=relative):
                folder = self.root / ('private-' + uuid.uuid4().hex)
                pointer, _ = make_release(folder, extra={relative: b'never deploy private bytes'})
                with self.assertRaises(Exception):
                    DEPLOY.validate_release(folder, pointer)
        outside = self.root / 'outside-secret'
        outside.write_bytes(b'not public')
        (self.release / 'linked.txt').symlink_to(outside)
        rebuild_index(self.release, self.pointer)
        with self.assertRaises(Exception):
            DEPLOY.validate_release(self.release, self.pointer)

    def test_strict_target_and_transaction_id(self):
        with self.assertRaises(Exception):
            DEPLOY.remote_prepare(self.web, self.transaction, self.manifest, self.archive)
        for value in ['../../escape', '/absolute', '', 'not-a-uuid', 'a' * 33]:
            with self.subTest(transaction=value), self.assertRaises(Exception):
                self.prepare(transaction=value)
        self.assert_no_live_changes()

    def test_prepare_external_backup_and_cooperative_lock(self):
        receipt = self.prepare()
        self.assertIn('backup_id', receipt)
        backup = Path(receipt['backup_path']).resolve()
        self.assertFalse(backup.is_relative_to(self.web.resolve()))
        self.assertTrue(backup.is_relative_to((self.web.parent / '.aptredlight-deploy').resolve()))
        self.assertTrue(backup.exists())
        self.assert_no_live_changes()
        with self.assertRaises(Exception):
            self.prepare(transaction=uuid.uuid4().hex)
        self.assert_no_live_changes()
        self.assertEqual(self.rollback()['status'], 'rolled_back')

    def test_apply_finalize_preserves_unrelated_uploads(self):
        self.prepare()
        receipt = self.apply()
        self.assertEqual(receipt['status'], 'applied')
        for item in self.manifest['files']:
            data = (self.web / item['path']).read_bytes()
            self.assertEqual(len(data), item['size'])
            self.assertEqual(digest(data), item['sha256'])
        self.assertEqual((self.web / 'uploads/keep.bin').read_bytes(), self.baseline['uploads/keep.bin'])
        self.assertEqual((self.web / 'old-only.txt').read_bytes(), self.baseline['old-only.txt'])
        self.assertEqual(self.finalize()['status'], 'finalized')
        second = uuid.uuid4().hex
        self.prepare(transaction=second)
        self.rollback(transaction=second)

    def test_http_failure_rollback_restores_old_and_removes_new_files(self):
        new_release = self.root / 'release-with-new'
        pointer, manifest = make_release(new_release, extra={'new-guide/new-file.html': b'<!doctype html>new guide'})
        archive = archive_release(new_release, self.root / 'new.tar.gz')
        self.prepare(manifest=manifest, archive=archive)
        self.apply()
        self.assertTrue((self.web / 'new-guide/new-file.html').exists())
        self.assertEqual(self.rollback()['status'], 'rolled_back')
        self.assert_no_live_changes()

    def test_apply_failure_rolls_back_partial_overwrites_and_new_files(self):
        release = self.root / 'failure-release'
        _, manifest = make_release(release, extra={'aaa-new.txt': b'new before failure', 'zzz-new.txt': b'new after failure'})
        archive = archive_release(release, self.root / 'failure.tar.gz')
        self.prepare(manifest=manifest, archive=archive)
        original_replace = DEPLOY.os.replace
        writes = []
        failed = False

        def fail_once(source, destination, *args, **kwargs):
            nonlocal failed
            target = Path(destination)
            if target.is_relative_to(self.web):
                writes.append(target)
                if len(writes) == 3 and not failed:
                    failed = True
                    raise OSError('synthetic third live replacement failed')
            return original_replace(source, destination, *args, **kwargs)

        with mock.patch.object(DEPLOY.os, 'replace', side_effect=fail_once):
            with self.assertRaises(Exception):
                self.apply()
        self.assertTrue(failed, 'fixture injected an actual partially applied file transaction')
        self.assert_no_live_changes()

    def test_newer_source_pointer_drift_blocks_apply(self):
        self.prepare()
        changed = copy.deepcopy(self.old_pointer)
        changed['sites_version'] = 46
        (self.web / 'source-release.json').write_bytes(json_bytes(changed))
        expected = self.web_snapshot()
        with self.assertRaises(Exception):
            self.apply()
        self.assertEqual(self.web_snapshot(), expected, 'drifted owner source is not overwritten or stale-rolled-back')

    def test_source_pointer_drift_blocks_stale_rollback(self):
        self.prepare()
        self.apply()
        changed = copy.deepcopy(self.pointer)
        changed['sites_version'] = 46
        (self.web / 'source-release.json').write_bytes(json_bytes(changed))
        expected = self.web_snapshot()
        with self.assertRaises(Exception):
            self.rollback()
        self.assertEqual(self.web_snapshot(), expected)

    def test_mismatched_parent_project_and_downgrade(self):
        for field, value in [('project_id', 'some-other-site'),
                             ('canonical_origin', 'https://foreign.example.invalid')]:
            with self.subTest(parent_field=field):
                wrong = copy.deepcopy(self.old_pointer)
                wrong[field] = value
                (self.web / 'source-release.json').write_bytes(json_bytes(wrong))
                with self.assertRaises(Exception):
                    self.prepare()
        newer = copy.deepcopy(self.old_pointer)
        newer['sites_version'] = 46
        (self.web / 'source-release.json').write_bytes(json_bytes(newer))
        with self.assertRaises(Exception):
            self.prepare()
        receipt = self.prepare(allow_downgrade=True)
        self.assertTrue(receipt['backup_id'])
        self.rollback()

    def test_tar_traversal_links_undeclared_and_duplicate_members(self):
        cases = []
        for name in ['../escape.txt', '/tmp/apt-test-absolute.txt', 'unlisted.txt', 'index.html']:
            member = tarfile.TarInfo(name)
            member.size = 4
            cases.append((member, b'evil'))
        for kind in [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE]:
            member = tarfile.TarInfo('archive-link')
            member.type = kind
            member.linkname = '../outside'
            cases.append((member, b''))
        for member, data in cases:
            with self.subTest(name=member.name, type=member.type):
                archive = archive_release(self.release, self.root / ('malicious-' + uuid.uuid4().hex + '.tar.gz'), (member, data))
                with self.assertRaises(Exception):
                    self.prepare(transaction=uuid.uuid4().hex, archive=archive)
                self.assert_no_live_changes()
                recovery = uuid.uuid4().hex
                self.prepare(transaction=recovery)
                self.rollback(transaction=recovery)
        self.assertFalse((self.web.parent / 'escape.txt').exists())

    def test_tar_payload_hash_and_destination_symlinks(self):
        bad_release = self.root / 'tampered-archive'
        shutil.copytree(self.release, bad_release)
        (bad_release / 'app.js').write_bytes(b'bad tar bytes not matching supplied index')
        archive = archive_release(bad_release, self.root / 'bad-hash.tar.gz')
        with self.assertRaises(Exception):
            self.prepare(archive=archive)
        release = self.root / 'symlink-destination-release'
        _, manifest = make_release(release, extra={'assets/new.txt': b'must stay under webroot'})
        archive = archive_release(release, self.root / 'symlink-destination.tar.gz')
        outside = self.root / 'outside-directory'
        outside.mkdir()
        (self.web / 'assets').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(Exception):
            self.prepare(transaction=uuid.uuid4().hex, manifest=manifest, archive=archive)
        self.assertFalse((outside / 'new.txt').exists())

    def test_http_verifier_confirms_real_hashes_via_fake_opener(self):
        seen = []
        release = self.release

        class Response(io.BytesIO):
            status = 200

            def __init__(self, data, url):
                super().__init__(data)
                self.url = url

            def geturl(self):
                return self.url

        class Opener:
            def open(self, request, timeout):
                seen.append(request)
                self_test.assertEqual(timeout, 30)
                relative = urlsplit(request.full_url).path.lstrip('/')
                return Response((release / relative).read_bytes(), request.full_url)

        self_test = self
        result = DEPLOY.verify_http(self.release, self.manifest, self.transaction, opener=Opener())
        self.assertEqual(set(result), {'source-release.json', 'index.html', 'app.js'})
        self.assertEqual(len(seen), 4)
        self.assertEqual(seen[0].full_url, DEPLOY.ORIGIN + '/source-release.json')
        for index, request in enumerate(seen):
            self.assertEqual(urlsplit(request.full_url).netloc, 'www.aptredlight.com')
            if index:
                self.assertIn(self.transaction, urlsplit(request.full_url).query)
            else:
                self.assertEqual(urlsplit(request.full_url).query, '')
            self.assertEqual(request.get_header('Accept-encoding'), 'identity')
            self.assertEqual(request.get_header('Cache-control'), 'no-cache')

    def test_http_verifier_rejects_bad_js_old_source_and_external_redirect(self):
        release = self.release
        old_source = json_bytes(self.old_pointer)

        class Response(io.BytesIO):
            status = 200

            def __init__(self, data, url):
                super().__init__(data)
                self.url = url

            def geturl(self):
                return self.url

        for scenario in ['bad-js', 'old-source', 'external-response']:
            with self.subTest(scenario=scenario):
                class Opener:
                    def open(self, request, timeout):
                        relative = urlsplit(request.full_url).path.lstrip('/')
                        data = (release / relative).read_bytes()
                        if scenario == 'bad-js' and relative == 'app.js':
                            data = b'wrong JavaScript cached by host'
                        if scenario == 'old-source' and relative == 'source-release.json':
                            data = old_source
                        final = 'https://foreign.example.invalid/source-release.json' if scenario == 'external-response' else request.full_url
                        return Response(data, final)
                with self.assertRaises(Exception):
                    DEPLOY.verify_http(self.release, self.manifest, self.transaction, opener=Opener())
        redirects = DEPLOY.CanonicalRedirects()
        for destination in ['http://www.aptredlight.com/index.html', 'https://foreign.example.invalid/index.html']:
            with self.subTest(redirect=destination), self.assertRaises(Exception):
                redirects.redirect_request(Request(ORIGIN + '/'), None, 302, 'Found', {}, destination)

    def test_ssh_args_pin_known_hosts_and_disable_passwords_and_key_files(self):
        trusted = self.root / 'known_hosts'
        trusted.write_text('[127.0.0.1]:65002 ssh-ed25519 SYNTHETIC-FIXTURE-NOT-A-REAL-KEY\n')
        args = SimpleNamespace(user='u469397229', host='127.0.0.1', port=65002, known_hosts=str(trusted))
        result = DEPLOY.ssh_args(args, 'python3 -')
        self.assertEqual(result[:3], ['ssh', '-F', '/dev/null'])
        self.assertEqual(result[-3:], ['--', 'u469397229@127.0.0.1', 'python3 -'])
        options = {result[index + 1] for index, value in enumerate(result) if value == '-o'}
        self.assertTrue({'BatchMode=yes', 'StrictHostKeyChecking=yes',
                         'UserKnownHostsFile=' + str(trusted.resolve()),
                         'IdentityFile=none', 'PreferredAuthentications=publickey',
                         'PasswordAuthentication=no', 'KbdInteractiveAuthentication=no',
                         'ForwardAgent=no'}.issubset(options))
        self.assertNotIn('-i', result)
        for field, value in [('user', 'wrong-owner'), ('host', '-oProxyCommand=evil'),
                             ('host', 'host with whitespace'), ('port', 0), ('port', True),
                             ('known_hosts', str(self.root / 'missing-known-hosts'))]:
            with self.subTest(field=field, value=value), self.assertRaises(Exception):
                DEPLOY.ssh_args(SimpleNamespace(**{**vars(args), field: value}), 'python3 -')
        link = self.root / 'linked-known-hosts'
        link.symlink_to(trusted)
        with self.assertRaises(Exception):
            DEPLOY.ssh_args(SimpleNamespace(**{**vars(args), 'known_hosts': str(link)}), 'python3 -')


if __name__ == '__main__':
    unittest.main(verbosity=2)
