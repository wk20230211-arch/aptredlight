"""Isolated authorized_keys tests using synthetic public bytes, never real keys."""
import base64
import importlib.util
import os
from pathlib import Path
import stat
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location('install_hostinger_public_key_under_test', Path(__file__).with_name('install_hostinger_public_key.py'))
INSTALLER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = INSTALLER
SPEC.loader.exec_module(INSTALLER)
OPTIONS = 'no-agent-forwarding,no-port-forwarding,no-X11-forwarding,no-pty'
WIRE = struct.pack('>I', 11) + b'ssh-ed25519' + struct.pack('>I', 32) + b'\x01' * 32
BLOB = base64.b64encode(WIRE).decode()
PUBLIC = OPTIONS + ' ssh-ed25519 ' + BLOB + ' synthetic-fixture'
LOCK = '.aptredlight-authorized-keys.lock'


class PublicKeyInstallTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='apt-public-key-tests-')
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.home = self.base / 'home'
        self.home.mkdir(mode=0o700)
        self.ssh = self.home / '.ssh'
        self.ssh.mkdir(mode=0o700)
        self.authorized = self.ssh / 'authorized_keys'
        self.initial = b'# Existing synthetic owner-managed keys\r\nssh-rsa AAAASYNTHETIC-OTHER-KEY fixture-existing\r\n'
        self.authorized.write_bytes(self.initial)
        self.authorized.chmod(0o600)
        account = SimpleNamespace(pw_name='fixture-user', pw_uid=os.getuid(), pw_gid=os.getgid(), pw_dir=str(self.home))
        self.identity = mock.patch.object(INSTALLER.pwd, 'getpwuid', return_value=account)
        self.identity.start()
        self.addCleanup(self.identity.stop)

    def install(self, value=PUBLIC, **kwargs):
        return INSTALLER.install(value, home=self.home, expected_uid=os.getuid(),
                                 expected_user='fixture-user', verify_identity=False, **kwargs)

    def test_install_preserves_original_bytes_and_retries_idempotently(self):
        result = self.install()
        self.assertEqual(result, {'status': 'authorized', 'changed': True})
        first = self.authorized.read_bytes()
        self.assertTrue(first.startswith(self.initial))
        self.assertIn(PUBLIC.encode(), first)
        self.assertEqual(stat.S_IMODE(self.authorized.stat().st_mode), 0o600)
        result = self.install()
        self.assertEqual(result, {'status': 'already_authorized', 'changed': False})
        self.assertEqual(self.authorized.read_bytes(), first)

    def test_missing_ssh_and_authorized_keys_created_with_safe_permissions(self):
        self.authorized.unlink()
        self.ssh.rmdir()
        self.assertTrue(self.install()['changed'])
        self.assertEqual(stat.S_IMODE(self.ssh.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(self.authorized.stat().st_mode), 0o600)

    def test_existing_algorithm_blob_dedup_ignores_comment_and_options(self):
        existing = self.initial + ('ssh-ed25519 ' + BLOB + ' pre-existing-comment\n').encode()
        self.authorized.write_bytes(existing)
        self.assertEqual(self.install(), {'status': 'already_authorized', 'changed': False})
        self.assertEqual(self.authorized.read_bytes(), existing)

    def test_comment_does_not_count_as_authorized_key_and_missing_newline_preserved(self):
        original = ('# ssh-ed25519 ' + BLOB + ' only a comment').encode()
        self.authorized.write_bytes(original)
        self.assertTrue(self.install()['changed'])
        result = self.authorized.read_bytes()
        self.assertTrue(result.startswith(original + b'\n'))
        self.assertIn(PUBLIC.encode(), result)

    def test_rejects_missing_restrictions_multiple_keys_private_text_and_comments(self):
        invalid = [
            'ssh-ed25519 ' + BLOB + ' unrestricted',
            'no-agent-forwarding ssh-ed25519 ' + BLOB,
            OPTIONS + ',command="evil" ssh-ed25519 ' + BLOB,
            PUBLIC + '\n' + PUBLIC,
            '-----BEGIN OPENSSH PRIVATE KEY-----\nSYNTHETIC-NOT-A-PRIVATE-KEY',
            OPTIONS + ' ssh-rsa ' + BLOB,
            OPTIONS + ' ssh-ed25519 not-valid-base64',
            OPTIONS + ' ssh-ed25519 ' + BLOB + ' ' + 'x' * 101,
            OPTIONS + ' ssh-ed25519 ' + BLOB + ' non-ascii-中文',
            OPTIONS + ' ssh-ed25519 ' + BLOB + ' control\x00comment',
        ]
        for value in invalid:
            with self.subTest(value=value[:70]), self.assertRaises(Exception):
                self.install(value)
            self.assertEqual(self.authorized.read_bytes(), self.initial)

    def test_strict_ed25519_wire_lengths_and_algorithm(self):
        invalid = [WIRE[:-1], WIRE + b'\x02',
                   struct.pack('>I', 11) + b'ssh-ed25518' + struct.pack('>I', 32) + b'\x01' * 32,
                   struct.pack('>I', 11) + b'ssh-ed25519' + struct.pack('>I', 31) + b'\x01' * 32]
        for wire in invalid:
            with self.subTest(length=len(wire)), self.assertRaises(Exception):
                self.install(OPTIONS + ' ssh-ed25519 ' + base64.b64encode(wire).decode())
            self.assertEqual(self.authorized.read_bytes(), self.initial)

    def test_wrong_uid_and_account_name_rejected(self):
        with self.assertRaises(Exception):
            INSTALLER.install(PUBLIC, home=self.home, expected_uid=os.getuid() + 1,
                              expected_user='fixture-user', verify_identity=False)
        with mock.patch.object(INSTALLER.pwd, 'getpwuid', return_value=SimpleNamespace(pw_name='wrong-account', pw_uid=os.getuid(), pw_dir=str(self.home))):
            with self.assertRaises(Exception):
                self.install()
        self.assertEqual(self.authorized.read_bytes(), self.initial)

    def test_unsafe_permissions_rejected(self):
        for target in [self.home, self.ssh, self.authorized]:
            with self.subTest(target=target.name):
                mode = stat.S_IMODE(target.stat().st_mode)
                target.chmod(0o777 if target.is_dir() else 0o666)
                try:
                    with self.assertRaises(Exception):
                        self.install()
                    self.assertEqual(self.authorized.read_bytes(), self.initial)
                finally:
                    target.chmod(mode)

    def test_home_ssh_and_authorized_keys_symlinks_rejected(self):
        alias = self.base / 'home-link'
        alias.symlink_to(self.home, target_is_directory=True)
        with self.assertRaises(Exception):
            INSTALLER.install(PUBLIC, home=alias, expected_uid=os.getuid(),
                              expected_user='fixture-user', verify_identity=False)
        saved = self.home / 'ssh-real'
        self.ssh.rename(saved)
        self.ssh.symlink_to(saved, target_is_directory=True)
        with self.assertRaises(Exception):
            self.install()
        self.ssh.unlink()
        saved.rename(self.ssh)
        other = self.base / 'other-authorized'
        other.write_bytes(self.initial)
        other.chmod(0o600)
        self.authorized.unlink()
        self.authorized.symlink_to(other)
        with self.assertRaises(Exception):
            self.install()
        self.assertEqual(other.read_bytes(), self.initial)

    def test_lock_symlink_rejected_and_real_lock_uses_flock(self):
        target = self.base / 'lock-target'
        target.write_text('do not replace')
        target.chmod(0o600)
        lock = self.ssh / LOCK
        lock.symlink_to(target)
        with self.assertRaises(Exception):
            self.install()
        self.assertEqual(target.read_text(), 'do not replace')
        lock.unlink()
        calls = []
        original = INSTALLER.fcntl.flock

        def flock(descriptor, operation):
            calls.append(operation)
            return original(descriptor, operation)

        with mock.patch.object(INSTALLER.fcntl, 'flock', side_effect=flock):
            self.assertTrue(self.install()['changed'])
        self.assertTrue(any(operation & INSTALLER.fcntl.LOCK_EX for operation in calls))
        self.assertEqual(stat.S_IMODE(lock.stat().st_mode), 0o600)
        descriptor = os.open(lock, os.O_RDWR | os.O_NOFOLLOW)
        try:
            original(descriptor, INSTALLER.fcntl.LOCK_EX | INSTALLER.fcntl.LOCK_NB)
            original(descriptor, INSTALLER.fcntl.LOCK_UN)
        finally:
            os.close(descriptor)

    def test_busy_lock_stops_without_waiting_or_modifying_keys(self):
        lock = self.ssh / LOCK
        descriptor = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            INSTALLER.fcntl.flock(descriptor, INSTALLER.fcntl.LOCK_EX | INSTALLER.fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                self.install()
            self.assertEqual(self.authorized.read_bytes(), self.initial)
            self.assertEqual(list(self.ssh.glob('.aptredlight-key-*')), [])
        finally:
            INSTALLER.fcntl.flock(descriptor, INSTALLER.fcntl.LOCK_UN)
            os.close(descriptor)

    def test_existing_unsafe_lock_permissions_rejected(self):
        lock = self.ssh / LOCK
        lock.write_text('')
        lock.chmod(0o666)
        with self.assertRaises(Exception):
            self.install()
        self.assertEqual(self.authorized.read_bytes(), self.initial)

    def test_concurrent_authorized_keys_change_preserved_and_install_rejected(self):
        concurrent = self.initial + b'# concurrent owner addition must be preserved\n'

        def change(_path):
            self.authorized.write_bytes(concurrent)

        with mock.patch.object(INSTALLER, '_before_replace', side_effect=change):
            with self.assertRaises(Exception):
                self.install()
        self.assertEqual(self.authorized.read_bytes(), concurrent)
        self.assertEqual({p.name for p in self.ssh.iterdir()}, {'authorized_keys', LOCK})

    def test_atomic_failure_preserves_original_and_cleans_private_temp(self):
        observed = []

        def failure(_path):
            for path in self.ssh.iterdir():
                if path.name not in {'authorized_keys', LOCK}:
                    observed.append(stat.S_IMODE(path.stat().st_mode))
            raise OSError('synthetic before-replace failure')

        with mock.patch.object(INSTALLER, '_before_replace', side_effect=failure):
            with self.assertRaises(Exception):
                self.install()
        self.assertTrue(observed, 'hook ran after an actual temporary file was written')
        self.assertTrue(all(mode == 0o600 for mode in observed))
        self.assertEqual(self.authorized.read_bytes(), self.initial)
        self.assertEqual({p.name for p in self.ssh.iterdir()}, {'authorized_keys', LOCK})


if __name__ == '__main__':
    unittest.main(verbosity=2)
