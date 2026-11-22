#!/usr/bin/env python3
"""Create an encrypted, native WordPress owner password-setup handoff.

The existing password is never reset by this job. Native reset tokens are captured
internally and encrypted before any receipt can leave the SSH subprocess.
"""
import argparse
import base64
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys
import tempfile
import time

URL='https://www.aptredlight.com/cms'
TARGET=Path('/home/u469397229/domains/aptredlight.com/public_html/cms')
STAGE=Path('/home/u469397229/.aptredlight-cms-bootstrap/staging/run-45025196230-1')
PRIVATE=Path('/home/u469397229/.aptredlight-cms-bootstrap/owner-setup')
MODULE_SHA256='c40d40cc1b473cf0a2c276581894149f923663ea32f53de2e75553893ca29611'
PHAR_SHA512='be928f6b8ca1e8dfb9d2f4b75a13aa4aee0896f8a9a0a1c45cd5d2c98605e6172e6d014dda2e27f88c98befc16c040cbb2bd1bfa121510ea5cdf5f6a30fe8832'
RECIPIENT_SHA256='0654fd6d0f48cbd27da86b82ffc348f7ff2dd3c4ce483ba335017ac3140d0721'
PLUGIN_TARGET=TARGET/'wp-content/plugins/aptredlight-growth-desk/aptredlight-growth-desk.php'
PLUGIN_OLD_SHA256='7088665080448f3ac067f57d8da0c64333b608bf28a0bc6f23247c48e7bb71e6'
PLUGIN_NEW_SHA256='a93c5d2070645fe5524c99881b3649a8779e0b808e7a263cf05948783a6553ae'
BEGIN='APT_OWNER_SETUP_BEGIN';END='APT_OWNER_SETUP_END'

READONLY_PHP=r'''require_once ABSPATH.'wp-admin/includes/plugin.php';$o=get_user_by('login','aptredlight_admin');$ok=$o&&in_array('administrator',$o->roles,true)&&user_can($o,'manage_options');$site=untrailingslashit(get_option('siteurl'))==='https://www.aptredlight.com/cms';$woo=is_plugin_active('woocommerce/woocommerce.php');$brand=is_plugin_active('aptredlight-growth-desk/aptredlight-growth-desk.php');echo 'APT_OWNER_SETUP_BEGIN'.wp_json_encode(array('site_target_verified'=>(bool)$site,'admin_role_verified'=>(bool)$ok,'woocommerce_active'=>(bool)$woo,'brand_plugin_active'=>(bool)$brand)).'APT_OWNER_SETUP_END';'''
WRITE_PHP=r'''require_once ABSPATH.'wp-admin/includes/plugin.php';$o=get_user_by('login','aptredlight_admin');if(!$o||!in_array('administrator',$o->roles,true)||!user_can($o,'manage_options')||untrailingslashit(get_option('siteurl'))!=='https://www.aptredlight.com/cms'||!is_plugin_active('woocommerce/woocommerce.php')||!is_plugin_active('aptredlight-growth-desk/aptredlight-growth-desk.php'))throw new Exception('owner_scope_changed');$ttl=apply_filters('password_reset_expiration',DAY_IN_SECONDS);if(!is_numeric($ttl)||(int)$ttl<=0||(int)$ttl>31536000)throw new Exception('reset_expiration_invalid');$settings=array('blog_public'=>'0','timezone_string'=>'Asia/Shanghai','blogdescription'=>'APTREDLIGHT OEM/ODM product operations','default_comment_status'=>'closed','default_ping_status'=>'closed');foreach($settings as $k=>$v){update_option($k,$v);if(get_option($k)!==$v)throw new Exception('option_readback_failed');}$key=get_password_reset_key($o);if(is_wp_error($key)||!is_string($key)||!preg_match('/^[A-Za-z0-9]{20,64}$/',$key))throw new Exception('reset_key_failed');$issued=time();$payload=array('schema'=>1,'cms_url'=>'https://www.aptredlight.com/cms','admin_login'=>'aptredlight_admin','issued_at'=>gmdate('c',$issued),'expires_at'=>gmdate('c',$issued+(int)$ttl),'setup_url'=>'https://www.aptredlight.com/cms/wp-login.php?action=rp&key='.rawurlencode($key).'&login=aptredlight_admin');echo 'APT_OWNER_SETUP_BEGIN'.wp_json_encode($payload).'APT_OWNER_SETUP_END';'''
MEDIA_PROOF_PHP=r'''require_once ABSPATH.'wp-admin/includes/plugin.php';$s=get_user_by('login','apt_growth_service');$a=get_post(10);$own=$s&&$a&&$a->post_type==='attachment'&&(int)$a->post_author===(int)$s->ID;$role=$s&&array_values($s->roles)===array('apt_growth_product_operator');$allowed=$own&&function_exists('APTREDLIGHT\\GrowthDesk\\own_product_media_capabilities')&&user_can($s,'edit_post',10);$narrow=$s&&!user_can($s,'edit_posts')&&!user_can($s,'edit_pages')&&!user_can($s,'manage_options')&&!user_can($s,'activate_plugins');$no_delete=$s&&!user_can($s,'delete_post',10);echo 'APT_OWNER_SETUP_BEGIN'.wp_json_encode(array('service_role_scoped'=>(bool)$role,'existing_media_owned'=>(bool)$own,'own_media_edit_allowed'=>(bool)$allowed,'article_permissions_unchanged'=>(bool)$narrow,'own_media_delete_denied'=>(bool)$no_delete,'plugin_active'=>is_plugin_active('aptredlight-growth-desk/aptredlight-growth-desk.php'))).'APT_OWNER_SETUP_END';'''


class OwnerSetupError(Exception):pass


def require(condition,code):
    if not condition:raise OwnerSetupError(code)


def safe_chain(path):return not any(p.is_symlink() for p in (path,*path.parents))


def marker_json(raw):
    require(len(raw)<=65536,'wordpress_response_limit')
    try:
        text=raw.decode()
        require(text.count(BEGIN)==1 and text.count(END)==1,'wordpress_response_unconfirmed')
        value=json.loads(text.split(BEGIN,1)[1].split(END,1)[0])
        require(isinstance(value,dict),'wordpress_response_unconfirmed')
        return value
    except OwnerSetupError:raise
    except Exception:raise OwnerSetupError('wordpress_response_unconfirmed') from None


def validate_payload(value):
    require(isinstance(value,dict) and set(value)=={'schema','cms_url','admin_login','issued_at','expires_at','setup_url'}
            and type(value['schema']) is int and value['schema']==1 and value['cms_url']==URL
            and value['admin_login']=='aptredlight_admin','native_setup_schema_invalid')
    try:
        issued=datetime.datetime.fromisoformat(value['issued_at']);expires=datetime.datetime.fromisoformat(value['expires_at'])
        duration=(expires-issued).total_seconds()
        require(issued.tzinfo is not None and expires.tzinfo is not None and 0<duration<=31536000,'native_setup_expiry_invalid')
        require(abs(issued.timestamp()-time.time())<300,'native_setup_issue_time_invalid')
    except OwnerSetupError:raise
    except Exception:raise OwnerSetupError('native_setup_expiry_invalid') from None
    require(isinstance(value['setup_url'],str) and re.fullmatch(re.escape(URL)+r'/wp-login\.php\?action=rp&key=[A-Za-z0-9]{20,64}&login=aptredlight_admin',value['setup_url']),
            'native_setup_url_invalid')
    return value


def validate_public_receipt(report):
    require(isinstance(report,dict) and report.get('cms_url')==URL and report.get('status') in ('ready','blocked','unknown'),
            'owner_remote_receipt_invalid')
    require('setup_url' not in report and 'admin_email' not in report,'owner_plaintext_handoff_refused')
    if report['status']=='ready':
        require(all(report.get(key) is True for key in ('site_target_verified','admin_role_verified','woocommerce_active','brand_plugin_active',
                                                       'native_password_setup_generated','settings_verified'))
                and report.get('native_password_changed') is False,'owner_ready_proof_missing')
        envelope=report.get('encrypted_admin_setup')
        require(isinstance(envelope,dict) and set(envelope)=={'algorithm','iterations','salt_length','wrapped_key_b64','ciphertext_b64','hmac_sha256'}
                and envelope.get('algorithm')=='RSA-OAEP-SHA256+AES-256-CBC-PBKDF2-SHA256+HMAC-SHA256'
                and type(envelope.get('iterations')) is int and envelope['iterations']==200000
                and type(envelope.get('salt_length')) is int and envelope['salt_length']==8,'owner_envelope_invalid')
        try:
            wrapped=base64.b64decode(envelope['wrapped_key_b64'],validate=True)
            ciphertext=base64.b64decode(envelope['ciphertext_b64'],validate=True)
        except Exception:raise OwnerSetupError('owner_envelope_invalid') from None
        require(len(wrapped)==384 and 32<=len(ciphertext)<=65536 and ciphertext.startswith(b'Salted__')
                and len(ciphertext)%16==0 and isinstance(envelope['hmac_sha256'],str)
                and re.fullmatch(r'[0-9a-f]{64}',envelope['hmac_sha256']),'owner_envelope_invalid')
    return report


def perform(backend,pem):
    proof=marker_json(backend.wp(TARGET,['eval',READONLY_PHP],'owner_readonly_preflight'))
    require(set(proof)=={'site_target_verified','admin_role_verified','woocommerce_active','brand_plugin_active'}
            and all(value is True for value in proof.values()),'owner_or_site_scope_not_verified')
    public=backend.command(['openssl','pkey','-pubin','-outform','DER'],'owner_recipient_check',pem.encode(),15)
    require(hashlib.sha256(public).hexdigest()==RECIPIENT_SHA256,'owner_recipient_pin_mismatch')
    backend.encrypt(b'{"preflight":true}',pem)
    payload=validate_payload(marker_json(backend.wp(TARGET,['eval',WRITE_PHP],'owner_native_password_setup')))
    envelope=backend.encrypt(json.dumps(payload,separators=(',',':')).encode(),pem)
    return {'schema':1,'status':'ready','cms_url':URL,**proof,'setup_expires_at':payload['expires_at'],
            'native_password_setup_generated':True,'native_password_changed':False,'settings_verified':True,
            'product_writes_performed':False,'encrypted_admin_setup':envelope,
            'cms_home_redirect':'not_requested'}


def replace_plugin_file(path,content,mode):
    descriptor,temporary=tempfile.mkstemp(prefix='.apt-media-cap-',dir=path.parent)
    try:
        os.fchmod(descriptor,mode)
        with os.fdopen(descriptor,'wb') as stream:
            stream.write(content);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)


def deploy_media_cap_fix(backend,content,task,target=PLUGIN_TARGET):
    require(len(content)<64*1024 and hashlib.sha256(content).hexdigest()==PLUGIN_NEW_SHA256,'media_fix_source_mismatch')
    require(safe_chain(target) and target.is_file() and target.stat().st_uid==os.getuid(),'media_fix_target_unsafe')
    original=target.read_bytes();old_hash=hashlib.sha256(original).hexdigest()
    require(old_hash in (PLUGIN_OLD_SHA256,PLUGIN_NEW_SHA256),'media_fix_existing_file_unreviewed')
    backend.command([backend.php,'-l'],'media_fix_php_syntax',content,20)
    changed=False;backup=task/'aptredlight-growth-desk.php.before'
    try:
        if old_hash!=PLUGIN_NEW_SHA256:
            descriptor=os.open(backup,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(descriptor,'wb') as stream:
                stream.write(original);stream.flush();os.fsync(stream.fileno())
            replace_plugin_file(target,content,stat.S_IMODE(target.stat().st_mode))
            changed=True
        require(hashlib.sha256(target.read_bytes()).hexdigest()==PLUGIN_NEW_SHA256,'media_fix_file_readback_failed')
        backend.wp(TARGET,['plugin','is-active','aptredlight-growth-desk'],'media_fix_plugin_active')
        proof=marker_json(backend.wp(TARGET,['eval',MEDIA_PROOF_PHP],'media_fix_native_capability_readback'))
        require(set(proof)=={'service_role_scoped','existing_media_owned','own_media_edit_allowed','article_permissions_unchanged','own_media_delete_denied','plugin_active'}
                and all(value is True for value in proof.values()),'media_fix_native_capability_not_verified')
        return {'status':'applied' if changed else 'already_current','file_sha256':PLUGIN_NEW_SHA256,
                'private_backup_path':str(backup) if changed else None,'native_capability_proof':proof}
    except Exception:
        if changed:
            try:
                require(hashlib.sha256(target.read_bytes()).hexdigest()==PLUGIN_NEW_SHA256,'media_fix_concurrent_change')
                replace_plugin_file(target,original,stat.S_IMODE(target.stat().st_mode))
                require(hashlib.sha256(target.read_bytes()).hexdigest()==old_hash,'media_fix_restore_readback_failed')
                backend.wp(TARGET,['plugin','is-active','aptredlight-growth-desk'],'media_fix_restore_active')
            except Exception:raise OwnerSetupError('media_cap_fix_failed_rollback_unconfirmed') from None
            raise OwnerSetupError('media_cap_fix_failed_original_restored') from None
        raise OwnerSetupError('media_cap_fix_verification_failed_without_overwrite') from None


def remote_main():
    report={'schema':1,'status':'blocked','cms_url':URL,'native_password_changed':False,'product_writes_performed':False}
    mutation_started=False
    try:
        raw=sys.stdin.buffer.read(131073);require(len(raw)<=131072,'owner_input_limit')
        value=json.loads(raw)
        require(isinstance(value,dict) and set(value)=={'public_key_pem','run_id','run_attempt','plugin_php_b64'},'owner_input_invalid')
        require(isinstance(value['public_key_pem'],str) and 300<len(value['public_key_pem'])<8192
                and '-----BEGIN PUBLIC KEY-----' in value['public_key_pem'] and 'PRIVATE' not in value['public_key_pem'], 'owner_recipient_invalid')
        require(re.fullmatch(r'[1-9][0-9]{0,19}',value['run_id']) and re.fullmatch(r'[1-9][0-9]{0,5}',value['run_attempt']), 'owner_run_id_invalid')
        content=base64.b64decode(value['plugin_php_b64'],validate=True)
        require(len(content)<64*1024 and hashlib.sha256(content).hexdigest()==PLUGIN_NEW_SHA256,'media_fix_source_mismatch')
        for path in (TARGET,STAGE,PRIVATE,STAGE/'cms_bootstrap.py',STAGE/'wp-cli.phar'):
            require(safe_chain(path),'owner_path_symlink_rejected')
        module_path=STAGE/'cms_bootstrap.py';phar=STAGE/'wp-cli.phar'
        require(module_path.is_file() and module_path.stat().st_size<128*1024
                and hashlib.sha256(module_path.read_bytes()).hexdigest()==MODULE_SHA256,'owner_bootstrap_source_mismatch')
        require(phar.is_file() and phar.stat().st_size<32*1024*1024
                and hashlib.sha512(phar.read_bytes()).hexdigest()==PHAR_SHA512,'owner_cli_checksum_mismatch')
        spec=importlib.util.spec_from_file_location('apt_owner_verified_backend',module_path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        # The first backend operates from the already verified private stage.
        initial=module.Backend(STAGE,phar)
        proof=marker_json(initial.wp(TARGET,['eval',READONLY_PHP],'owner_readonly_preflight'))
        require(all(proof.get(k) is True for k in ('site_target_verified','admin_role_verified','woocommerce_active','brand_plugin_active')),
                'owner_or_site_scope_not_verified')
        PRIVATE.mkdir(mode=0o700,exist_ok=True);PRIVATE.chmod(0o700)
        task=PRIVATE/('run-'+value['run_id']+'-'+value['run_attempt'])
        task.mkdir(mode=0o700)
        backend=module.Backend(task,phar)
        mutation_started=True
        report['plugin_media_fix']=deploy_media_cap_fix(backend,content,task)
        report.update(perform(backend,value['public_key_pem']))
        receipt=task/'owner-setup-receipt.json'
        module.atomic_private_json(receipt,report)
        report['secure_receipt_path']=str(receipt)
    except Exception as error:
        report.update(status='unknown' if mutation_started else 'blocked',
                      reason=str(error) if isinstance(error,OwnerSetupError) else 'owner_setup_step_failed',
                      manual_review_required=mutation_started)
    print(json.dumps(report,separators=(',',':')))
    return 0 if report['status']=='ready' else 1


def runner_main(argv):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--known-hosts',type=Path,required=True)
    parser.add_argument('--public-key',type=Path,required=True)
    parser.add_argument('--receipt',type=Path,required=True)
    parser.add_argument('--plugin',type=Path,default=Path('integrations/wordpress/aptredlight-growth-desk/aptredlight-growth-desk.php'))
    args=parser.parse_args(argv)
    report={'schema':1,'status':'blocked','cms_url':URL,'native_password_changed':False}
    try:
        host=os.environ.get('CMS_SSH_HOST','');port=os.environ.get('CMS_SSH_PORT','')
        require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,252}',host) and port.isdigit() and 1<=int(port)<=65535,'owner_ssh_target_invalid')
        require(args.known_hosts.is_file() and not args.known_hosts.is_symlink(),'owner_pinned_host_file_missing')
        require(args.public_key.is_file() and not args.public_key.is_symlink() and args.public_key.stat().st_size<8192,'owner_public_key_missing')
        pem=args.public_key.read_text()
        public=subprocess.run(['openssl','pkey','-pubin','-outform','DER'],input=pem.encode(),capture_output=True,timeout=15,check=False)
        require(public.returncode==0 and hashlib.sha256(public.stdout).hexdigest()==RECIPIENT_SHA256,'owner_recipient_pin_mismatch')
        require(args.plugin.is_file() and not args.plugin.is_symlink() and args.plugin.stat().st_size<64*1024,'media_fix_source_missing')
        content=args.plugin.read_bytes()
        require(hashlib.sha256(content).hexdigest()==PLUGIN_NEW_SHA256,'media_fix_source_mismatch')
        payload={'public_key_pem':pem,'run_id':os.environ.get('GITHUB_RUN_ID',''),'run_attempt':os.environ.get('GITHUB_RUN_ATTEMPT',''),
                 'plugin_php_b64':base64.b64encode(content).decode()}
        source=Path(__file__).read_text()
        command='python3 -c '+shlex.quote(source)+' --remote'
        argv=['ssh','-F','/dev/null','-T','-p',port,'-o','BatchMode=yes','-o','NumberOfPasswordPrompts=0',
              '-o','ConnectTimeout=15','-o','ServerAliveInterval=10','-o','ServerAliveCountMax=3',
              '-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(args.known_hosts.resolve()),
              '-o','ForwardAgent=no','-o','ClearAllForwardings=yes','-o','PermitLocalCommand=no','-o','UpdateHostKeys=no',
              '-o','LogLevel=ERROR','u469397229@'+host,command]
        env=os.environ.copy()
        for key in ('HOSTINGER_SSH_PRIVATE_KEY','APTREDLIGHT_CMS_DATABASE','APTREDLIGHT_HOSTINGER_SETUP'):env.pop(key,None)
        result=subprocess.run(argv,input=json.dumps(payload).encode(),capture_output=True,timeout=180,env=env,check=False)
        require(len(result.stdout)<=128*1024,'owner_remote_receipt_limit')
        report=json.loads(result.stdout)
        validate_public_receipt(report)
        require(b'action=rp' not in result.stdout,'owner_plaintext_handoff_refused')
        if result.returncode!=0 and report.get('status')=='ready':report.update(status='unknown',reason='owner_ssh_exit_not_confirmed')
    except Exception as error:
        report={'schema':1,'status':'unknown','cms_url':URL,'reason':str(error) if isinstance(error,OwnerSetupError) else 'owner_remote_result_unconfirmed',
                'native_password_changed':False}
    args.receipt.write_text(json.dumps(report,indent=2)+'\n');args.receipt.chmod(0o600)
    print(json.dumps({k:report.get(k) for k in ('status','cms_url','setup_expires_at','native_password_changed','reason')}))
    return 0 if report.get('status')=='ready' else 1


if __name__=='__main__':
    sys.exit(remote_main() if sys.argv[1:]==['--remote'] else runner_main(sys.argv[1:]))
