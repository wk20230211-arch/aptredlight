#!/usr/bin/env python3
"""Runner-side fixed-target CMS setup. Credentials travel only over SSH stdin.

No database secret or installation password is written to an artifact or command
argument. The remote bootstrap emits a public receipt with an encrypted envelope.
"""
from __future__ import annotations

import argparse
import base64
import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import subprocess
import sys
import tarfile
import urllib.request

ACCOUNT = "u469397229"
PRIVATE_ROOT = "/home/u469397229/.aptredlight-cms-bootstrap"
WP_CLI_COMMIT = "539d8d569755990b06fa2969a43fb039e5762e2b"
WP_CLI_URL = "https://raw.githubusercontent.com/wp-cli/builds/" + WP_CLI_COMMIT + "/phar/wp-cli.phar"
WP_CLI_SHA512 = "be928f6b8ca1e8dfb9d2f4b75a13aa4aee0896f8a9a0a1c45cd5d2c98605e6172e6d014dda2e27f88c98befc16c040cbb2bd1bfa121510ea5cdf5f6a30fe8832"
RECEIPT_PUBLIC_KEY_SHA256 = "0654fd6d0f48cbd27da86b82ffc348f7ff2dd3c4ce483ba335017ac3140d0721"
SECRET_ENV = "APTREDLIGHT_CMS_DATABASE"
PLUGIN_FILES = ("aptredlight-growth-desk.php", "assets/admin.js", "assets/admin.css", "readme.txt", "README.zh-CN.txt")


class SetupError(Exception):
    """Only bounded public failure codes are allowed in exceptions."""


def require(condition, code):
    if not condition:
        raise SetupError(code)


def clean_environment():
    env = os.environ.copy()
    env.pop(SECRET_ENV, None)
    env.pop("HOSTINGER_SSH_PRIVATE_KEY", None)
    env.pop("MYSQL_PWD", None)
    return env


def child(args, *, data=None, timeout=30):
    try:
        result = subprocess.run(args, input=data, capture_output=True, timeout=timeout,
                                env=clean_environment(), check=False)
    except subprocess.TimeoutExpired:
        raise SetupError("child_timeout") from None
    except OSError:
        raise SetupError("child_unavailable") from None
    require(len(result.stdout) <= 2 * 1024 * 1024 and len(result.stderr) <= 256 * 1024,
            "child_output_limit")
    return result


def database_secret(raw):
    require(isinstance(raw, str) and 0 < len(raw.encode("utf-8")) <= 16384, "database_secret_invalid")
    try:
        def pairs(items):
            output = {}
            for key, value in items:
                require(key not in output, "database_secret_duplicate_field")
                output[key] = value
            return output
        value = json.loads(raw, object_pairs_hook=pairs)
    except (ValueError, UnicodeError):
        raise SetupError("database_secret_not_json") from None
    require(isinstance(value, dict) and set(value) == {"name", "user", "password", "host", "admin_email"},
            "database_secret_fields_invalid")
    for key in ("name", "user"):
        require(isinstance(value[key], str) and len(value[key]) <= 64 and re.fullmatch(ACCOUNT + r"_[A-Za-z0-9_]{1,53}", value[key]),
                "database_account_scope_invalid")
    require(value["host"] in ("localhost", "127.0.0.1", "localhost:3306", "127.0.0.1:3306"),
            "database_host_outside_local_scope")
    if value["host"].endswith(":3306"):
        value["host"] = value["host"][:-5]
    require(isinstance(value["password"], str) and 12 <= len(value["password"]) <= 256
            and not any(ord(c) < 32 or ord(c) == 127 for c in value["password"]), "database_password_invalid")
    email = value["admin_email"]
    require(isinstance(email, str) and len(email) <= 254
            and re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?", email)
            and ".." not in email and "." in email.rsplit("@", 1)[-1], "admin_email_invalid")
    return value


def receipt_public_key(path):
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 8192,
            "receipt_public_key_missing")
    data = path.read_bytes()
    require(b"-----BEGIN PUBLIC KEY-----" in data and b"PRIVATE" not in data,
            "receipt_key_must_be_public")
    parsed = child(["openssl", "pkey", "-pubin", "-outform", "DER"], data=data)
    require(parsed.returncode == 0 and hashlib.sha256(parsed.stdout).hexdigest() == RECEIPT_PUBLIC_KEY_SHA256,
            "receipt_public_key_pin_mismatch")
    return data.decode("ascii")


def download_wp_cli():
    try:
        request = urllib.request.Request(WP_CLI_URL, headers={"User-Agent": "APTREDLIGHT-CMS-Setup"})
        with urllib.request.urlopen(request, timeout=60) as response:
            require(response.status == 200 and response.geturl() == WP_CLI_URL, "wp_cli_download_redirected")
            body = response.read(32 * 1024 * 1024 + 1)
    except SetupError:
        raise
    except Exception:
        raise SetupError("wp_cli_download_failed") from None
    require(len(body) <= 32 * 1024 * 1024
            and hashlib.sha512(body).hexdigest() == WP_CLI_SHA512, "wp_cli_checksum_mismatch")
    return body


def bundle(source, plugin, phar):
    buffer = io.BytesIO()
    files = [("cms_bootstrap.py", source.read_bytes()), ("wp-cli.phar", phar)]
    for name in PLUGIN_FILES:
        path = plugin / name
        require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 2 * 1024 * 1024,
                "brand_plugin_file_invalid")
        files.append(("plugin/aptredlight-growth-desk/" + name, path.read_bytes()))
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for name, data in files:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o600
            info.mtime = 0
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def ssh_arguments(known_hosts):
    host = os.environ.get("CMS_SSH_HOST", "")
    port = os.environ.get("CMS_SSH_PORT", "")
    require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]{0,252}", host) and port.isdigit()
            and 1 <= int(port) <= 65535 and known_hosts.is_file(), "verified_ssh_target_missing")
    return ["ssh", "-F", "/dev/null", "-T", "-p", port,
            "-o", "BatchMode=yes", "-o", "NumberOfPasswordPrompts=0", "-o", "ConnectTimeout=15",
            "-o", "ServerAliveInterval=10", "-o", "ServerAliveCountMax=3",
            "-o", "StrictHostKeyChecking=yes", "-o", "UserKnownHostsFile=" + str(known_hosts.resolve()),
            "-o", "ForwardAgent=no", "-o", "ClearAllForwardings=yes", "-o", "PermitLocalCommand=no",
            "-o", "UpdateHostKeys=no", "-o", "LogLevel=ERROR", ACCOUNT + "@" + host]


def paths_for_run():
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
    require(re.fullmatch(r"[1-9][0-9]{0,19}", run_id) and re.fullmatch(r"[1-9][0-9]{0,5}", attempt),
            "github_run_identity_invalid")
    name = "run-" + run_id + "-" + attempt
    return PRIVATE_ROOT + "/staging/" + name, PRIVATE_ROOT + "/receipts/" + name + ".json"


def upload_bundle(ssh, stage, archive):
    # Only first-party source and the pinned PHAR are staged. No credentials are
    # in this tar stream. Exclusive files and no symlink ancestors are required.
    remote = """import io,os,pathlib,sys,tarfile
base=pathlib.Path('/home/u469397229/.aptredlight-cms-bootstrap')
stage=pathlib.Path(STAGE)
assert os.getuid()==pathlib.Path('/home/u469397229').stat().st_uid
assert not any(p.is_symlink() for p in (base,*base.parents))
base.mkdir(mode=0o700,exist_ok=True)
assert base.is_dir() and base.stat().st_uid==os.getuid()
os.chmod(base,0o700)
for part in (base/'staging',base/'receipts'):
 assert not part.is_symlink()
 part.mkdir(mode=0o700,exist_ok=True)
 assert part.is_dir() and part.stat().st_uid==os.getuid()
 os.chmod(part,0o700)
stage.mkdir(mode=0o700)
data=sys.stdin.buffer.read(40*1024*1024+1)
assert len(data)<=40*1024*1024
allowed={'cms_bootstrap.py','wp-cli.phar','plugin/aptredlight-growth-desk/aptredlight-growth-desk.php','plugin/aptredlight-growth-desk/assets/admin.js','plugin/aptredlight-growth-desk/assets/admin.css','plugin/aptredlight-growth-desk/readme.txt','plugin/aptredlight-growth-desk/README.zh-CN.txt'}
with tarfile.open(fileobj=io.BytesIO(data),mode='r:') as tar:
 members=tar.getmembers()
 assert len(members)==len(allowed) and {m.name for m in members}==allowed
 for member in members:
  assert member.isfile() and 0<=member.size<=32*1024*1024
 for member in members:
  target=stage/member.name
  target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
  with target.open('xb') as out:
   os.chmod(target,0o600)
   out.write(tar.extractfile(member).read())
print('staged')
""".replace("STAGE", repr(stage))
    result = child(ssh + ["python3 -c " + shlex.quote(remote)], data=archive, timeout=120)
    require(result.returncode == 0 and result.stdout.strip() == b"staged", "private_staging_not_confirmed")


def safe_receipt(raw, sensitive):
    require(len(raw) <= 1024 * 1024, "remote_receipt_too_large")
    require(all(value.encode("utf-8") not in raw for value in sensitive if value),
            "remote_receipt_redaction_failed")
    try:
        receipt = json.loads(raw)
    except (UnicodeError, ValueError):
        raise SetupError("remote_receipt_not_json") from None
    require(isinstance(receipt, dict) and receipt.get("status") in ("ready", "blocked", "failed", "unknown", "needs_setup"),
            "remote_receipt_invalid")
    # The reviewed remote code emits only this public schema and an authenticated
    # encrypted envelope; it must never return an unencrypted credentials object.
    require("credentials" not in receipt and "database" not in receipt, "plaintext_receipt_refused")
    require(receipt.get("cms_url") == "https://www.aptredlight.com/cms", "remote_receipt_target_mismatch")
    if receipt["status"] == "ready":
        require(all(receipt.get(name) is True for name in ("wordpress_installed", "woocommerce_active", "brand_plugin_active", "api_read_verified", "media_read_verified", "front_preserved"))
                and receipt.get("maintenance_lock") == "released",
                "ready_receipt_missing_runtime_proof")
        envelope = receipt.get("encrypted_credentials")
        require(isinstance(envelope, dict)
                and set(envelope) == {"algorithm", "iterations", "salt_length", "wrapped_key_b64", "ciphertext_b64", "hmac_sha256"}
                and envelope.get("algorithm") == "RSA-OAEP-SHA256+AES-256-CBC-PBKDF2-SHA256+HMAC-SHA256"
                and type(envelope.get("iterations")) is int and envelope["iterations"] == 200000
                and type(envelope.get("salt_length")) is int and envelope["salt_length"] == 8,
                "encrypted_credentials_envelope_invalid")
        try:
            wrapped = base64.b64decode(envelope["wrapped_key_b64"], validate=True)
            ciphertext = base64.b64decode(envelope["ciphertext_b64"], validate=True)
        except (TypeError, ValueError):
            raise SetupError("encrypted_credentials_encoding_invalid") from None
        require(len(wrapped) == 384 and 32 <= len(ciphertext) <= 512 * 1024
                and ciphertext.startswith(b"Salted__") and len(ciphertext) % 16 == 0
                and isinstance(envelope["hmac_sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", envelope["hmac_sha256"]),
                "encrypted_credentials_envelope_invalid")
    return receipt


def write_receipt(path, value):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    path.chmod(0o600)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--plugin", type=Path, required=True)
    parser.add_argument("--public-key", type=Path, required=True)
    parser.add_argument("--known-hosts", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args(argv)
    report = {"schema": 1, "status": "not_started", "cms_url": "https://www.aptredlight.com/cms",
              "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "wordpress_installed": False, "woocommerce_active": False, "product_writes_performed": False,
              "wp_cli_source_commit": WP_CLI_COMMIT, "wp_cli_sha512": WP_CLI_SHA512}
    remote_started = False
    staging_started = False
    raw_secret = os.environ.pop(SECRET_ENV, "")
    try:
        if not raw_secret:
            report.update(status="needs_setup", reason="database_secret_missing", writes_performed=False,
                          missing=["GitHub repository secret APTREDLIGHT_CMS_DATABASE"])
            write_receipt(args.receipt, report)
            print(json.dumps({"status": "needs_setup", "reason": "database_secret_missing"}))
            return 1
        db = database_secret(raw_secret)
        public_key = receipt_public_key(args.public_key)
        ssh = ssh_arguments(args.known_hosts)
        stage, remote_receipt = paths_for_run()
        require(args.source.is_file() and not args.source.is_symlink(), "bootstrap_source_missing")
        phar = download_wp_cli()
        archive = bundle(args.source, args.plugin, phar)
        staging_started = True
        upload_bundle(ssh, stage, archive)
        report["staging_performed"] = True
        password = secrets.token_urlsafe(36)
        payload = {"database": {key: db[key] for key in ("name", "user", "password", "host")},
                   "admin_email": db["admin_email"], "admin_login": "aptredlight_admin",
                   "admin_password": password, "receipt_public_key_pem": public_key}
        command = "python3 " + shlex.quote(stage + "/cms_bootstrap.py") + " --bundle-dir " + shlex.quote(stage)
        command += " --wp-cli " + shlex.quote(stage + "/wp-cli.phar") + " --receipt " + shlex.quote(remote_receipt)
        remote_started = True
        result = child(ssh + [command], data=json.dumps(payload).encode("utf-8"), timeout=850)
        report = safe_receipt(result.stdout, (db["password"], password, db["name"], db["user"], db["admin_email"]))
        report["ssh_command_exit_code"] = result.returncode
        report["wp_cli_source_commit"] = WP_CLI_COMMIT
        if result.returncode != 0 and report["status"] == "ready":
            report.update(status="unknown", reason="ssh_exit_contradicts_ready_receipt",
                          wordpress_installed=None, woocommerce_active=None,
                          brand_plugin_active=None, api_read_verified=None, media_read_verified=None)
        write_receipt(args.receipt, report)
        print(json.dumps({"status": report["status"], "reason": report.get("reason"),
                          "wordpress_installed": report.get("wordpress_installed"),
                          "woocommerce_active": report.get("woocommerce_active")}))
        return 0 if result.returncode == 0 and report["status"] == "ready" else 1
    except SetupError as error:
        report.update(status="unknown" if remote_started else "blocked", reason=str(error),
                      writes_performed="unknown" if remote_started or staging_started else False,
                      cms_mutations_started="unknown" if remote_started else False,
                      wordpress_installation_state="unknown" if remote_started else "not_started")
    except Exception:
        report.update(status="unknown" if remote_started else "blocked", reason="runner_setup_failed",
                      writes_performed="unknown" if remote_started or staging_started else False,
                      cms_mutations_started="unknown" if remote_started else False,
                      wordpress_installation_state="unknown" if remote_started else "not_started")
    if remote_started:
        report.update(wordpress_installed=None, woocommerce_active=None,
                      brand_plugin_active=None, api_read_verified=None, media_read_verified=None)
    write_receipt(args.receipt, report)
    print(json.dumps({"status": report["status"], "reason": report["reason"]}))
    return 1


if __name__ == "__main__":
    sys.exit(main())
