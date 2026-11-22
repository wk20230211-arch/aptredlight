"""Fresh-bootstrap fixtures: temporary files and controlled backend, no network/WP."""
import base64
import copy
import hashlib
import io
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile
from unittest.mock import patch

SPEC=importlib.util.spec_from_file_location('cms_bootstrap',Path(__file__).with_name('cms_bootstrap.py'))
cms=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(cms)
PLUGIN=Path(__file__).resolve().parents[1]/'integrations/wordpress/aptredlight-growth-desk'
if not PLUGIN.is_dir():PLUGIN=Path('/workspace/apt-wordpress-admin-20261122/plugin/aptredlight-growth-desk')


class FakeBackend:
    def __init__(self):
        self.calls=[];self.encrypted_plain=[];self.fail_step=None;self.extensions={x:True for x in ('mysqli','json','openssl','fileinfo','curl','mbstring','xml','zip','gd')};self.extensions['imagick']=False
        self.auth=True;self.table_count=0;self.web_ready=True;self.lock_status=403;self.api_products=[];self.broad_media=False;self.mutate_front=None
    def php_info(self):return {'version':'8.2.29','extensions':self.extensions}
    def versions(self):return {'core':'6.9','core_php':'7.4','woo':'10.0.0','woo_php':'7.4'}
    def database_check(self,db):return {'auth_success':self.auth,'query_success':True,'mysql_only':True,'table_count':self.table_count}
    def encrypt(self,plain,pem):
        self.encrypted_plain.append(json.loads(plain))
        return {'algorithm':'RSA-OAEP-SHA256+AES-256-CBC-PBKDF2-SHA256+HMAC-SHA256','iterations':200000,'salt_length':8,'wrapped_key_b64':base64.b64encode(b'w'*384).decode(),'ciphertext_b64':base64.b64encode(b'Salted__'+b'x'*40).decode(),'hmac_sha256':'1'*64}
    def health(self,url,nonce):return {'apt_php_probe':nonce,'version':'8.2.29','extensions':self.extensions} if self.web_ready else None
    def http_status(self,url):return self.lock_status
    def download_core(self,target,version):
        self.calls.append((['core','download','--version='+version],'core_download',None))
        if self.fail_step=='core_download':raise cms.BootstrapError('core_download_failed')
        (target/'wp-content/plugins').mkdir(parents=True)
        (target/'wp-admin').mkdir()
        (target/'index.php').write_text('<?php /* fixture core */')
        return {'source':'official_https_zip','manifest_count':100,'official_checksums_verified':True}
    def wp(self,target,args,step,stdin=None,timeout=120):
        self.calls.append((args,step,stdin))
        if self.fail_step==step:raise cms.BootstrapError(step+'_failed')
        if step=='wordpress_install' and self.mutate_front:self.mutate_front.write_text('external concurrent edit')
        if step=='service_credentials':
            value={'service_user_id':2,'service_username':'apt_growth_service','service_role':'apt_growth_product_operator','service_password':'fixture-service-password','application_password':'fixture-application-password','consumer_key':'ck_fixture','consumer_secret':'cs_fixture'}
            return ('APT_CMS_CREDENTIALS_BEGIN'+json.dumps(value)+'APT_CMS_CREDENTIALS_END').encode()
        return b''
    def http_json(self,url,authorization=None):
        if '/wc/v3/products' in url:return self.api_products
        if '/users/me' in url:return {'id':2,'username':'apt_growth_service','roles':['apt_growth_product_operator'],'capabilities':{'upload_files':True,'manage_options':self.broad_media}}
        raise AssertionError('Unexpected HTTP URL')


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.home=Path(self.tmp.name);self.root=self.home/'public_html';self.root.mkdir();self.target=self.root/'cms'
        (self.root/'index.html').write_text('Original static front')
        (self.root/'.htaccess').write_text('Original root rules')
        self.private=self.home/'private';self.bundle=self.private/'staging/run';self.bundle.mkdir(parents=True)
        self.phar=self.bundle/'wp-cli.phar';self.phar.write_bytes(b'fixture phar')
        shutil.copytree(PLUGIN,self.bundle/'plugin'/cms.SLUG)
        self.receipt=self.private/'receipts/run.json';self.backend=FakeBackend()
        self.config={'database':{'name':'u469397229_fixture','user':'u469397229_fixture','password':"Fixture'\\DBPassword16",'host':'127.0.0.1'},'admin_email':'owner-fixture@example.invalid','admin_login':'fixture_owner','admin_password':'Fixture-Admin-Password-22','receipt_public_key_pem':'-----BEGIN PUBLIC KEY-----\n'+'A'*500+'\n-----END PUBLIC KEY-----'}
    def tearDown(self):self.tmp.cleanup()
    def engine(self):return cms.Bootstrap(self.bundle,self.phar,self.receipt,self.backend,self.root,self.target,self.private,hashlib.sha512(self.phar.read_bytes()).hexdigest())
    def run_it(self):return self.engine().run(self.config)
    def assert_front(self):
        self.assertEqual((self.root/'index.html').read_text(),'Original static front')
        self.assertEqual((self.root/'.htaccess').read_text(),'Original root rules')
    def assert_blocked(self,reason):
        report=self.run_it();self.assertEqual(report['status'],'blocked');self.assertEqual(report['reason'],reason);self.assertFalse(report['cms_mutations_started']);self.assertFalse(self.target.exists());self.assert_front();return report
    def test_success_is_based_on_wp_wc_and_both_actual_api_checks(self):
        report=self.run_it();self.assertEqual(report['status'],'ready')
        for field in ('wordpress_installed','woocommerce_active','brand_plugin_active','api_read_verified','media_read_verified','front_preserved'):self.assertIs(report[field],True)
        self.assertFalse(report['product_writes_performed']);self.assertEqual(report['readonly_product_test']['returned_count'],0)
        self.assertEqual((self.target/'wp-config.php').stat().st_mode&0o777,0o600)
        self.assertEqual(self.receipt.stat().st_mode&0o777,0o600)
        self.assertEqual(Path(report['secure_recovery_receipt_path']).stat().st_mode&0o777,0o600)
        self.assertIn('DirectoryIndex index.php',(self.target/'.htaccess').read_text());self.assert_front()
    def test_public_receipt_contains_no_plain_credentials(self):
        text=json.dumps(self.run_it())
        for value in [*self.config['database'].values(),self.config['admin_email'],self.config['admin_password']]:
            if value not in ('127.0.0.1',):self.assertNotIn(value,text)
        recovery=json.loads(Path(json.loads(text)['secure_recovery_receipt_path']).read_text());self.assertNotIn('database',recovery)
    def test_mysql_host_scope_rejected_before_mutation(self):
        self.config['database']['host']='remote.attacker.test';self.assert_blocked('database_host_rejected')
    def test_database_account_prefix_required(self):
        self.config['database']['user']='root';self.assert_blocked('database_account_scope_rejected')
    def test_admin_password_cannot_inject_prompt_line(self):
        self.config['admin_password']='StrongEnoughPass\nsecond';self.assert_blocked('invalid_admin_password')
    def test_database_auth_failure_never_creates_cms(self):
        self.backend.auth=False;self.assert_blocked('mysql_authentication_or_read_failed')
    def test_nonempty_database_is_never_erased(self):
        self.backend.table_count=1;self.assert_blocked('database_not_empty_requires_review');self.assertFalse(self.backend.calls)
    def test_missing_php_extension_does_not_downgrade_to_sqlite(self):
        self.backend.extensions['mysqli']=False;self.assert_blocked('required_php_extension_missing')
    def test_existing_cms_contents_are_preserved(self):
        self.target.mkdir();(self.target/'existing.php').write_text('preserve me')
        report=self.run_it();self.assertEqual(report['reason'],'existing_or_partial_cms_requires_review');self.assertFalse(report['cms_mutations_started']);self.assertEqual((self.target/'existing.php').read_text(),'preserve me')
    def test_target_symlink_is_rejected(self):
        elsewhere=self.home/'elsewhere';elsewhere.mkdir();self.target.symlink_to(elsewhere,target_is_directory=True)
        report=self.run_it();self.assertEqual(report['reason'],'cms_target_scope_rejected');self.assertEqual(list(elsewhere.iterdir()),[])
    def test_extra_unreviewed_plugin_file_is_rejected(self):
        (self.bundle/'plugin'/cms.SLUG/'evil.php').write_text('<?php evil();');self.assert_blocked('reviewed_plugin_integrity_failed')
    def test_wp_cli_hash_cannot_be_supplied_by_payload(self):
        engine=cms.Bootstrap(self.bundle,self.phar,self.receipt,self.backend,self.root,self.target,self.private)
        report=engine.run(self.config);self.assertEqual(report['reason'],'wp_cli_integrity_failed');self.assertFalse(self.target.exists())
    def test_failed_web_php_never_places_database_password_in_webroot(self):
        self.backend.web_ready=False;report=self.run_it();self.assertEqual(report['reason'],'web_php_not_ready')
        self.assertFalse((self.target/'wp-config.php').exists());self.assertIn('Require all denied',(self.target/'.htaccess').read_text());self.assertFalse(self.backend.calls)
    def test_unenforced_maintenance_gate_stops_before_core_or_secrets(self):
        self.backend.lock_status=200;report=self.run_it();self.assertEqual(report['reason'],'maintenance_lock_not_enforced');self.assertFalse((self.target/'wp-config.php').exists());self.assertFalse(self.backend.calls)
    def test_core_install_failure_retains_closed_partial_state(self):
        self.backend.fail_step='wordpress_install';report=self.run_it();self.assertEqual(report['status'],'failed');self.assertTrue(report['manual_review_required']);self.assertEqual(report['maintenance_lock'],'closed_after_failure');self.assertTrue((self.target/'wp-config.php').exists());self.assert_front()
    def test_credential_passwords_are_not_cli_arguments(self):
        self.run_it()
        commands=json.dumps([args for args,_,_ in self.backend.calls])
        self.assertNotIn(self.config['admin_password'],commands);self.assertNotIn(self.config['database']['password'],commands)
        install=next(call for call in self.backend.calls if call[1]=='wordpress_install');self.assertIn('--prompt=admin_password',install[0]);self.assertEqual(install[2],(self.config['admin_password']+'\n').encode())
        code=(self.target/'wp-config.php').read_text();self.assertIn(cms.php_string(self.config['database']['password']),code)
    def test_media_broad_role_fails_and_closes_cms(self):
        self.backend.broad_media=True;report=self.run_it();self.assertEqual(report['reason'],'media_capability_verification_failed');self.assertFalse(report['media_read_verified']);self.assertEqual(report['maintenance_lock'],'closed_after_failure')
    def test_bad_wc_json_is_not_an_empty_product_list(self):
        self.backend.api_products={'error':'not an array'};report=self.run_it();self.assertEqual(report['reason'],'woocommerce_readonly_verification_failed');self.assertFalse(report['api_read_verified']);self.assertEqual(report['maintenance_lock'],'closed_after_failure')
    def test_all_plugin_files_are_web_readable_without_exposing_config(self):
        self.run_it();plugin=self.target/'wp-content/plugins'/cms.SLUG
        self.assertEqual((plugin/'assets/admin.js').stat().st_mode&0o777,0o644);self.assertEqual((plugin/'assets').stat().st_mode&0o777,0o755)
    def test_front_change_is_not_reverted_or_called_ready(self):
        self.backend.mutate_front=self.root/'index.html';report=self.run_it();self.assertEqual(report['reason'],'frontend_changed_during_setup');self.assertFalse(report['front_preserved']);self.assertEqual(report['maintenance_lock'],'closed_after_failure');self.assertEqual((self.root/'index.html').read_text(),'external concurrent edit')
    def test_receipt_failure_after_success_recloses_cms(self):
        original=cms.atomic_private_json
        def write(path,value):
            if path==self.receipt:raise OSError('fixture failure')
            return original(path,value)
        with patch.object(cms,'atomic_private_json',write):report=self.run_it()
        self.assertEqual(report['reason'],'secure_receipt_write_failed');self.assertEqual(report['maintenance_lock'],'closed_after_failure')


class CoreZipTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.target=Path(self.tmp.name)/'cms';self.target.mkdir()
        (self.target/'.htaccess').write_text(cms.maintenance_htaccess())
        self.files={'wp-includes/fixture-%03d.php'%i:b'<?php /* fixture */' for i in range(100)}
        self.long='wp-includes/php-ai-client/src/Providers/Contracts/ProviderWithOperationsHandlerInterface.php'
        self.files[self.long]=b'<?php interface CompleteName {}'
        self.files['wp-content/themes/example/fonts/Inter-VariableFont_slnt,wght.ttf']=b'fixturefont'
        self.files['wp-content/plugins/example/logo@2x.png']=b'fixtureimage'
    def tearDown(self):self.tmp.cleanup()
    def manifest(self):return {name:hashlib.md5(value).hexdigest() for name,value in self.files.items()}
    def archive(self,extras=None,override=None):
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            for name,value in self.files.items():archive.writestr('wordpress/'+name,(override or {}).get(name,value))
            for name,value in (extras or {}).items():archive.writestr(name,value)
        return buffer.getvalue()
    def test_preserves_long_full_paths_and_scoped_punctuation(self):
        report=cms.extract_core_archive(self.target,self.archive(),self.manifest())
        self.assertTrue(report['official_checksums_verified']);self.assertEqual((self.target/self.long).read_bytes(),self.files[self.long])
        self.assertFalse((self.target/self.long[:-2]).exists());self.assertIn('Require all denied',(self.target/'.htaccess').read_text())
    def test_path_traversal_is_rejected_before_extraction(self):
        with self.assertRaisesRegex(cms.BootstrapError,'core_archive_path_invalid'):cms.extract_core_archive(self.target,self.archive({'wordpress/../../outside':b'evil'}),self.manifest())
        self.assertEqual([p.name for p in self.target.iterdir()],['.htaccess']);self.assertFalse((self.target.parent/'outside').exists())
    def test_absolute_or_backslash_or_control_paths_rejected(self):
        for value in ('/etc/passwd','a/../b','a\\b','a//b','a\x00b','a\nb'):
            with self.subTest(value=value),self.assertRaises(cms.BootstrapError):cms.core_relative_path(value)
    def test_corrupt_file_fails_official_checksum(self):
        with self.assertRaisesRegex(cms.BootstrapError,'core_official_checksum_mismatch'):cms.extract_core_archive(self.target,self.archive(override={self.long:b'wrong'}),self.manifest())
        self.assertFalse((self.target/'wp-config.php').exists())
    def test_missing_manifest_file_fails_integrity(self):
        manifest=self.manifest();manifest['wp-includes/missing.php']='0'*32
        with self.assertRaisesRegex(cms.BootstrapError,'core_official_checksum_missing_file'):cms.extract_core_archive(self.target,self.archive(),manifest)
    def test_symlink_member_rejected_before_any_extraction(self):
        buffer=io.BytesIO(self.archive())
        with zipfile.ZipFile(buffer,'a') as archive:
            link=zipfile.ZipInfo('wordpress/wp-includes/evil');link.create_system=3;link.external_attr=0o120777<<16;archive.writestr(link,'/etc/passwd')
        with self.assertRaisesRegex(cms.BootstrapError,'core_archive_entry_invalid'):cms.extract_core_archive(self.target,buffer.getvalue(),self.manifest())
        self.assertEqual(len(list(self.target.iterdir())),1)
    def test_archive_cannot_replace_maintenance_or_create_config(self):
        for name in ('.htaccess','wp-config.php'):
            with self.subTest(name=name),self.assertRaisesRegex(cms.BootstrapError,'core_archive_protected_file'):cms.extract_core_archive(self.target,self.archive({'wordpress/'+name:b'evil'}),self.manifest())
        self.assertEqual(len(list(self.target.iterdir())),1)
    def test_non_official_zip_root_rejected(self):
        with self.assertRaisesRegex(cms.BootstrapError,'core_archive_root_invalid'):cms.extract_core_archive(self.target,self.archive({'other/index.php':b'evil'}),self.manifest())
    def test_existing_core_is_never_overwritten(self):
        path=self.target/'wp-includes/fixture-000.php';path.parent.mkdir();path.write_bytes(b'existing')
        with self.assertRaisesRegex(cms.BootstrapError,'core_archive_existing_path'):cms.extract_core_archive(self.target,self.archive(),self.manifest())
        self.assertEqual(path.read_bytes(),b'existing')


if __name__=='__main__':unittest.main()
