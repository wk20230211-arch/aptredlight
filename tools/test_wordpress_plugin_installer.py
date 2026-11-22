"""Real temporary filesystem + injected WP CLI outcomes. No network or real WP."""
import base64
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

SPEC = importlib.util.spec_from_file_location('installer', Path(__file__).with_name('wordpress_plugin_installer.py'))
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)
PLUGIN = Path(__file__).resolve().parents[1] / 'integrations/wordpress/aptredlight-growth-desk'
if not PLUGIN.is_dir():
    PLUGIN = Path('/workspace/apt-wordpress-admin-20261122/plugin/aptredlight-growth-desk')


def payload():
    return {'schema': 1, 'source_commit': mod.SOURCE_COMMIT, 'verified_files': [
        {'path': name, 'sha256': digest,
         'content_base64': base64.b64encode((PLUGIN / name).read_bytes()).decode('ascii')}
        for name, digest in mod.HASHES.items()]}


class FakeWP:
    def __init__(self):
        self.sites, self.active, self.calls = {}, set(), []
        self.activation_fail = False
        self.deactivation_fail = False
        self.version = '1.0.0'
        self.state_exit_override = None

    def add(self, root, siteurl, core=True, woo=True):
        self.sites[str(root)] = {'siteurl': siteurl, 'core': core, 'woo': woo}

    def __call__(self, command, **kwargs):
        assert not kwargs.get('shell')
        assert kwargs['timeout'] <= 20
        self.calls.append(command)
        root = command[1].removeprefix('--path=')
        args = command[command.index('--no-color') + 1:]
        site = self.sites[root]
        code, out = 0, ''
        if args == ['core', 'is-installed']:
            code = 0 if site['core'] else 1
        elif args == ['option', 'get', 'siteurl']:
            out = site['siteurl']
        elif args == ['plugin', 'is-active', 'woocommerce']:
            code = 0 if site['woo'] else 1
        elif args == ['eval', 'echo WP_PLUGIN_DIR;']:
            out = str(Path(root) / 'wp-content/plugins')
        elif args == ['plugin', 'is-active', mod.SLUG]:
            code = self.state_exit_override if self.state_exit_override is not None else 0 if root in self.active else 1
        elif args == ['plugin', 'activate', mod.SLUG]:
            self.active.add(root)
            code = 1 if self.activation_fail else 0
        elif args == ['plugin', 'deactivate', mod.SLUG]:
            if self.deactivation_fail:
                code = 1
            else:
                self.active.discard(root)
        elif args == ['plugin', 'get', mod.SLUG, '--field=version']:
            out = self.version
        else:
            raise AssertionError('Unexpected command: ' + repr(args))
        # Deliberately sensitive-looking stderr must never reach the receipt.
        return subprocess.CompletedProcess(command, code, out.encode(), b'password=DO-NOT-PRINT')


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.domains = self.home / 'domains'
        self.domains.mkdir()
        self.private = self.home / '.aptredlight-plugin-install'
        self.runner = FakeWP()
        self.data = payload()

    def tearDown(self):
        self.temp.cleanup()

    def wp(self, domain='aptredlight.com', sub=''):
        root = self.domains / domain / 'public_html' / sub
        root.mkdir(parents=True)
        (root / 'wp-admin').mkdir()
        (root / 'wp-config.php').write_text('sensitive configuration is never opened')
        (root / 'wp-load.php').write_text('fixture')
        (root / 'wp-content/plugins').mkdir(parents=True)
        host = 'www.aptredlight.com' if domain == 'aptredlight.com' else domain
        url = 'https://' + host + ('/' + sub if sub else '')
        self.runner.add(root, url)
        return root

    def run_install(self, data=None, wp='/fixture/wp'):
        return mod.Installer(self.domains, self.private, self.runner, wp).run(data or self.data)

    def test_no_wordpress_is_zero_writes(self):
        root = self.domains / 'aptredlight.com/public_html'
        root.mkdir(parents=True)
        (root / 'index.html').write_text('Existing static front remains intact')
        report = self.run_install()
        self.assertEqual(report['reason'], 'no_wordpress_installation')
        self.assertFalse(report['writes_performed'])
        self.assertFalse(self.private.exists())
        self.assertFalse((root / 'wp-content').exists())
        self.assertEqual((root / 'index.html').read_text(), 'Existing static front remains intact')
        self.assertEqual(self.runner.calls, [])

    def test_unique_valid_wordpress_installs_and_activates(self):
        root = self.wp()
        unrelated = root / 'wp-content/plugins/unrelated'
        unrelated.mkdir()
        (unrelated / 'original.php').write_text('untouched')
        result = self.run_install()
        self.assertEqual(result['status'], 'installed')
        self.assertTrue(result['activated'])
        self.assertTrue(mod.same_plugin(root / 'wp-content/plugins' / mod.SLUG))
        self.assertEqual((unrelated / 'original.php').read_text(), 'untouched')
        self.assertNotIn('DO-NOT-PRINT', json.dumps(result))
        self.assertEqual(self.private.stat().st_mode & 0o777, 0o700)

    def test_multiple_valid_wordpress_is_ambiguous_without_writes(self):
        self.wp()
        self.wp('cms.aptredlight.com')
        report = self.run_install()
        self.assertEqual(report['reason'], 'ambiguous_wordpress_installations')
        self.assertFalse(report['writes_performed'])
        self.assertFalse(self.private.exists())

    def test_wrong_domain_and_backup_path_not_eligible(self):
        root = self.wp(sub='oldsite')
        self.runner.sites[str(root)]['siteurl'] = 'https://www.aptredlight.com'
        report = self.run_install()
        self.assertEqual(report['reason'], 'no_eligible_wordpress_installation')
        self.assertIn('siteurl_outside_expected_scope', report['rejected_candidate_reasons'])
        self.assertFalse(report['writes_performed'])

    def test_external_hostname_not_eligible(self):
        root = self.wp()
        self.runner.sites[str(root)]['siteurl'] = 'https://aptredlight.com.attacker.test'
        report = self.run_install()
        self.assertFalse(report['writes_performed'])
        self.assertEqual(report['eligible_count'], 0)

    def test_unrelated_domains_are_not_scanned(self):
        self.wp('unrelated.example')
        report = self.run_install()
        self.assertEqual(report['candidate_count'], 0)
        self.assertFalse(self.runner.calls)

    def test_unreviewed_source_and_corrupt_file_are_rejected_before_commands(self):
        self.wp()
        data = copy.deepcopy(self.data)
        data['source_commit'] = '0' * 40
        self.assertEqual(self.run_install(data)['reason'], 'unreviewed_source')
        data = copy.deepcopy(self.data)
        data['verified_files'][0]['content_base64'] = base64.b64encode(b'tampered PHP').decode()
        self.assertEqual(self.run_install(data)['reason'], 'file_integrity_failed')
        self.assertFalse(self.runner.calls)

    def test_path_traversal_file_is_rejected(self):
        self.wp()
        self.data['verified_files'][0]['path'] = '../../wp-config.php'
        report = self.run_install()
        self.assertEqual(report['reason'], 'unreviewed_file')
        self.assertFalse(report['writes_performed'])

    def test_existing_different_plugin_is_not_touched(self):
        root = self.wp()
        target = root / 'wp-content/plugins' / mod.SLUG
        target.mkdir()
        (target / 'custom.php').write_text('Existing plugin contents')
        report = self.run_install()
        self.assertEqual(report['reason'], 'existing_plugin_requires_review')
        self.assertFalse(report['writes_performed'])
        self.assertFalse(self.private.exists())
        self.assertEqual((target / 'custom.php').read_text(), 'Existing plugin contents')

    def test_matching_active_plugin_is_idempotent(self):
        root = self.wp()
        target = root / 'wp-content/plugins' / mod.SLUG
        shutil.copytree(PLUGIN, target)
        self.runner.active.add(str(root))
        report = self.run_install()
        self.assertEqual(report['status'], 'already_installed')
        self.assertFalse(report['writes_performed'])

    def test_matching_inactive_plugin_is_activated_without_replacement(self):
        root = self.wp()
        target = root / 'wp-content/plugins' / mod.SLUG
        shutil.copytree(PLUGIN, target)
        before = (target / 'aptredlight-growth-desk.php').stat().st_mtime_ns
        report = self.run_install()
        self.assertEqual(report['status'], 'activated')
        self.assertFalse(report['files_installed'])
        self.assertEqual((target / 'aptredlight-growth-desk.php').stat().st_mtime_ns, before)

    def test_unknown_existing_plugin_state_is_not_treated_as_inactive(self):
        root = self.wp()
        target = root / 'wp-content/plugins' / mod.SLUG
        shutil.copytree(PLUGIN, target)
        self.runner.state_exit_override = 2
        report = self.run_install()
        self.assertEqual(report['reason'], 'plugin_state_unavailable')
        self.assertFalse(report['writes_performed'])
        self.assertFalse(any('activate' in command or 'deactivate' in command for command in self.runner.calls))

    def test_activation_failure_removes_only_new_files_and_flags_role_review(self):
        root = self.wp()
        self.runner.activation_fail = True
        report = self.run_install()
        self.assertEqual(report['reason'], 'plugin_activation_failed')
        self.assertEqual(report['rollback_status'], 'new_files_removed')
        self.assertFalse((root / 'wp-content/plugins' / mod.SLUG).exists())
        self.assertNotIn(str(root), self.runner.active)
        self.assertTrue(report['role_review_required'])

    def test_version_failure_also_rolls_back(self):
        root = self.wp()
        self.runner.version = '9.9.9'
        report = self.run_install()
        self.assertEqual(report['reason'], 'plugin_version_readback_failed')
        self.assertFalse((root / 'wp-content/plugins' / mod.SLUG).exists())

    def test_uncertain_deactivation_preserves_new_code_for_manual_review(self):
        root = self.wp()
        self.runner.activation_fail = True
        self.runner.deactivation_fail = True
        report = self.run_install()
        self.assertEqual(report['rollback_status'], 'manual_review_required')
        self.assertTrue(report['activated'])
        self.assertTrue((root / 'wp-content/plugins' / mod.SLUG).is_dir())

    def test_directory_named_like_config_is_not_a_wordpress_candidate(self):
        root = self.wp()
        (root / 'wp-config.php').unlink()
        (root / 'wp-config.php').mkdir()
        self.assertEqual(self.run_install()['candidate_count'], 0)

    def test_symlink_root_marker_and_plugin_path_are_not_followed(self):
        outside = self.home / 'outside'
        outside.mkdir()
        domain = self.domains / 'aptredlight.com'
        domain.mkdir()
        (domain / 'public_html').symlink_to(outside, target_is_directory=True)
        self.assertEqual(self.run_install()['reason'], 'no_wordpress_installation')
        (domain / 'public_html').unlink()
        root = self.wp()
        target = root / 'wp-content/plugins' / mod.SLUG
        target.symlink_to(outside, target_is_directory=True)
        report = self.run_install()
        self.assertEqual(report['reason'], 'existing_plugin_requires_review')
        self.assertEqual(list(outside.iterdir()), [])

    def test_depth_and_backup_directories_are_excluded(self):
        self.wp(sub='one/two/three/four/five')
        self.wp('cms.aptredlight.com', sub='backups/wordpress')
        self.assertEqual(self.run_install()['candidate_count'], 0)

    def test_scan_limit_does_not_install_a_partial_match(self):
        root = self.wp()
        for index in range(802):
            (root / ('dir' + str(index))).mkdir()
        report = self.run_install()
        self.assertEqual(report['reason'], 'scan_directory_limit')
        self.assertFalse(report['writes_performed'])

    def test_missing_woo_is_not_activated_automatically(self):
        root = self.wp()
        self.runner.sites[str(root)]['woo'] = False
        report = self.run_install()
        self.assertIn('woocommerce_not_active', report['rejected_candidate_reasons'])
        self.assertFalse(report['writes_performed'])
        self.assertFalse(any('activate' in command for command in self.runner.calls))

    def test_scan_checks_total_deadline_before_commands_or_writes(self):
        installer = mod.Installer(self.domains, self.private, self.runner, '/fixture/wp')
        installer.deadline = time.monotonic() - 1
        report = installer.run(self.data)
        self.assertEqual(report['reason'], 'total_deadline_reached')
        self.assertFalse(report['writes_performed'])
        self.assertFalse(self.runner.calls)


if __name__ == '__main__':
    unittest.main()
