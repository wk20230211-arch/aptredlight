"""Offline public-key identity verification tests. Never scan hosts or read private keys."""
import base64
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('hostinger_identity', Path(__file__).with_name('verify_hostinger_identity.py'))
IDENTITY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(IDENTITY)


def wire_string(value):
    return struct.pack('>I', len(value)) + value


KEY = wire_string(b'ssh-ed25519') + wire_string(bytes(range(32)))
ENCODED = base64.b64encode(KEY).decode('ascii')
PIN = 'SHA256:' + base64.b64encode(hashlib.sha256(KEY).digest()).decode('ascii').rstrip('=')


def config():
    return {'schema': 1, 'project_id': IDENTITY.PROJECT, 'domain': IDENTITY.DOMAIN,
            'canonical_origin': IDENTITY.ORIGIN, 'ssh_user': IDENTITY.USER,
            'ssh_port': 65002, 'web_root': IDENTITY.WEB_ROOT,
            'ssh_host': '45.87.81.210', 'ssh_host_key_sha256': PIN}


def record(target='[45.87.81.210]:65002', algorithm='ssh-ed25519', key=ENCODED):
    return target + ' ' + algorithm + ' ' + key + '\n'


class IdentityTests(unittest.TestCase):
    def test_correct_public_wire_and_pin(self):
        result = IDENTITY.verify(config(), '# synthetic ssh-keyscan banner\n' + record())
        self.assertEqual(result, {'status': 'identity_verified', 'verified': True,
                                 'host': '45.87.81.210', 'port': 65002,
                                 'algorithm': 'ssh-ed25519', 'fingerprint': PIN})

    def test_ordinary_port_22_and_explicit_endpoint(self):
        result = IDENTITY.verify(config(), record('ssh.example.test'), host='ssh.example.test', port=22)
        self.assertEqual(result['port'], 22)
        self.assertEqual(result['host'], 'ssh.example.test')
        self.assertEqual(IDENTITY.verify(config(), record('[2001:db8::1]:65002'), host='2001:db8::1')['algorithm'], 'ssh-ed25519')

    def test_target_mismatch_markers_aliases_hashes_and_duplicates(self):
        bad = ['', record('45.87.81.210'), record('[45.87.81.210]:22'), record('[other.example]:65002'),
               record('[45.87.81.210]:65002,other.example'), record('|1|hashed|host'),
               '@cert-authority ' + record(), record() + record(), record() + record('other.example'),
               record(algorithm='ssh-rsa'), record() + '\x00']
        for value in bad:
            with self.subTest(value=value[:40]), self.assertRaises(IDENTITY.IdentityError):
                IDENTITY.verify(config(), value)

    def test_no_typo_or_case_fallback_for_fingerprint(self):
        for pin in [PIN[:-1] + ('A' if PIN[-1] != 'A' else 'B'), PIN.lower(), PIN + '=', 'SHA256:' + 'A' * 43,
                    'SHA256:4mfb2c67Lhi/idZu+pyYocKONELisV4IInwlFdR8t98']:
            with self.subTest(pin=pin), self.assertRaises(IDENTITY.IdentityError):
                IDENTITY.verify({**config(), 'ssh_host_key_sha256': pin}, record())

    def test_bad_base64_and_wire(self):
        malformed = [b'', b'\x00', wire_string(b'ssh-rsa') + wire_string(bytes(range(32))),
                     wire_string(b'ssh-ed25519') + wire_string(bytes(range(31))),
                     wire_string(b'ssh-ed25519') + wire_string(bytes(range(33))), KEY + b'junk',
                     struct.pack('>I', 100000) + b'x']
        for blob in malformed:
            encoded = base64.b64encode(blob).decode('ascii')
            pin = 'SHA256:' + base64.b64encode(hashlib.sha256(blob).digest()).decode('ascii').rstrip('=')
            with self.subTest(blob=blob[:15]), self.assertRaises(IDENTITY.IdentityError):
                IDENTITY.verify({**config(), 'ssh_host_key_sha256': pin}, record(key=encoded))
        for encoded in [ENCODED + '=', '!!!!', ENCODED[:-1], ENCODED[:10] + '-' + ENCODED[11:]]:
            with self.subTest(encoded=encoded[:20]), self.assertRaises(IDENTITY.IdentityError):
                IDENTITY.verify(config(), record(key=encoded))

    def test_scope_user_path_host_and_port_injection(self):
        mutations = [('schema', True), ('project_id', 'other'), ('domain', 'other.example'),
                     ('canonical_origin', 'https://www.aptredlight.com.evil.test'), ('ssh_user', 'root'),
                     ('web_root', '/home/u469397229/domains/aptredlight.com/../other/public_html'),
                     ('web_root', IDENTITY.WEB_ROOT + '; echo injected'), ('ssh_host_key_algorithm', 'ssh-rsa')]
        for key, value in mutations:
            with self.subTest(key=key), self.assertRaises(IDENTITY.IdentityError):
                IDENTITY.verify({**config(), key: value}, record())
        for host in ['-oProxyCommand=evil', 'good\nInjected=x', 'user@host', 'host;echo', '../escape', '[::1]', 'a..b', '999.999.1.1', 'host%zone']:
            with self.subTest(host=host), self.assertRaises(IDENTITY.IdentityError):
                IDENTITY.verify(config(), record(), host=host)
        for port in [0, -1, 65536, True, '65002']:
            with self.subTest(port=port), self.assertRaises(IDENTITY.IdentityError):
                IDENTITY.verify(config(), record(), port=port)

    def test_cli_success_failure_receipts_and_no_raw_input_echo(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            configuration, hosts, receipt = root/'deploy.json', root/'known_hosts', root/'receipt.json'
            configuration.write_text(json.dumps(config()))
            hosts.write_text(record())
            args = ['--config', str(configuration), '--known-hosts', str(hosts), '--receipt', str(receipt)]
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(IDENTITY.main(args), 0)
            self.assertEqual(json.loads(receipt.read_text())['status'], 'identity_verified')
            self.assertNotIn(ENCODED, output.getvalue())
            hosts.write_text(record(key='RAW_INPUT_MUST_NOT_APPEAR'))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(IDENTITY.main(args), 1)
            self.assertEqual(json.loads(receipt.read_text())['status'], 'failed')
            self.assertNotIn('RAW_INPUT_MUST_NOT_APPEAR', output.getvalue())
            self.assertNotIn(str(configuration), output.getvalue())

    def test_input_symlinks_oversize_duplicate_json_and_receipt_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            actual = root/'actual.json'; actual.write_text(json.dumps(config()))
            link = root/'config.json'; link.symlink_to(actual)
            with self.assertRaises(IDENTITY.IdentityError):
                IDENTITY.read_config(link)
            actual.write_text('{"schema":1,"schema":1}')
            with self.assertRaises(IDENTITY.IdentityError):
                IDENTITY.read_config(actual)
            actual.write_text('x' * 16385)
            with self.assertRaises(IDENTITY.IdentityError):
                IDENTITY.read_config(actual)
            secret_target = root/'unchanged.json'; secret_target.write_text('preserve me')
            receipt = root/'receipt.json'; receipt.symlink_to(secret_target)
            with self.assertRaises(IDENTITY.IdentityError):
                IDENTITY.write_receipt(receipt, {'status': 'failed'})
            self.assertEqual(secret_target.read_text(), 'preserve me')
            with self.assertRaises(IDENTITY.IdentityError):
                IDENTITY.write_receipt(root/'..'/'escape.json', {'status': 'failed'})
            with self.assertRaises(IDENTITY.IdentityError):
                IDENTITY.write_receipt(root/'id_ed25519', {'status': 'failed'})

    def test_cli_argument_errors_are_exit_one_without_echo(self):
        for args in [['--raw-sensitive-input'], ['--config', 'unused', '--known-hosts', 'unused', '--port', 'DO_NOT_ECHO']]:
            output, errors = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                self.assertEqual(IDENTITY.main(args), 1)
            self.assertEqual(json.loads(output.getvalue())['status'], 'failed')
            self.assertNotIn('DO_NOT_ECHO', output.getvalue() + errors.getvalue())
            self.assertNotIn('raw-sensitive-input', output.getvalue() + errors.getvalue())


if __name__ == '__main__':
    unittest.main(verbosity=2)
