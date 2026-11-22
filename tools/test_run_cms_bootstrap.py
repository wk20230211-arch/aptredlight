#!/usr/bin/env python3
"""Fixtures only: no SSH, database authentication or installation is performed."""
import base64
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest import mock

MODULE = Path(__file__).with_name("run_cms_bootstrap.py")
spec = importlib.util.spec_from_file_location("run_cms_bootstrap", MODULE)
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class RunnerGuards(unittest.TestCase):
    def invoke_mock_remote(self, *, upload_error=None, child_error=None, exit_code=0):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'bootstrap.py';source.write_text('#fixture')
            receipt=root/'receipt.json'
            ready={"status":"ready","cms_url":"https://www.aptredlight.com/cms","wordpress_installed":True,
                   "woocommerce_active":True,"brand_plugin_active":True,"api_read_verified":True}
            argv=['--source',str(source),'--plugin',str(root),'--public-key',str(root/'key'),
                  '--known-hosts',str(root/'known-hosts'),'--receipt',str(receipt)]
            with contextlib.ExitStack() as stack:
                stack.enter_context(mock.patch.dict(os.environ,{'APTREDLIGHT_CMS_DATABASE':json.dumps(self.config())}))
                stack.enter_context(mock.patch.object(setup,'receipt_public_key',return_value='fixture-public-key'))
                stack.enter_context(mock.patch.object(setup,'ssh_arguments',return_value=['fixture-ssh']))
                stack.enter_context(mock.patch.object(setup,'paths_for_run',return_value=('/private/stage','/private/receipt.json')))
                stack.enter_context(mock.patch.object(setup,'download_wp_cli',return_value=b'fixture'))
                stack.enter_context(mock.patch.object(setup,'bundle',return_value=b'fixture'))
                stack.enter_context(mock.patch.object(setup,'upload_bundle',side_effect=upload_error))
                stack.enter_context(mock.patch.object(setup,'child',side_effect=child_error,return_value=subprocess.CompletedProcess([],exit_code,b'fixture',b'')))
                stack.enter_context(mock.patch.object(setup,'safe_receipt',return_value=ready))
                stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                code=setup.main(argv)
            return code,json.loads(receipt.read_text())

    def config(self, **changes):
        value = {"name":"u469397229_aptcms", "user":"u469397229_aptcms", "password":"Fixture-only-1234!", "host":"localhost", "admin_email":"owner@example.test"}
        value.update(changes)
        return value

    def test_valid_database_secret(self):
        value = self.config()
        self.assertEqual(setup.database_secret(json.dumps(value)), value)

    def test_local_default_port_normalized_and_identifier_length_bounded(self):
        self.assertEqual(setup.database_secret(json.dumps(self.config(host="localhost:3306")))["host"], "localhost")
        value = "u469397229_" + "a" * 53
        self.assertEqual(len(value), 64)
        self.assertEqual(setup.database_secret(json.dumps(self.config(name=value)))["name"], value)
        with self.assertRaises(setup.SetupError):
            setup.database_secret(json.dumps(self.config(name=value+"a")))

    def test_scope_host_fields_and_controls_refused(self):
        candidates = [self.config(name="other_db"), self.config(user="root"), self.config(host="remote.example"),
                      self.config(password="short"), self.config(password="bad\npassword-123456"),
                      self.config(admin_email="unsafe\n@example.test"), self.config(extra="field")]
        for value in candidates:
            with self.subTest(value=list(value)), self.assertRaises(setup.SetupError):
                setup.database_secret(json.dumps(value))

    def test_duplicate_json_field_refused(self):
        value = json.dumps(self.config())[:-1] + ',"host":"localhost"}'
        with self.assertRaises(setup.SetupError):
            setup.database_secret(value)

    def test_missing_secret_stops_before_ssh_or_network(self):
        with tempfile.TemporaryDirectory() as folder:
            receipt = Path(folder, "receipt.json")
            argv = ["--source", "not-needed", "--plugin", "not-needed", "--public-key", "not-needed", "--known-hosts", "not-needed", "--receipt", str(receipt)]
            with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(setup,"child") as child, mock.patch.object(setup,"download_wp_cli") as download, contextlib.redirect_stdout(io.StringIO()) as output:
                result = setup.main(argv)
            self.assertEqual(result, 1)
            self.assertEqual(json.loads(receipt.read_text())["status"], "needs_setup")
            self.assertFalse(child.called)
            self.assertFalse(download.called)
            self.assertEqual(json.loads(output.getvalue())["reason"], "database_secret_missing")

    def test_environment_secrets_removed_for_subprocesses(self):
        with mock.patch.dict(os.environ, {"APTREDLIGHT_CMS_DATABASE":"secret-json", "HOSTINGER_SSH_PRIVATE_KEY":"secret-key", "MYSQL_PWD":"secret-pw", "SSH_AUTH_SOCK":"public-path"}):
            child_env = setup.clean_environment()
        self.assertNotIn("APTREDLIGHT_CMS_DATABASE", child_env)
        self.assertNotIn("HOSTINGER_SSH_PRIVATE_KEY", child_env)
        self.assertNotIn("MYSQL_PWD", child_env)
        self.assertEqual(child_env["SSH_AUTH_SOCK"], "public-path")

    def test_remote_timeout_preserves_unknown_cms_state(self):
        code,report=self.invoke_mock_remote(child_error=setup.SetupError('child_timeout'))
        self.assertEqual(code,1);self.assertEqual(report['status'],'unknown')
        self.assertIsNone(report['wordpress_installed']);self.assertIsNone(report['woocommerce_active'])

    def test_nonzero_ssh_cannot_leave_ready_receipt(self):
        code,report=self.invoke_mock_remote(exit_code=1)
        self.assertEqual(code,1);self.assertEqual(report['status'],'unknown')
        self.assertEqual(report['reason'],'ssh_exit_contradicts_ready_receipt')

    def test_failed_staging_does_not_claim_zero_private_writes(self):
        code,report=self.invoke_mock_remote(upload_error=setup.SetupError('private_staging_not_confirmed'))
        self.assertEqual(code,1);self.assertEqual(report['status'],'blocked')
        self.assertEqual(report['writes_performed'],'unknown')
        self.assertIs(report['cms_mutations_started'],False)

    def test_public_key_exact_owner_pin(self):
        key = Path(__file__).with_name("cms-receipt-public-key.pem")
        if not key.exists():
            key = Path(__file__).resolve().parents[1] / ".hostinger/cms-receipt-public-key.pem"
        self.assertTrue(key.exists())
        self.assertIn("BEGIN PUBLIC KEY", setup.receipt_public_key(key))
        with tempfile.TemporaryDirectory() as folder:
            wrong = Path(folder,"wrong.pem")
            private = subprocess.run(["openssl","genpkey","-algorithm","RSA","-pkeyopt","rsa_keygen_bits:2048"],capture_output=True,check=True).stdout
            public = subprocess.run(["openssl","pkey","-pubout"],input=private,capture_output=True,check=True).stdout
            wrong.write_bytes(public)
            with self.assertRaises(setup.SetupError):setup.receipt_public_key(wrong)

    def test_private_key_never_accepted_as_recipient(self):
        with tempfile.TemporaryDirectory() as folder:
            key = Path(folder,"private.pem"); key.write_text("-----BEGIN PRIVATE KEY-----\nfixture\n")
            with self.assertRaises(setup.SetupError):setup.receipt_public_key(key)

    def test_remote_receipt_never_accepts_raw_secrets(self):
        with self.assertRaises(setup.SetupError):
            setup.safe_receipt(b'{"status":"failed","reason":"Fixture-only-1234!"}', ["Fixture-only-1234!"])
        with self.assertRaises(setup.SetupError):setup.safe_receipt(b'{"status":"ready","credentials":{}}', [])
        with self.assertRaises(setup.SetupError):setup.safe_receipt(b'PHP fatal error, private contents', [])

    def test_ready_receipt_requires_actual_proof_and_encrypted_credentials(self):
        value={"status":"ready","cms_url":"https://www.aptredlight.com/cms"}
        with self.assertRaises(setup.SetupError):setup.safe_receipt(json.dumps(value).encode(),[])
        for name in ("wordpress_installed","woocommerce_active","brand_plugin_active","api_read_verified","media_read_verified","front_preserved"):
            value[name]=True
        value['maintenance_lock']='released'
        with self.assertRaises(setup.SetupError):setup.safe_receipt(json.dumps(value).encode(),[])
        value['encrypted_credentials']={
            'algorithm':'RSA-OAEP-SHA256+AES-256-CBC-PBKDF2-SHA256+HMAC-SHA256',
            'iterations':200000,'salt_length':8,'wrapped_key_b64':base64.b64encode(b'x'*384).decode(),
            'ciphertext_b64':base64.b64encode(b'Salted__'+b'x'*24).decode(),'hmac_sha256':'a'*64}
        self.assertEqual(setup.safe_receipt(json.dumps(value).encode(),[])['status'],'ready')
        value['api_read_verified']='true'
        with self.assertRaises(setup.SetupError):setup.safe_receipt(json.dumps(value).encode(),[])

    def test_wrong_target_or_unknown_status_is_rejected(self):
        for status,url in [('mystery','https://www.aptredlight.com/cms'),('blocked','https://other.example/cms')]:
            with self.assertRaises(setup.SetupError):setup.safe_receipt(json.dumps({'status':status,'cms_url':url}).encode(),[])

    def test_remote_upload_only_fixed_source_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); source=root/"bootstrap.py"; source.write_text("# fixture only\n")
            plugin=root/"plugin"
            for name in setup.PLUGIN_FILES:
                p=plugin/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text("fixture")
            packed=setup.bundle(source,plugin,b"fixture-phar")
            with tarfile.open(fileobj=io.BytesIO(packed)) as archive:
                self.assertEqual(len(archive.getmembers()),7)
                self.assertTrue(all(member.isfile() and member.mode==0o600 for member in archive.getmembers()))
                self.assertNotIn(".env",archive.getnames())

    def test_upload_rejects_symlinked_plugin(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/"bootstrap.py";source.write_text("fixture")
            plugin=root/"plugin";plugin.mkdir();(plugin/setup.PLUGIN_FILES[0]).symlink_to(source)
            with self.assertRaises(setup.SetupError):setup.bundle(source,plugin,b"fixture")

    def test_run_id_path_cannot_escape_private_root(self):
        with mock.patch.dict(os.environ,{"GITHUB_RUN_ID":"450001","GITHUB_RUN_ATTEMPT":"2"}):
            stage,receipt=setup.paths_for_run()
            self.assertTrue(stage.startswith(setup.PRIVATE_ROOT+"/staging/"))
            self.assertTrue(receipt.startswith(setup.PRIVATE_ROOT+"/receipts/"))
        with mock.patch.dict(os.environ,{"GITHUB_RUN_ID":"../../other","GITHUB_RUN_ATTEMPT":"2"}):
            with self.assertRaises(setup.SetupError):setup.paths_for_run()

    def test_unverified_phar_is_refused(self):
        response = mock.MagicMock();response.status=200;response.geturl.return_value=setup.WP_CLI_URL;response.read.return_value=b"modified PHAR"
        context=mock.MagicMock();context.__enter__.return_value=response
        with mock.patch.object(setup.urllib.request,"urlopen",return_value=context):
            with self.assertRaises(setup.SetupError):setup.download_wp_cli()

    def test_public_ui_has_no_data_transport_or_storage(self):
        path=Path(__file__).with_name("cms-database-secret.html")
        if not path.exists():
            self.skipTest("Standalone UI is published with the private workbench, not the controller tools")
        html=path.read_text()
        self.assertIn("connect-src 'none'",html)
        self.assertIn("form-action 'none'",html)
        self.assertNotIn("localStorage",html)
        self.assertNotIn("fetch(",html)
        self.assertIn("JSON.stringify(fields)",html)
        self.assertIn("event.preventDefault()",html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
