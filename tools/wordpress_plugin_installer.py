"""Install only the reviewed APT plugin into one verified, existing branded WP.

CLI roots, plugin paths and hashes are fixed. No WordPress/database creation,
configuration-file reads, credentials, product queries or generic shell commands.
"""
import base64
import binascii
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse

DOMAINS_ROOT = Path('/home/u469397229/domains')
PRIVATE_ROOT = Path('/home/u469397229/.aptredlight-plugin-install')
DOMAINS = ('aptredlight.com', 'cms.aptredlight.com', 'wp.aptredlight.com',
           'admin.aptredlight.com', 'backend.aptredlight.com', 'blog.aptredlight.com')
SLUG = 'aptredlight-growth-desk'
SOURCE_COMMIT = 'b9e37cc02f25da1b1a5b9cc3dba0bc2aa49f3e08'
HASHES = {
    'aptredlight-growth-desk.php': '7088665080448f3ac067f57d8da0c64333b608bf28a0bc6f23247c48e7bb71e6',
    'readme.txt': '866b197329878c1a8c540671f1908e322f1d8903e4bcadb7a17ea098cfa298b5',
    'README.zh-CN.txt': '07c3b6a1572e44cdb7ac617607b86debc6dca7022cee068418cbeea78c6ed13b',
    'assets/admin.css': '0c12db3a032d044b488b378e90404dbd798b2d63909ec4ff5be681d3f7d10804',
    'assets/admin.js': '3bd7db991a3f078ebc272fc61f38ab677edc53104acd0ceba8fe88b538cf7333',
}
SKIP = {'uploads', 'assets', 'vendor', '.git', 'cache', 'caches', 'backup', 'backups',
        'node_modules', 'wp-content', 'wp-admin', 'wp-includes'}


class InstallerError(Exception):
    pass


def valid_files(payload):
    if not isinstance(payload, dict) or set(payload) != {'schema', 'source_commit', 'verified_files'}:
        raise InstallerError('invalid_payload')
    if payload['schema'] != 1 or payload['source_commit'] != SOURCE_COMMIT:
        raise InstallerError('unreviewed_source')
    rows = payload['verified_files']
    if not isinstance(rows, list) or len(rows) != len(HASHES):
        raise InstallerError('invalid_file_manifest')
    result, size = {}, 0
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'path', 'content_base64', 'sha256'}:
            raise InstallerError('invalid_file_manifest')
        name = row['path']
        if name not in HASHES or name in result or row['sha256'] != HASHES[name]:
            raise InstallerError('unreviewed_file')
        encoded = row['content_base64']
        if not isinstance(encoded, str) or len(encoded) > 1400000:
            raise InstallerError('payload_over_limit')
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            raise InstallerError('invalid_file_encoding') from None
        size += len(data)
        if size > 1024 * 1024 or hashlib.sha256(data).hexdigest() != HASHES[name]:
            raise InstallerError('file_integrity_failed')
        result[name] = data
    return result


def safe_chain(path):
    """Reject symlinks even when they point back inside the allowed tree."""
    return not any(item.is_symlink() for item in (path, *path.parents))


def same_plugin(path):
    if not path.is_dir() or not safe_chain(path):
        return False
    found = set()
    for current, dirs, files in os.walk(path, followlinks=False):
        if any((Path(current) / name).is_symlink() for name in dirs + files):
            return False
        for name in files:
            item = Path(current) / name
            relative = item.relative_to(path).as_posix()
            if relative not in HASHES or item.stat().st_size > 1024 * 1024:
                return False
            if hashlib.sha256(item.read_bytes()).hexdigest() != HASHES[relative]:
                return False
            found.add(relative)
    return found == set(HASHES)


class Installer:
    def __init__(self, domains_root=DOMAINS_ROOT, private_root=PRIVATE_ROOT, runner=None, wp=None):
        self.domains_root, self.private_root = Path(domains_root), Path(private_root)
        self.runner = runner or subprocess.run
        self.wp = wp if wp is not None else shutil.which('wp')
        self.deadline = time.monotonic() + 220
        self.report = {'schema': 1, 'status': 'blocked', 'source_commit': SOURCE_COMMIT,
                       'candidate_count': 0, 'eligible_count': 0, 'files_installed': False,
                       'activated': False, 'writes_performed': False,
                       'production_product_write_performed': False,
                       'rollback_status': 'not_required', 'role_review_required': False}

    def call(self, root, *args):
        left = self.deadline - time.monotonic()
        if left <= 0:
            raise InstallerError('total_deadline_reached')
        command = [self.wp, '--path=' + str(root), '--skip-plugins', '--skip-themes',
                   '--skip-packages', '--no-color', *args]
        try:
            result = self.runner(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 timeout=min(20, left), check=False)
        except subprocess.TimeoutExpired:
            raise InstallerError('wp_cli_timeout') from None
        if len(result.stdout) > 65536 or len(result.stderr) > 65536:
            raise InstallerError('wp_cli_output_over_limit')
        return result.returncode, result.stdout.decode('utf-8', errors='replace').strip()

    def discover(self):
        candidates, visited = [], 0
        if not safe_chain(self.domains_root):
            raise InstallerError('symlink_domains_root')
        for domain in DOMAINS:
            if time.monotonic() >= self.deadline:
                raise InstallerError('total_deadline_reached')
            public = self.domains_root / domain / 'public_html'
            if not public.exists() or not safe_chain(public):
                continue
            for current, dirs, _ in os.walk(public, followlinks=False):
                if time.monotonic() >= self.deadline:
                    raise InstallerError('total_deadline_reached')
                visited += 1
                if visited > 800:
                    raise InstallerError('scan_directory_limit')
                root = Path(current)
                depth = len(root.relative_to(public).parts)
                dirs[:] = [] if depth >= 4 else [name for name in dirs if
                    name.lower() not in SKIP and not name.startswith('.') and
                    not name.lower().startswith('.apt') and not (root / name).is_symlink()]
                markers = (root / 'wp-config.php', root / 'wp-load.php', root / 'wp-admin')
                if (all(not p.is_symlink() for p in markers) and markers[0].is_file() and
                        markers[1].is_file() and markers[2].is_dir()):
                    if safe_chain(root):
                        candidates.append((domain, public, root))
        self.report['candidate_count'] = len(candidates)
        if not candidates:
            raise InstallerError('no_wordpress_installation')
        if not self.wp:
            raise InstallerError('wp_cli_unavailable')
        eligible = []
        rejected = []
        for domain, public, root in candidates:
            if self.call(root, 'core', 'is-installed')[0]:
                rejected.append('wp_core_not_installed')
                continue
            code, siteurl = self.call(root, 'option', 'get', 'siteurl')
            parsed = urllib.parse.urlsplit(siteurl)
            expected_path = '/' + root.relative_to(public).as_posix()
            if expected_path == '/.':
                expected_path = ''
            if (code or parsed.scheme != 'https' or parsed.hostname not in (*DOMAINS, 'www.aptredlight.com') or
                    parsed.username or parsed.password or parsed.port not in (None, 443) or
                    parsed.query or parsed.fragment or parsed.path.rstrip('/') != expected_path):
                rejected.append('siteurl_outside_expected_scope')
                continue
            # The hostname must match the directory: www is the sole apex alias.
            expected_hosts = {domain, 'www.aptredlight.com'} if domain == 'aptredlight.com' else {domain}
            if parsed.hostname not in expected_hosts:
                rejected.append('siteurl_domain_mismatch')
                continue
            if self.call(root, 'plugin', 'is-active', 'woocommerce')[0]:
                rejected.append('woocommerce_not_active')
                continue
            eligible.append((domain, public, root))
        self.report['eligible_count'] = len(eligible)
        self.report['rejected_candidate_reasons'] = sorted(set(rejected))
        if len(eligible) != 1:
            raise InstallerError('ambiguous_wordpress_installations' if len(eligible) > 1 else
                                 'no_eligible_wordpress_installation')
        return eligible[0]

    def run(self, payload):
        activation_attempted, new_install, target, root = False, False, None, None
        try:
            files = valid_files(payload)  # Validate trusted source before all filesystem changes.
            domain, public, root = self.discover()
            self.report['target'] = {'domain': domain, 'relative_root': root.relative_to(public).as_posix()}
            plugins = root / 'wp-content/plugins'
            if not plugins.is_dir() or not safe_chain(plugins):
                raise InstallerError('plugin_directory_unavailable')
            # Do not guess a custom WP_PLUGIN_DIR or silently install into the wrong folder.
            code, configured_plugins = self.call(root, 'eval', 'echo WP_PLUGIN_DIR;')
            if code or Path(configured_plugins) != plugins or not safe_chain(Path(configured_plugins)):
                raise InstallerError('custom_plugin_directory_requires_review')
            target = plugins / SLUG
            if target.exists() or target.is_symlink():
                if not same_plugin(target):
                    raise InstallerError('existing_plugin_requires_review')
                state = self.call(root, 'plugin', 'is-active', SLUG)[0]
                if state not in (0, 1):
                    raise InstallerError('plugin_state_unavailable')
                if state == 0:
                    code, version = self.call(root, 'plugin', 'get', SLUG, '--field=version')
                    if code or version != '1.0.0':
                        raise InstallerError('plugin_version_readback_failed')
                    self.report.update(status='already_installed', activated=True, plugin_version=version)
                    return self.report
            else:
                if not safe_chain(self.private_root) or self.private_root.is_symlink():
                    raise InstallerError('unsafe_private_staging')
                self.private_root.mkdir(mode=0o700, parents=True, exist_ok=True)
                self.private_root.chmod(0o700)
                self.report['writes_performed'] = True
                stage = Path(tempfile.mkdtemp(prefix='apt-plugin-', dir=self.private_root))
                try:
                    for name, data in files.items():
                        destination = stage / name
                        destination.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
                        destination.write_bytes(data)
                        destination.chmod(0o644)
                    stage.chmod(0o755)
                    # Recheck both paths immediately before the atomic install.
                    if target.exists() or target.is_symlink() or not safe_chain(plugins):
                        raise InstallerError('plugin_directory_changed')
                    os.rename(stage, target)
                    new_install = True
                    self.report['files_installed'] = True
                finally:
                    if stage.exists():
                        shutil.rmtree(stage)
            activation_attempted = True
            self.report['writes_performed'] = True
            if self.call(root, 'plugin', 'activate', SLUG)[0]:
                raise InstallerError('plugin_activation_failed')
            if self.call(root, 'plugin', 'is-active', SLUG)[0]:
                raise InstallerError('activation_readback_failed')
            code, version = self.call(root, 'plugin', 'get', SLUG, '--field=version')
            if code or version != '1.0.0':
                raise InstallerError('plugin_version_readback_failed')
            self.report.update(status='installed' if new_install else 'activated', activated=True,
                               plugin_version=version)
        except Exception as error:
            self.report['reason'] = str(error) if isinstance(error, InstallerError) else 'installer_failed'
            if activation_attempted:
                self.report['role_review_required'] = True
                try:
                    self.call(root, 'plugin', 'deactivate', SLUG)
                    state = self.call(root, 'plugin', 'is-active', SLUG)[0]
                    self.report['activated'] = False if state == 1 else True if state == 0 else None
                    self.report['rollback_status'] = 'activation_restored' if state == 1 else 'manual_review_required'
                except Exception:
                    self.report['activated'] = None
                    self.report['rollback_status'] = 'manual_review_required'
            if new_install:
                # Never remove potentially active code when deactivation is unconfirmed.
                can_remove = not activation_attempted or self.report['rollback_status'] == 'activation_restored'
                if can_remove and same_plugin(target):
                    shutil.rmtree(target)
                    self.report['files_installed'] = False
                    if self.report['rollback_status'] in ('not_required', 'activation_restored'):
                        self.report['rollback_status'] = 'new_files_removed'
                else:
                    self.report['rollback_status'] = 'manual_review_required'
            self.report['status'] = 'failed' if self.report['writes_performed'] else 'blocked'
        return self.report


def main():
    try:
        raw = sys.stdin.buffer.read(1500001)
        if len(raw) > 1500000:
            raise InstallerError('payload_over_limit')
        payload = json.loads(raw)
        report = Installer().run(payload)
    except Exception as error:
        report = {'schema': 1, 'status': 'blocked', 'reason': str(error) if isinstance(error, InstallerError)
                  else 'invalid_payload', 'writes_performed': False, 'activated': False}
    print(json.dumps(report, separators=(',', ':')))
    return 0 if report['status'] in ('installed', 'activated', 'already_installed') else 3


if __name__ == '__main__':
    sys.exit(main())
