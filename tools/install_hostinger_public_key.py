#!/usr/bin/env python3
"""Authorize one dedicated public key; never accepts passwords or private keys."""
import base64
import fcntl
import json
import os
from pathlib import Path
import pwd
import re
import shlex
import shutil
import stat
import sys
import uuid

USER = 'u469397229'
HOME = '/home/u469397229'
PROJECT = 'appgprj_6addb8c872b081918d711d7bc0c5cbf4'
ORIGIN = 'https://www.aptredlight.com'
OPTIONS = 'no-agent-forwarding,no-port-forwarding,no-X11-forwarding,no-pty'
AUTH = 'authorized_keys'
LOCK = '.aptredlight-authorized-keys.lock'


def check(value):
    if not value:
        raise RuntimeError('Authorization safety check failed.')


def _owned(info, uid, directory=False):
    check(info.st_uid == uid and (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)))
    check(not info.st_mode & 0o022)
    if not directory:
        check(info.st_nlink == 1)


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_uid, stat.S_IFMT(info.st_mode))


def _snapshot(directory, uid):
    try:
        descriptor = os.open(AUTH, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
    except FileNotFoundError:
        return None, b''
    try:
        info = os.fstat(descriptor)
        _owned(info, uid)
        check(_identity(info) == _identity(os.stat(AUTH, dir_fd=directory, follow_symlinks=False)))
        check(info.st_size <= 4 * 1024 * 1024)
        chunks = []
        while True:
            value = os.read(descriptor, 65536)
            if not value:
                break
            chunks.append(value)
        data = b''.join(chunks)
        check(len(data) == info.st_size)
        stamp = (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
                 info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        return stamp, data
    finally:
        os.close(descriptor)


def _before_replace(path):
    """Test hook: the real installer does not call any external program here."""
    return None


def _public(text):
    check(isinstance(text, str) and 0 < len(text) <= 4096)
    line = text[:-2] if text.endswith('\r\n') else text[:-1] if text.endswith('\n') else text
    check('\n' not in line and '\r' not in line)
    prefix = OPTIONS + ' '
    check(line.startswith(prefix))
    match = re.fullmatch(r'ssh-ed25519 ([A-Za-z0-9+/]+={0,2})(?: ([ -~]{1,100}))?', line[len(prefix):])
    check(match is not None)
    blob = base64.b64decode(match[1], validate=True)
    check(len(blob) == 51 and blob[:4] == b'\x00\x00\x00\x0b' and blob[4:15] == b'ssh-ed25519'
          and blob[15:19] == b'\x00\x00\x00\x20' and base64.b64encode(blob).decode() == match[1])
    return match[1], (line + '\n').encode('ascii')


def _already(data, blob):
    for line in data.splitlines():
        if not line.strip() or line.lstrip().startswith(b'#'):
            continue
        try:
            tokens = shlex.split(line.decode('utf-8', 'surrogateescape'), comments=True)
        except ValueError:
            continue
        for index in (0, 1):
            if len(tokens) > index + 1 and tokens[index] == 'ssh-ed25519' and tokens[index + 1] == blob:
                return True
    return False


def install(public_text, home=None, expected_uid=None, expected_user=USER, verify_identity=True):
    blob, addition = _public(public_text)
    uid = os.geteuid()
    check(uid == (uid if expected_uid is None else expected_uid))
    account = pwd.getpwuid(uid)
    check(account.pw_name == expected_user)
    home = Path(HOME if home is None else home)
    check(home.is_absolute() and home.resolve() == home)
    _owned(os.lstat(home), uid, True)
    if verify_identity:
        check(expected_user == USER and str(home) == HOME and account.pw_dir == HOME and shutil.which('tar'))
        source = home / 'domains/aptredlight.com/public_html/source-release.json'
        for directory in (home / 'domains', source.parent.parent, source.parent):
            _owned(os.lstat(directory), uid, True)
        descriptor = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            _owned(os.fstat(descriptor), uid)
            check(os.fstat(descriptor).st_size <= 65536)
            value = json.loads(os.read(descriptor, 65537))
        finally:
            os.close(descriptor)
        check(value.get('project_id') == PROJECT and value.get('canonical_origin') == ORIGIN)
    home_fd = ssh_fd = lock_fd = None
    temporary = None
    try:
        home_fd = os.open(home, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.mkdir('.ssh', 0o700, dir_fd=home_fd)
        except FileExistsError:
            pass
        ssh_fd = os.open('.ssh', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=home_fd)
        _owned(os.fstat(ssh_fd), uid, True)
        os.fchmod(ssh_fd, 0o700)
        lock_fd = os.open(LOCK, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600, dir_fd=ssh_fd)
        _owned(os.fstat(lock_fd), uid)
        check(stat.S_IMODE(os.fstat(lock_fd).st_mode) == 0o600)
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        check(_identity(os.fstat(lock_fd)) == _identity(os.stat(LOCK, dir_fd=ssh_fd, follow_symlinks=False)))
        original_stamp, original = _snapshot(ssh_fd, uid)
        if _already(original, blob):
            return {'status': 'already_authorized', 'changed': False}
        payload = original + (b'\n' if original and not original.endswith(b'\n') else b'') + addition
        temporary = '.aptredlight-key-' + uuid.uuid4().hex
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600, dir_fd=ssh_fd)
        with os.fdopen(descriptor, 'wb') as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        _before_replace(home / '.ssh' / AUTH)
        check(_snapshot(ssh_fd, uid) == (original_stamp, original))
        check(_identity(os.fstat(home_fd)) == _identity(os.lstat(home)))
        check(_identity(os.fstat(ssh_fd)) == _identity(os.stat('.ssh', dir_fd=home_fd, follow_symlinks=False)))
        os.replace(temporary, AUTH, src_dir_fd=ssh_fd, dst_dir_fd=ssh_fd)
        temporary = None
        os.fsync(ssh_fd)
        return {'status': 'authorized', 'changed': True}
    finally:
        if temporary is not None and ssh_fd is not None:
            try:
                os.unlink(temporary, dir_fd=ssh_fd)
            except FileNotFoundError:
                pass
        if lock_fd is not None:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)
        for descriptor in (ssh_fd, home_fd):
            if descriptor is not None:
                os.close(descriptor)


def main():
    try:
        result = install(sys.stdin.read(4097))
        print(json.dumps(result, separators=(',', ':')))
        return 0
    except Exception:
        print('Public key authorization failed; input was not logged.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
