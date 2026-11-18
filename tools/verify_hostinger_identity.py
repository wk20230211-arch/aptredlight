#!/usr/bin/env python3
"""Verify a scanned public SSH key against the owner-pinned Hostinger identity.

This module performs no network operation and never reads an SSH private key.
"""
import argparse
import base64
import binascii
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import struct
import tempfile

PROJECT = 'appgprj_6addb8c872b081918d711d7bc0c5cbf4'
DOMAIN = 'aptredlight.com'
ORIGIN = 'https://www.aptredlight.com'
USER = 'u469397229'
WEB_ROOT = '/home/u469397229/domains/aptredlight.com/public_html'
ALGORITHM = 'ssh-ed25519'
CONFIG_FIELDS = {'schema', 'project_id', 'domain', 'canonical_origin', 'ssh_user',
                 'ssh_port', 'web_root', 'ssh_host', 'ssh_host_key_sha256',
                 'ssh_host_key_algorithm'}


class IdentityError(ValueError):
    """A bounded, non-sensitive verification failure."""


def require(condition, message):
    if not condition:
        raise IdentityError(message)


def valid_host(value):
    require(isinstance(value, str) and value == value.strip() and 0 < len(value) <= 253,
            'Invalid SSH host.')
    require(not any(ord(char) < 33 or ord(char) == 127 for char in value)
            and not any(char in value for char in '/\\@[]%'), 'Invalid SSH host.')
    try:
        ipaddress.ip_address(value)
        return value
    except ValueError:
        require(':' not in value and not re.fullmatch(r'[0-9.]+', value), 'Invalid SSH host.')
        require(all(re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', part)
                    for part in value.split('.')), 'Invalid SSH host.')
    return value


def valid_port(value):
    require(type(value) is int and 1 <= value <= 65535, 'Invalid SSH port.')
    return value


def fingerprint_bytes(value):
    require(isinstance(value, str) and re.fullmatch(r'SHA256:[A-Za-z0-9+/]{43}', value),
            'Invalid pinned SSH fingerprint.')
    encoded = value[len('SHA256:'):]
    try:
        raw = base64.b64decode(encoded + '=', validate=True)
    except (ValueError, binascii.Error):
        raise IdentityError('Invalid pinned SSH fingerprint.') from None
    require(len(raw) == 32 and base64.b64encode(raw).decode('ascii').rstrip('=') == encoded,
            'Invalid pinned SSH fingerprint.')
    return raw


def validate_config(config):
    require(isinstance(config, dict) and set(config) <= CONFIG_FIELDS,
            'Unexpected deployment configuration fields.')
    require(type(config.get('schema')) is int and config['schema'] == 1
            and config.get('project_id') == PROJECT and config.get('domain') == DOMAIN
            and config.get('canonical_origin') == ORIGIN and config.get('ssh_user') == USER
            and config.get('web_root') == WEB_ROOT, 'Deployment configuration scope mismatch.')
    require(config.get('ssh_host_key_algorithm', ALGORITHM) == ALGORITHM,
            'Only the pinned ED25519 host key is permitted.')
    valid_host(config.get('ssh_host'))
    valid_port(config.get('ssh_port'))
    fingerprint_bytes(config.get('ssh_host_key_sha256'))
    return config


def decode_public_key(encoded):
    require(isinstance(encoded, str) and len(encoded) <= 512, 'Invalid public host key encoding.')
    try:
        blob = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise IdentityError('Invalid public host key encoding.') from None
    require(base64.b64encode(blob).decode('ascii') == encoded, 'Non-canonical public host key encoding.')
    position = 0

    def read_string():
        nonlocal position
        require(position + 4 <= len(blob), 'Malformed SSH public key wire data.')
        length = struct.unpack('>I', blob[position:position + 4])[0]
        position += 4
        require(length <= len(blob) - position, 'Malformed SSH public key wire data.')
        value = blob[position:position + length]
        position += length
        return value

    require(read_string() == ALGORITHM.encode('ascii'), 'SSH key wire algorithm mismatch.')
    require(len(read_string()) == 32 and position == len(blob), 'Invalid ED25519 key length or trailing wire data.')
    return blob


def verify(config, known_hosts_text, host=None, port=None):
    """Return public identity metadata only after exact target/key/pin validation."""
    config = validate_config(config)
    host = valid_host(config['ssh_host'] if host is None else host)
    port = valid_port(config['ssh_port'] if port is None else port)
    require(isinstance(known_hosts_text, str)
            and len(known_hosts_text.encode('utf-8')) <= 65536
            and not any(ord(char) < 32 and char not in '\r\n\t' or ord(char) == 127
                        for char in known_hosts_text), 'Invalid known_hosts content.')
    expected_target = host if port == 22 else '[' + host + ']:' + str(port)
    candidates = []
    for line in known_hosts_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        columns = stripped.split()
        require(len(columns) >= 3, 'Malformed known_hosts record.')
        require(columns[0] == expected_target, 'Known host target does not match the configured SSH endpoint.')
        require(columns[1] == ALGORITHM, 'Known host algorithm is not ED25519.')
        candidates.append(columns[2])
    require(len(candidates) == 1, 'Exactly one matching SSH host key is required; duplicates are refused.')
    blob = decode_public_key(candidates[0])
    fingerprint = 'SHA256:' + base64.b64encode(hashlib.sha256(blob).digest()).decode('ascii').rstrip('=')
    require(hmac.compare_digest(fingerprint, config['ssh_host_key_sha256']), 'SSH host key fingerprint mismatch; no identity was accepted.')
    return {'status': 'identity_verified', 'verified': True, 'host': host, 'port': port,
            'algorithm': ALGORITHM, 'fingerprint': fingerprint}


def _safe_file(path, maximum):
    path = Path(path)
    require(not any(part == '..' or any(ord(char) < 32 or ord(char) == 127 for char in part)
                    for part in path.parts), 'Unsafe input file path.')
    require(path.exists() and not path.is_symlink() and stat.S_ISREG(path.stat().st_mode),
            'Input must be a regular file.')
    require(path.absolute() == path.resolve(), 'Input file must not have symlink ancestors.')
    require(path.stat().st_size <= maximum, 'Input file exceeds the verification limit.')
    return path


def read_config(path):
    try:
        text = _safe_file(path, 16384).read_text(encoding='utf-8')
        def unique(pairs):
            result = {}
            for key, value in pairs:
                require(key not in result, 'Duplicate configuration fields are refused.')
                result[key] = value
            return result
        return json.loads(text, object_pairs_hook=unique)
    except IdentityError:
        raise
    except (OSError, ValueError, UnicodeError):
        raise IdentityError('Deployment configuration could not be read safely.') from None


def write_receipt(path, value):
    destination = Path(path)
    require(destination.suffix == '.json' and not any(part == '..' or any(ord(c) < 32 or ord(c) == 127 for c in part)
                                                    for part in destination.parts), 'Unsafe receipt path.')
    require(destination.parent.is_dir() and destination.parent.absolute() == destination.parent.resolve()
            and not destination.is_symlink() and (not destination.exists() or destination.is_file()),
            'Unsafe receipt destination.')
    temporary = None
    try:
        descriptor, temporary = tempfile.mkstemp(prefix='.hostinger-identity-', suffix='.json', dir=destination.parent)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
            os.fchmod(handle.fileno(), 0o600)
            json.dump(value, handle, sort_keys=True)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        temporary = None
    except OSError:
        raise IdentityError('Identity receipt could not be saved safely.') from None
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def main(argv=None):
    class SafeParser(argparse.ArgumentParser):
        def error(self, message):
            raise IdentityError('Invalid verification command arguments.')

    parser = SafeParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--known-hosts', required=True)
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    parser.add_argument('--receipt')
    args = None
    try:
        args = parser.parse_args(argv)
        config = read_config(args.config)
        try:
            known_hosts = _safe_file(args.known_hosts, 65536).read_text(encoding='utf-8')
        except (OSError, UnicodeError):
            raise IdentityError('Public known_hosts file could not be read safely.') from None
        result = verify(config, known_hosts, args.host, args.port)
        if args.receipt:
            write_receipt(args.receipt, result)
    except (IdentityError, OSError, ValueError):
        result = {'status': 'failed', 'verified': False,
                  'error': 'SSH identity verification failed; no key was accepted. Check the trusted pin and endpoint.'}
        if args and args.receipt:
            try:
                write_receipt(args.receipt, result)
            except (IdentityError, OSError):
                pass
        print(json.dumps(result, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
