#!/usr/bin/env python3
"""Synthetic owner-handoff boundary tests. No production SSH or WordPress calls."""
import base64
import datetime
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import hashlib
import unittest
from unittest import mock

spec=importlib.util.spec_from_file_location('final_owner_setup',Path(__file__).with_name('final_owner_setup.py'))
owner=importlib.util.module_from_spec(spec);spec.loader.exec_module(owner)


def payload():
    issued=datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    return {'schema':1,'cms_url':owner.URL,'admin_login':'aptredlight_admin','issued_at':issued.isoformat(),
            'expires_at':(issued+datetime.timedelta(days=1)).isoformat(),
            'setup_url':owner.URL+'/wp-login.php?action=rp&key='+'a'*20+'&login=aptredlight_admin'}


def envelope():
    return {'algorithm':'RSA-OAEP-SHA256+AES-256-CBC-PBKDF2-SHA256+HMAC-SHA256','iterations':200000,'salt_length':8,
            'wrapped_key_b64':base64.b64encode(b'a'*384).decode(),'ciphertext_b64':base64.b64encode(b'Salted__'+b'a'*24).decode(),'hmac_sha256':'a'*64}


class FakeBackend:
    def __init__(self,proof=None,encryption_failure=False):
        self.proof={'site_target_verified':True,'admin_role_verified':True,'woocommerce_active':True,'brand_plugin_active':True}
        if proof:self.proof.update(proof)
        self.wp_calls=[];self.encrypt_calls=[];self.encryption_failure=encryption_failure
    def wp(self,target,args,step):
        self.wp_calls.append(args[1])
        value=self.proof if args[1]==owner.READONLY_PHP else payload()
        return (owner.BEGIN+json.dumps(value)+owner.END).encode()
    def command(self,*args):return b'fixture-public-der'
    def encrypt(self,value,pem):
        self.encrypt_calls.append(value)
        if self.encryption_failure:raise owner.OwnerSetupError('fixture_encryption_failed')
        return envelope()


class OwnerBoundary(unittest.TestCase):
    def perform(self,backend):
        import hashlib
        with mock.patch.object(owner,'RECIPIENT_SHA256',hashlib.sha256(b'fixture-public-der').hexdigest()):
            return owner.perform(backend,'fixture-public-pem')

    def test_success_contains_only_encrypted_native_setup_and_public_proof(self):
        backend=FakeBackend();report=self.perform(backend)
        self.assertEqual(report['status'],'ready');self.assertIs(report['native_password_changed'],False)
        self.assertEqual(len(backend.encrypt_calls),2)
        self.assertNotIn('action=rp',json.dumps(report));self.assertNotIn('setup_url',report)
        self.assertIn('setup_url',json.loads(backend.encrypt_calls[1]))
        self.assertEqual(owner.validate_public_receipt(report),report)

    def test_wrong_site_admin_or_plugin_stops_before_mutation(self):
        for key in ('site_target_verified','admin_role_verified','woocommerce_active','brand_plugin_active'):
            backend=FakeBackend({key:False})
            with self.subTest(key=key),self.assertRaises(owner.OwnerSetupError):self.perform(backend)
            self.assertEqual(backend.wp_calls,[owner.READONLY_PHP]);self.assertEqual(backend.encrypt_calls,[])

    def test_encryption_preflight_precedes_native_token_creation(self):
        backend=FakeBackend(encryption_failure=True)
        with self.assertRaises(owner.OwnerSetupError):self.perform(backend)
        self.assertEqual(backend.wp_calls,[owner.READONLY_PHP])

    def test_wrong_recipient_pin_stops_before_native_token_creation(self):
        backend=FakeBackend()
        with self.assertRaises(owner.OwnerSetupError):owner.perform(backend,'fixture-public-pem')
        self.assertEqual(backend.wp_calls,[owner.READONLY_PHP]);self.assertEqual(backend.encrypt_calls,[])

    def test_native_url_origin_login_and_expiry_are_strict(self):
        for key,value in [('cms_url','https://other.example/cms'),('admin_login','other_admin'),
                          ('setup_url','https://other.example/reset'),('expires_at','2000-01-01T00:00:00+00:00')]:
            item=payload();item[key]=value
            with self.subTest(key=key),self.assertRaises(owner.OwnerSetupError):owner.validate_payload(item)

    def test_ready_requires_actual_proof_and_encryption(self):
        report=self.perform(FakeBackend());report.pop('encrypted_admin_setup')
        with self.assertRaises(owner.OwnerSetupError):owner.validate_public_receipt(report)
        report=self.perform(FakeBackend());report['native_password_changed']=True
        with self.assertRaises(owner.OwnerSetupError):owner.validate_public_receipt(report)

    def test_raw_setup_url_is_rejected_from_public_receipt(self):
        report=self.perform(FakeBackend());report['setup_url']=payload()['setup_url']
        with self.assertRaises(owner.OwnerSetupError):owner.validate_public_receipt(report)

    def test_php_uses_native_key_generation_without_password_or_mail_calls(self):
        self.assertIn('get_password_reset_key($o)',owner.WRITE_PHP)
        self.assertIn("apply_filters('password_reset_expiration',DAY_IN_SECONDS)",owner.WRITE_PHP)
        self.assertNotIn('wp_set_password',owner.WRITE_PHP)
        self.assertNotIn('wp_update_user',owner.WRITE_PHP)
        self.assertNotIn('wp_mail',owner.WRITE_PHP)
        self.assertNotIn('user_email',owner.WRITE_PHP)


class MediaBackend:
    php='fixture-php'
    def __init__(self,verified=True):self.verified=verified;self.calls=[];self.concurrent=None
    def command(self,*args):self.calls.append('syntax');return b'fixture syntax passed'
    def wp(self,target,args,step):
        self.calls.append(step)
        if args[0]=='eval':
            if self.concurrent:self.concurrent()
            proof={name:self.verified for name in ('service_role_scoped','existing_media_owned','own_media_edit_allowed','article_permissions_unchanged','own_media_delete_denied','plugin_active')}
            return (owner.BEGIN+json.dumps(proof)+owner.END).encode()
        return b''


class PluginDeployment(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.task=self.root/'private';self.task.mkdir(mode=0o700)
        self.target=self.root/'plugin.php';self.target.write_bytes(b'old-reviewed');self.target.chmod(0o644)
        self.new=b'new-reviewed'
        self.old_patch=mock.patch.object(owner,'PLUGIN_OLD_SHA256',hashlib.sha256(b'old-reviewed').hexdigest());self.old_patch.start()
        self.new_patch=mock.patch.object(owner,'PLUGIN_NEW_SHA256',hashlib.sha256(self.new).hexdigest());self.new_patch.start()
    def tearDown(self):self.new_patch.stop();self.old_patch.stop();self.tmp.cleanup()
    def test_only_exact_file_replaced_with_private_backup_and_proof(self):
        report=owner.deploy_media_cap_fix(MediaBackend(),self.new,self.task,self.target)
        self.assertEqual(report['status'],'applied');self.assertEqual(self.target.read_bytes(),self.new)
        backup=Path(report['private_backup_path']);self.assertEqual(backup.read_bytes(),b'old-reviewed')
        self.assertEqual(backup.stat().st_mode&0o777,0o600)
    def test_failed_native_proof_restores_original_and_rechecks_activation(self):
        backend=MediaBackend(False)
        with self.assertRaisesRegex(owner.OwnerSetupError,'original_restored'):
            owner.deploy_media_cap_fix(backend,self.new,self.task,self.target)
        self.assertEqual(self.target.read_bytes(),b'old-reviewed')
        self.assertIn('media_fix_restore_active',backend.calls)
    def test_unknown_existing_source_is_never_overwritten(self):
        self.target.write_bytes(b'unreviewed-current')
        with self.assertRaisesRegex(owner.OwnerSetupError,'existing_file_unreviewed'):
            owner.deploy_media_cap_fix(MediaBackend(),self.new,self.task,self.target)
        self.assertEqual(self.target.read_bytes(),b'unreviewed-current');self.assertEqual(list(self.task.iterdir()),[])
    def test_already_current_is_idempotent_without_backup(self):
        self.target.write_bytes(self.new)
        report=owner.deploy_media_cap_fix(MediaBackend(),self.new,self.task,self.target)
        self.assertEqual(report['status'],'already_current');self.assertEqual(list(self.task.iterdir()),[])
    def test_concurrent_edit_is_preserved_when_restore_is_not_safe(self):
        backend=MediaBackend(False);backend.concurrent=lambda:self.target.write_bytes(b'concurrent-editor')
        with self.assertRaisesRegex(owner.OwnerSetupError,'rollback_unconfirmed'):
            owner.deploy_media_cap_fix(backend,self.new,self.task,self.target)
        self.assertEqual(self.target.read_bytes(),b'concurrent-editor')


if __name__=='__main__':unittest.main(verbosity=2)
