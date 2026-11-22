#!/usr/bin/env python3
"""Quarantine exactly one known, unconfigured, closed failed CMS core tree."""
import argparse
import fcntl
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import shlex
import stat
import sys


class Gate(Exception):
    pass


def quarantine_failed_core(root, cms, private, receipt, owner_uid):
    report = {'schema': 1, 'status': 'blocked', 'cms_url': 'https://www.aptredlight.com/cms',
              'known_failure_run': '45022484164-1', 'writes_performed': False,
              'quarantined': False, 'front_preserved': False, 'rollback_available': False}
    lock_fd = None
    def check(ok, code):
        if not ok:
            raise Gate(code)
    def plain(path, kind=None):
        check(not any(p.is_symlink() for p in (path, *path.parents)), 'symlink_refused')
        info = path.stat()
        check(info.st_uid == owner_uid, 'owner_mismatch')
        if kind == 'file':
            check(stat.S_ISREG(info.st_mode), 'regular_file_required')
        if kind == 'dir':
            check(stat.S_ISDIR(info.st_mode), 'directory_required')
        return info
    def absent_config():
        for path in (root/'wp-config.php', cms/'wp-config.php'):
            check(not os.path.lexists(path), 'wp_config_present_refused')
    def front_hashes():
        hashes = {}
        for name in ('index.html', '.htaccess'):
            path = root/name
            info = plain(path, 'file')
            check(info.st_size <= 16*1024*1024, 'front_file_over_limit')
            with path.open('rb') as stream:
                digest = hashlib.sha256()
                for block in iter(lambda: stream.read(1024*1024), b''):
                    digest.update(block)
                hashes[name] = digest.hexdigest()
        return hashes
    try:
        root, cms, private, receipt = map(Path, (root, cms, private, receipt))
        check(cms == root/'cms' and receipt == private/'receipts/run-45022484164-1.json', 'fixed_scope_mismatch')
        check(owner_uid == os.getuid(), 'process_owner_mismatch')
        for path in (root, cms, private, private/'receipts'):
            plain(path, 'dir')
        check((private.stat().st_mode & 0o777) == 0o700, 'private_directory_not_700')
        lock = private/'.bootstrap.lock'
        plain(lock, 'file')
        lock_fd = os.open(lock, os.O_RDWR | os.O_NOFOLLOW)
        check(os.fstat(lock_fd).st_uid == owner_uid, 'lock_owner_mismatch')
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Gate('bootstrap_busy') from None
        report['bootstrap_lock_acquired'] = True
        before = front_hashes()
        absent_config()
        info = plain(receipt, 'file')
        check(info.st_size <= 1024*1024, 'known_receipt_over_limit')
        prior = json.loads(receipt.read_text(encoding='utf-8'))
        check(prior.get('status') == 'failed' and prior.get('reason') == 'core_checksums_failed'
              and prior.get('last_step') == 'core_download' and prior.get('wordpress_installed') is False
              and prior.get('cms_url') == report['cms_url'], 'known_receipt_mismatch')
        report['known_failure_verified'] = True
        maintenance = cms/'.htaccess'
        check(plain(maintenance, 'file').st_size <= 65536, 'maintenance_over_limit')
        closed = 'DirectoryIndex index.php\nOptions -Indexes\nRequire all denied\n'
        check(maintenance.read_text(encoding='utf-8').replace('\r\n', '\n') == closed, 'maintenance_not_closed')
        report['maintenance_verified_closed'] = True
        directories, files = 0, 0
        for current, dirs, names in os.walk(cms, followlinks=False):
            directories += 1
            files += len(names)
            check(directories + files <= 10000, 'core_tree_limit')
            plain(Path(current), 'dir')
            for name in dirs:
                plain(Path(current)/name, 'dir')
            for name in names:
                plain(Path(current)/name, 'file')
        report['tree_counts'] = {'directories': directories, 'files': files}
        destination_parent = private/'quarantine'
        destination = destination_parent/'core-45022484164-1'
        check(not os.path.lexists(destination), 'quarantine_destination_exists')
        check(not destination_parent.is_symlink(), 'quarantine_parent_symlink')
        if destination_parent.exists():
            plain(destination_parent, 'dir')
            check((destination_parent.stat().st_mode & 0o777) == 0o700, 'quarantine_parent_not_700')
        # Recheck all no-config, closed-tree and front gates while holding the same
        # bootstrap flock immediately before the only rename operation.
        absent_config()
        check(front_hashes() == before, 'frontend_changed_before_quarantine')
        check(maintenance.read_text(encoding='utf-8').replace('\r\n', '\n') == closed, 'maintenance_changed')
        if not destination_parent.exists():
            destination_parent.mkdir(mode=0o700)
            report['writes_performed'] = True
        check(not os.path.lexists(destination), 'quarantine_destination_exists')
        os.rename(cms, destination)
        report.update(writes_performed=True, quarantined=True, rollback_available=True)
        destination.chmod(0o700)
        report['front_preserved'] = front_hashes() == before
        check(report['front_preserved'], 'frontend_changed_during_quarantine')
        check(not os.path.lexists(cms) and not os.path.lexists(root/'wp-config.php'), 'unexpected_post_quarantine_state')
        report['status'] = 'quarantined'
    except Gate as error:
        report['reason'] = str(error)
        if report['writes_performed']:
            report['status'] = 'failed'
    except Exception as error:
        report['reason'] = 'quarantine_exception'
        report['error_class'] = type(error).__name__
        if report['writes_performed']:
            report['status'] = 'failed'
    finally:
        if lock_fd is not None:
            os.close(lock_fd)  # Releases only our flock; never removes or unlocks a stale lock.
    return report


REMOTE = ('import fcntl,hashlib,json,os,stat\nfrom pathlib import Path\n'
          + 'class Gate(Exception):\n    pass\n' + inspect.getsource(quarantine_failed_core) + '''
HOME=Path('/home/u469397229')
ROOT=HOME/'domains/aptredlight.com/public_html'
PRIVATE=HOME/'.aptredlight-cms-bootstrap'
if HOME.is_symlink() or HOME.stat().st_uid != os.getuid():
 print(json.dumps({'schema':1,'status':'blocked','reason':'fixed_home_owner_mismatch','writes_performed':False,'quarantined':False,'front_preserved':False}))
else:
 print(json.dumps(quarantine_failed_core(ROOT,ROOT/'cms',PRIVATE,PRIVATE/'receipts/run-45022484164-1.json',os.getuid()),separators=(',',':')))
''')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runner', required=True, type=Path)
    parser.add_argument('--known-hosts', required=True, type=Path)
    parser.add_argument('--receipt', required=True, type=Path)
    args = parser.parse_args(argv)
    spec = importlib.util.spec_from_file_location('apt_cms_quarantine_runner', args.runner)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    result = runner.child(runner.ssh_arguments(args.known_hosts) + ['python3 -c ' + shlex.quote(REMOTE)], timeout=60)
    try:
        report = json.loads(result.stdout)
        if not isinstance(report, dict) or report.get('status') not in ('blocked', 'failed', 'quarantined'):
            raise ValueError('unexpected quarantine receipt')
        if report.get('status') == 'quarantined' and (report.get('front_preserved') is not True or report.get('quarantined') is not True):
            raise ValueError('unverified quarantine')
    except Exception:
        report = {'schema':1,'status':'blocked','reason':'remote_quarantine_receipt_unavailable',
                  'writes_performed':None,'outcome':'unknown','ssh_exit_code':result.returncode}
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(report, indent=2)+'\n')
    args.receipt.chmod(0o600)
    print(json.dumps(report))
    return 0 if result.returncode == 0 and report['status'] == 'quarantined' else 3


if __name__ == '__main__':
    sys.exit(main())
