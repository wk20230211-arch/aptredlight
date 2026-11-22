"""Guarded fresh WordPress/Woo CMS setup. Passwords enter through stdin only.

Production target and trusted tool/plugin hashes are fixed. This is deliberately
fresh-only: a partial directory/database is preserved for explicit recovery.
"""
import argparse
import base64
import hashlib
import hmac
import io
import json
import os
import fcntl
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

ROOT = Path('/home/u469397229/domains/aptredlight.com/public_html')
TARGET = ROOT / 'cms'
PRIVATE = Path('/home/u469397229/.aptredlight-cms-bootstrap')
URL = 'https://www.aptredlight.com/cms'
SLUG = 'aptredlight-growth-desk'
WPCLI_SHA512 = 'be928f6b8ca1e8dfb9d2f4b75a13aa4aee0896f8a9a0a1c45cd5d2c98605e6172e6d014dda2e27f88c98befc16c040cbb2bd1bfa121510ea5cdf5f6a30fe8832'
PLUGIN_HASHES = {
    'aptredlight-growth-desk.php':'a93c5d2070645fe5524c99881b3649a8779e0b808e7a263cf05948783a6553ae',
    'assets/admin.js':'3bd7db991a3f078ebc272fc61f38ab677edc53104acd0ceba8fe88b538cf7333',
    'assets/admin.css':'0c12db3a032d044b488b378e90404dbd798b2d63909ec4ff5be681d3f7d10804',
    'readme.txt':'866b197329878c1a8c540671f1908e322f1d8903e4bcadb7a17ea098cfa298b5',
    'README.zh-CN.txt':'07c3b6a1572e44cdb7ac617607b86debc6dca7022cee068418cbeea78c6ed13b',
}


class BootstrapError(Exception):
    pass


def safe_chain(path):
    return not any(p.is_symlink() for p in (path, *path.parents))


def php_string(value):
    return "'" + value.replace('\\', '\\\\').replace("'", "\\'") + "'"


def valid_input(value):
    expected={'database','admin_email','admin_login','admin_password','receipt_public_key_pem'}
    if not isinstance(value,dict) or set(value)!=expected:
        raise BootstrapError('invalid_input_fields')
    db=value['database']
    if not isinstance(db,dict) or set(db)!={'name','user','password','host'}:
        raise BootstrapError('invalid_database_fields')
    for field in ('name','user'):
        if not isinstance(db[field],str) or not re.fullmatch(r'u469397229_[A-Za-z0-9_]{1,53}',db[field]):
            raise BootstrapError('database_account_scope_rejected')
    if db['host'] not in ('127.0.0.1','localhost'):
        raise BootstrapError('database_host_rejected')
    for field in ('password',):
        if not isinstance(db[field],str) or not 1<=len(db[field])<=2000 or any(c in db[field] for c in '\x00\r\n'):
            raise BootstrapError('invalid_database_password')
    if not isinstance(value['admin_login'],str) or not re.fullmatch(r'[A-Za-z0-9_.-]{3,60}',value['admin_login']) or value['admin_login']=='apt_growth_service':
        raise BootstrapError('invalid_admin_login')
    email=value['admin_email']
    if not isinstance(email,str) or len(email)>254 or not re.fullmatch(r'[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+',email):
        raise BootstrapError('invalid_admin_email')
    password=value['admin_password']
    if not isinstance(password,str) or not 16<=len(password)<=2000 or any(c in password for c in '\x00\r\n'):
        raise BootstrapError('invalid_admin_password')
    pem=value['receipt_public_key_pem']
    if not isinstance(pem,str) or not 300<len(pem)<12000 or '-----BEGIN PUBLIC KEY-----' not in pem:
        raise BootstrapError('invalid_receipt_public_key')
    return value


def atomic_private_json(path,value):
    path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    path.parent.chmod(0o700)
    fd,temporary=tempfile.mkstemp(prefix='.receipt-',dir=path.parent)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            json.dump(value,stream,ensure_ascii=False,separators=(',',':'))
            stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


class OfficialCoreRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,message,headers,new_url):
        parsed=urllib.parse.urlsplit(new_url)
        if parsed.scheme!='https' or parsed.hostname not in ('wordpress.org','downloads.wordpress.org') or parsed.username or parsed.port not in (None,443):
            raise BootstrapError('core_download_redirect_rejected')
        return super().redirect_request(request,fp,code,message,headers,new_url)


def core_relative_path(value):
    # Official core includes scoped JS packages such as @wordpress. Validate
    # filesystem containment rather than an incomplete character allowlist.
    if not isinstance(value,str) or not value or len(value)>1024 or '\\' in value or any(ord(c)<32 or ord(c)==127 for c in value):
        raise BootstrapError('core_archive_path_invalid')
    path=PurePosixPath(value)
    if path.is_absolute() or any(part in ('','.','..') for part in value.split('/')) or ':' in value:
        raise BootstrapError('core_archive_path_invalid')
    return path


def extract_core_archive(target,archive_bytes,checksums):
    """Extract the official ZIP with full filenames, then verify every manifest file."""
    target=Path(target)
    if not target.is_dir() or not safe_chain(target):raise BootstrapError('core_target_invalid')
    if not isinstance(checksums,dict) or not 100<=len(checksums)<=10000:raise BootstrapError('core_manifest_invalid')
    manifest={}
    for name,digest in checksums.items():
        core_relative_path(name)
        if not isinstance(digest,str) or re.fullmatch(r'[0-9a-fA-F]{32}',digest) is None:raise BootstrapError('core_manifest_invalid')
        manifest[name]=digest.lower()
    if len(archive_bytes)>64*1024*1024:raise BootstrapError('core_zip_size_limit')
    try:archive=zipfile.ZipFile(io.BytesIO(archive_bytes))
    except (ValueError,zipfile.BadZipFile):raise BootstrapError('core_zip_invalid') from None
    with archive:
        entries=archive.infolist();names=set();planned=[];total=0
        if not entries or len(entries)>10000:raise BootstrapError('core_archive_count_limit')
        for entry in entries:
            raw=entry.filename
            if raw!=entry.orig_filename:raise BootstrapError('core_archive_path_invalid')
            if raw=='wordpress/' and entry.is_dir():continue
            if not raw.startswith('wordpress/'):raise BootstrapError('core_archive_root_invalid')
            name=raw[len('wordpress/'):-1] if entry.is_dir() else raw[len('wordpress/'):]
            relative=core_relative_path(name);kind=(entry.external_attr>>16)&0o170000
            if kind not in (0,stat.S_IFREG,stat.S_IFDIR) or entry.flag_bits&1 or entry.compress_type not in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED):raise BootstrapError('core_archive_entry_invalid')
            if kind and ((kind==stat.S_IFDIR)!=entry.is_dir()):raise BootstrapError('core_archive_entry_invalid')
            if name in names:raise BootstrapError('core_archive_duplicate')
            names.add(name)
            if str(relative) in ('.htaccess','wp-config.php'):raise BootstrapError('core_archive_protected_file')
            destination=target.joinpath(*relative.parts)
            if not safe_chain(destination) or destination.exists():raise BootstrapError('core_archive_existing_path')
            if entry.file_size<0 or entry.file_size>32*1024*1024:raise BootstrapError('core_archive_file_size_limit')
            total+=entry.file_size
            if total>256*1024*1024:raise BootstrapError('core_archive_expanded_size_limit')
            planned.append((entry,destination))
        # Validate all archive metadata before any extraction. Never use tar,
        # whose ustar-name limits truncated the new long AI-client filenames.
        for entry,destination in planned:
            if entry.is_dir():destination.mkdir(mode=0o755,parents=True,exist_ok=True);continue
            destination.parent.mkdir(mode=0o755,parents=True,exist_ok=True)
            with archive.open(entry) as source,destination.open('xb') as output:
                shutil.copyfileobj(source,output,length=1024*1024)
            destination.chmod(0o644)
    for name,digest in manifest.items():
        path=target.joinpath(*core_relative_path(name).parts)
        if not safe_chain(path) or not path.is_file():raise BootstrapError('core_official_checksum_missing_file')
        md5=hashlib.md5()
        with path.open('rb') as stream:
            for block in iter(lambda:stream.read(1024*1024),b''):md5.update(block)
        if md5.hexdigest()!=digest:raise BootstrapError('core_official_checksum_mismatch')
    return {'source':'official_https_zip','manifest_count':len(manifest),'official_checksums_verified':True}


class Backend:
    def __init__(self,bundle,wp_cli,deadline=None):
        self.bundle=Path(bundle);self.wp_cli=Path(wp_cli)
        self.php=shutil.which('php');self.openssl=shutil.which('openssl')
        self.deadline=deadline or time.monotonic()+500

    def command(self,args,step,stdin=None,timeout=90,pass_fds=()):
        remaining=self.deadline-time.monotonic()
        if remaining<=0:raise BootstrapError('total_deadline_reached')
        try:
            child_env=os.environ.copy()
            child_env['WP_CLI_CONFIG_PATH']='/dev/null'
            for name in ('WP_CLI_PACKAGES_DIR','WP_CLI_PHP_ARGS','MYSQL_PWD'):
                child_env.pop(name,None)
            result=subprocess.run(args,input=stdin,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                  timeout=min(timeout,remaining),check=False,pass_fds=pass_fds,
                                  env=child_env,cwd=self.bundle)
        except subprocess.TimeoutExpired:
            raise BootstrapError(step+'_timeout') from None
        except Exception:
            raise BootstrapError(step+'_unavailable') from None
        if len(result.stdout)>4*1024*1024 or len(result.stderr)>4*1024*1024:
            raise BootstrapError(step+'_output_over_limit')
        if result.returncode:raise BootstrapError(step+'_failed')
        return result.stdout

    def php_json(self,code,data,step):
        raw=self.command([self.php,'-r',code],step,json.dumps(data).encode('utf-8'),30)
        try:return json.loads(raw)
        except Exception:raise BootstrapError(step+'_invalid_response') from None

    def php_info(self):
        if not self.php or not self.openssl:raise BootstrapError('php_or_openssl_missing')
        return self.php_json('$names=array("mysqli","json","openssl","fileinfo","curl","mbstring","xml","zip","gd","imagick");$e=array();foreach($names as $n){$e[$n]=extension_loaded($n);}echo json_encode(array("version"=>PHP_VERSION,"extensions"=>$e));',{},'php_preflight')

    def official_json(self,url):
        host=urllib.parse.urlsplit(url).hostname
        if host!='api.wordpress.org':raise BootstrapError('official_metadata_origin_rejected')
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'APTREDLIGHT-CMS-Setup/1.0','Accept':'application/json'})
            with urllib.request.build_opener(NoRedirect).open(req,timeout=25) as response:
                raw=response.read(2*1024*1024+1)
            if len(raw)>2*1024*1024:raise ValueError()
            return json.loads(raw)
        except Exception:raise BootstrapError('official_metadata_unavailable') from None

    def versions(self):
        core=self.official_json('https://api.wordpress.org/core/version-check/1.7/')
        woo=self.official_json('https://api.wordpress.org/plugins/info/1.2/?action=plugin_information&request%5Bslug%5D=woocommerce&request%5Bfields%5D%5Bsections%5D=false')
        offers=[x for x in core.get('offers',[]) if isinstance(x,dict) and
                x.get('response') in ('upgrade','autoupdate','latest') and
                re.fullmatch(r'\d+(?:\.\d+){1,2}',str(x.get('version','')))]
        if not offers:raise BootstrapError('core_metadata_invalid')
        selected=offers[0]
        result={'core':selected['version'],'core_php':str(selected.get('php_version','')),
                'woo':str(woo.get('version','')),'woo_php':str(woo.get('requires_php',''))}
        if not all(re.fullmatch(r'\d+(?:\.\d+){1,2}',result[k]) for k in result):raise BootstrapError('version_metadata_invalid')
        return result

    def download_core(self,target,version):
        if re.fullmatch(r'\d+(?:\.\d+){1,2}',version) is None:raise BootstrapError('core_download_version_invalid')
        url='https://wordpress.org/wordpress-'+version+'.zip'
        try:
            request=urllib.request.Request(url,headers={'User-Agent':'APTREDLIGHT-CMS-Setup/1.1'})
            with urllib.request.build_opener(OfficialCoreRedirect).open(request,timeout=75) as response:
                parsed=urllib.parse.urlsplit(response.geturl())
                if parsed.scheme!='https' or parsed.hostname not in ('wordpress.org','downloads.wordpress.org') or parsed.username or parsed.port not in (None,443):raise BootstrapError('core_download_origin_rejected')
                raw=response.read(64*1024*1024+1)
        except BootstrapError:raise
        except Exception:raise BootstrapError('core_zip_download_failed') from None
        metadata=self.official_json('https://api.wordpress.org/core/checksums/1.0/?version='+version+'&locale=en_US')
        return extract_core_archive(target,raw,metadata.get('checksums'))

    def database_check(self,db):
        code=r'''mysqli_report(MYSQLI_REPORT_OFF);$v=json_decode(stream_get_contents(STDIN),true);try{$m=@new mysqli($v['host'],$v['user'],$v['password'],$v['name']);if($m->connect_errno){echo json_encode(array('auth_success'=>false));exit;}$q=$m->query('SELECT COUNT(*) AS n FROM information_schema.tables WHERE table_schema=DATABASE()');if(!$q){echo json_encode(array('auth_success'=>true,'query_success'=>false));exit;}$r=$q->fetch_assoc();echo json_encode(array('auth_success'=>true,'query_success'=>true,'table_count'=>(int)$r['n'],'mysql_only'=>true));}catch(Throwable $e){echo json_encode(array('auth_success'=>false));}'''
        return self.php_json(code,db,'database_preflight')

    def wp(self,target,args,step,stdin=None,timeout=120):
        https_context=['--url='+URL] if args and args[0]=='eval' else []
        return self.command([self.php,str(self.wp_cli),'--path='+str(target),*https_context,'--skip-themes','--skip-packages','--no-color',*args],step,stdin,timeout)

    def health(self,url,nonce):
        value=self.http_json(url)
        if value.get('apt_php_probe')!=nonce:return None
        return value

    def http_json(self,url,authorization=None):
        parsed=urllib.parse.urlsplit(url)
        if parsed.scheme!='https' or parsed.netloc!='www.aptredlight.com' or not parsed.path.startswith('/cms/'):
            raise BootstrapError('cms_http_origin_rejected')
        headers={'User-Agent':'APTREDLIGHT-CMS-Verification/1.0','Accept':'application/json','Cache-Control':'no-cache'}
        if authorization:headers['Authorization']=authorization
        try:
            with urllib.request.build_opener(NoRedirect).open(urllib.request.Request(url,headers=headers),timeout=25) as response:
                if 'json' not in response.headers.get('Content-Type','').lower():raise ValueError()
                raw=response.read(2*1024*1024+1)
                if len(raw)>2*1024*1024:raise ValueError()
            return json.loads(raw)
        except Exception:raise BootstrapError('cms_http_verification_failed') from None

    def http_status(self,url):
        parsed=urllib.parse.urlsplit(url)
        if parsed.scheme!='https' or parsed.netloc!='www.aptredlight.com' or not parsed.path.startswith('/cms/'):
            raise BootstrapError('cms_http_origin_rejected')
        try:
            with urllib.request.build_opener(NoRedirect).open(urllib.request.Request(url,headers={'Cache-Control':'no-cache','User-Agent':'APTREDLIGHT-CMS-Verification/1.0'}),timeout=20) as response:
                return response.status
        except urllib.error.HTTPError as error:
            return error.code
        except Exception:raise BootstrapError('cms_http_verification_failed') from None

    def encrypt(self,plain,pem):
        details=self.command([self.openssl,'pkey','-pubin','-text','-noout'],'receipt_key_check',pem.encode(),15)
        match=re.search(rb'Public-Key:\s*\((\d+) bit\)',details)
        if not match or int(match[1])<3072 or b'Modulus:' not in details:raise BootstrapError('rsa_public_key_requires_3072_bits')
        public_file=self.bundle/('.receipt-public-'+secrets.token_hex(8)+'.pem')
        fd=os.open(public_file,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as stream:stream.write(pem.encode())
        password=base64.b64encode(secrets.token_bytes(32))
        mac_key=secrets.token_bytes(32)
        read_fd,write_fd=os.pipe()
        try:
            os.write(write_fd,password+b'\n');os.close(write_fd);write_fd=-1
            help_result=subprocess.run([self.openssl,'enc','-help'],capture_output=True,check=False,timeout=10)
            args=[self.openssl,'enc','-aes-256-cbc','-salt','-pbkdf2','-iter','200000','-md','sha256','-pass','fd:'+str(read_fd)]
            if b'-saltlen' in help_result.stdout+help_result.stderr:args+=['-saltlen','8']
            ciphertext=self.command(args,'receipt_encryption',plain,30,pass_fds=(read_fd,))
            package=json.dumps({'passphrase_b64':password.decode(),'hmac_key_b64':base64.b64encode(mac_key).decode()},separators=(',',':')).encode()
            wrapped=self.command([self.openssl,'pkeyutl','-encrypt','-pubin','-inkey',str(public_file),'-pkeyopt','rsa_padding_mode:oaep','-pkeyopt','rsa_oaep_md:sha256','-pkeyopt','rsa_mgf1_md:sha256'],'receipt_key_wrapping',package,20)
            return {'algorithm':'RSA-OAEP-SHA256+AES-256-CBC-PBKDF2-SHA256+HMAC-SHA256','iterations':200000,'salt_length':8,
                    'wrapped_key_b64':base64.b64encode(wrapped).decode(),'ciphertext_b64':base64.b64encode(ciphertext).decode(),
                    'hmac_sha256':hmac.new(mac_key,ciphertext,hashlib.sha256).hexdigest()}
        finally:
            os.close(read_fd)
            if write_fd>=0:os.close(write_fd)
            if public_file.exists():public_file.unlink()


def version_tuple(value):
    match=re.match(r'^(\d+)\.(\d+)(?:\.(\d+))?',str(value))
    if not match:raise BootstrapError('php_version_invalid')
    return tuple(int(x or 0) for x in match.groups())


def htaccess():
    return '''DirectoryIndex index.php
Options -Indexes
<Files "wp-config.php">
Require all denied
</Files>
<FilesMatch "(^\\.|\\.(?:sql|bak|log|ini)$)">
Require all denied
</FilesMatch>
<IfModule mod_rewrite.c>
RewriteEngine On
RewriteRule .* - [E=HTTP_AUTHORIZATION:%{HTTP:Authorization}]
RewriteBase /cms/
RewriteRule ^index\\.php$ - [L]
RewriteCond %{REQUEST_FILENAME} !-f
RewriteCond %{REQUEST_FILENAME} !-d
RewriteRule . /cms/index.php [L]
</IfModule>
'''


def maintenance_htaccess(allowed_probe=None):
    value='DirectoryIndex index.php\nOptions -Indexes\nRequire all denied\n'
    if allowed_probe:
        if not re.fullmatch(r'apt-health-[a-f0-9]{32}\.php',allowed_probe):raise BootstrapError('invalid_probe_filename')
        value+='<Files "'+allowed_probe+'">\nRequire all granted\n</Files>\n'
    return value


def config_php(db):
    values={'DB_NAME':db['name'],'DB_USER':db['user'],'DB_PASSWORD':db['password'],'DB_HOST':db['host'],'DB_CHARSET':'utf8mb4','DB_COLLATE':''}
    for name in ('AUTH_KEY','SECURE_AUTH_KEY','LOGGED_IN_KEY','NONCE_KEY','AUTH_SALT','SECURE_AUTH_SALT','LOGGED_IN_SALT','NONCE_SALT'):
        values[name]=secrets.token_urlsafe(64)
    code='<?php\n'+''.join('define('+php_string(k)+','+php_string(v)+');\n' for k,v in values.items())
    code+="$table_prefix='aptcms_';\ndefine('WP_DEBUG',false);\ndefine('FORCE_SSL_ADMIN',true);\ndefine('DISALLOW_FILE_EDIT',true);\nif(!defined('ABSPATH'))define('ABSPATH',__DIR__.'/');\nrequire_once ABSPATH.'wp-settings.php';\n"
    return code


CREDENTIAL_PHP = r'''$v=json_decode(stream_get_contents(STDIN),true);$required=array('edit_products','publish_products','upload_files');$r=get_role('apt_growth_product_operator');if(!$r)throw new Exception('role_missing');foreach($required as $c){if(empty($r->capabilities[$c]))throw new Exception('role_missing_cap');}foreach(array('manage_options','manage_woocommerce','edit_shop_orders','edit_others_shop_orders','activate_plugins','edit_users') as $c){if(!empty($r->capabilities[$c]))throw new Exception('role_too_broad');}if(get_user_by('login','apt_growth_service'))throw new Exception('service_user_exists');$id=wp_insert_user(array('user_login'=>'apt_growth_service','user_email'=>$v['service_email'],'user_pass'=>$v['service_password'],'role'=>'apt_growth_product_operator'));if(is_wp_error($id))throw new Exception('service_user_failed');$created=get_userdata($id);if(!$created||array_values($created->roles)!==array('apt_growth_product_operator'))throw new Exception('service_role_readback_failed');$app=WP_Application_Passwords::create_new_application_password($id,array('name'=>'APT Growth Desk media'));if(is_wp_error($app))throw new Exception('application_password_failed');if(!function_exists('wc_api_hash'))throw new Exception('woocommerce_key_api_missing');$key='ck_'.bin2hex(random_bytes(20));$secret='cs_'.bin2hex(random_bytes(20));global $wpdb;$ok=$wpdb->insert($wpdb->prefix.'woocommerce_api_keys',array('user_id'=>$id,'description'=>'APT Growth Desk products','permissions'=>'read_write','consumer_key'=>wc_api_hash($key),'consumer_secret'=>$secret,'truncated_key'=>substr($key,-7)),array('%d','%s','%s','%s','%s','%s'));if(!$ok)throw new Exception('consumer_key_failed');echo 'APT_CMS_CREDENTIALS_BEGIN'.wp_json_encode(array('service_user_id'=>(int)$id,'service_username'=>'apt_growth_service','service_role'=>'apt_growth_product_operator','service_password'=>$v['service_password'],'application_password'=>$app[0],'consumer_key'=>$key,'consumer_secret'=>$secret)).'APT_CMS_CREDENTIALS_END';'''


class Bootstrap:
    def __init__(self,bundle,wp_cli,receipt,backend=None,root=ROOT,target=TARGET,private=PRIVATE,wp_cli_sha512=WPCLI_SHA512):
        self.bundle=Path(bundle);self.wp_cli=Path(wp_cli);self.receipt=Path(receipt)
        self.root=Path(root);self.target=Path(target);self.private=Path(private)
        self.backend=backend or Backend(bundle,wp_cli)
        self.wp_cli_sha512=wp_cli_sha512
        self.report={'schema':1,'status':'blocked','cms_url':URL,'wordpress_installed':False,
                     'woocommerce_active':False,'brand_plugin_active':False,'cms_mutations_started':False,
                     'database_check':{'auth_success':False,'empty':False},'front_preserved':True,
                     'api_read_verified':False,'media_read_verified':False,'writes_performed':False,
                     'product_writes_performed':False,'real_product_creation_performed':False,
                     'maintenance_lock':'not_created'}
        self.recovery=None

    def preserve_front(self):
        result={}
        for name in ('index.html','.htaccess'):
            path=self.root/name
            result[name]=hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        return result

    def preflight(self,config):
        valid_input(config)
        if self.target!=self.root/'cms' or not self.root.is_dir() or not safe_chain(self.root) or not safe_chain(self.target):
            raise BootstrapError('cms_target_scope_rejected')
        if self.target.exists() and (not self.target.is_dir() or next(self.target.iterdir(),None) is not None):
            raise BootstrapError('existing_or_partial_cms_requires_review')
        if not safe_chain(self.bundle) or not safe_chain(self.wp_cli) or not self.wp_cli.is_file():raise BootstrapError('trusted_bundle_missing')
        if hashlib.sha512(self.wp_cli.read_bytes()).hexdigest()!=self.wp_cli_sha512:raise BootstrapError('wp_cli_integrity_failed')
        plugin=self.bundle/'plugin'/SLUG
        present=set()
        for file in plugin.rglob('*'):
            if not safe_chain(file):raise BootstrapError('reviewed_plugin_integrity_failed')
            if file.is_file():present.add(file.relative_to(plugin).as_posix())
        if present!=set(PLUGIN_HASHES):raise BootstrapError('reviewed_plugin_integrity_failed')
        for name,expected in PLUGIN_HASHES.items():
            file=plugin/name
            if not file.is_file() or not safe_chain(file) or hashlib.sha256(file.read_bytes()).hexdigest()!=expected:
                raise BootstrapError('reviewed_plugin_integrity_failed')
        info=self.backend.php_info(); versions=self.backend.versions()
        if version_tuple(info.get('version'))<max(version_tuple('7.4'),version_tuple(versions['core_php']),version_tuple(versions['woo_php'])):
            raise BootstrapError('php_below_official_component_requirement')
        required=('mysqli','json','openssl','fileinfo','curl','mbstring','xml','zip')
        if not all(info.get('extensions',{}).get(k) is True for k in required):raise BootstrapError('required_php_extension_missing')
        if not (info['extensions'].get('gd') or info['extensions'].get('imagick')):raise BootstrapError('image_processor_missing')
        db=self.backend.database_check(config['database'])
        self.report['database_check']['auth_success']=db.get('auth_success') is True
        if not db.get('auth_success') or not db.get('query_success'):raise BootstrapError('mysql_authentication_or_read_failed')
        if db.get('mysql_only') is not True:raise BootstrapError('mysql_driver_required')
        if db.get('table_count')!=0:raise BootstrapError('database_not_empty_requires_review')
        self.report['database_check']['empty']=True
        # Prove confidentiality tooling before placing passwords in wp-config.php.
        self.backend.encrypt(b'{"preflight":true}',config['receipt_public_key_pem'])
        return info,versions

    def child_htaccess(self,text):
        if not self.target.is_dir() or not safe_chain(self.target):raise BootstrapError('cms_target_changed')
        path=self.target/'.htaccess'
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o644)
        with os.fdopen(fd,'w') as stream:stream.write(text)
        path.chmod(0o644)

    def close_on_failure(self):
        if self.report['status']=='ready' or not self.report['cms_mutations_started']:return
        try:
            self.child_htaccess(maintenance_htaccess());self.report['maintenance_lock']='closed_after_failure'
        except Exception:self.report['maintenance_lock']='unconfirmed_after_failure'

    def checkpoint(self,config,secrets_known,stage):
        plain=json.dumps({'schema':1,'cms_url':URL,'stage':stage,'database':config['database'],
                          'admin_email':config['admin_email'],'admin_login':config['admin_login'],
                          'admin_password':config['admin_password'],**secrets_known},ensure_ascii=False,separators=(',',':')).encode()
        encrypted=self.backend.encrypt(plain,config['receipt_public_key_pem'])
        self.recovery=self.receipt.with_name(self.receipt.stem+'-encrypted-recovery.json')
        atomic_private_json(self.recovery,{'schema':1,'cms_url':URL,'stage':stage,'encrypted_credentials':encrypted})
        self.report['secure_recovery_receipt_path']=str(self.recovery)
        self.report['encrypted_credentials']=encrypted

    def run(self,config):
        front_before=self.preserve_front();known={};step='preflight'
        try:
            _,versions=self.preflight(config)
            self.report['component_versions']={'wordpress':versions['core'],'woocommerce':versions['woo']}
            self.checkpoint(config,known,'validated_before_installation')
            self.report['cms_mutations_started']=True
            self.report['writes_performed']=True
            self.target.mkdir(mode=0o755,exist_ok=True)
            probe_name='apt-health-'+secrets.token_hex(16)+'.php';probe=self.target/probe_name;nonce=secrets.token_hex(24)
            self.child_htaccess(maintenance_htaccess(probe_name))
            self.report['maintenance_lock']='health_probe_only'
            probe.write_text('<?php $e=array();foreach(array("mysqli","json","openssl","fileinfo","curl","mbstring","xml","zip","gd","imagick") as $n){$e[$n]=extension_loaded($n);}header("Content-Type: application/json");echo json_encode(array("apt_php_probe"=>'+php_string(nonce)+',"version"=>PHP_VERSION,"extensions"=>$e));');probe.chmod(0o644)
            try:
                health=self.backend.health(URL+'/'+probe_name,nonce)
                web_ext=health.get('extensions',{}) if isinstance(health,dict) else {}
                if not health or not all(web_ext.get(k) is True for k in ('mysqli','json','openssl','fileinfo','curl','mbstring','xml','zip')) or not (web_ext.get('gd') or web_ext.get('imagick')) or version_tuple(health.get('version'))<max(version_tuple('7.4'),version_tuple(versions['core_php']),version_tuple(versions['woo_php'])):
                    raise BootstrapError('web_php_not_ready')
                self.report['web_php_version']=str(health['version'])
                self.child_htaccess(maintenance_htaccess())
                self.report['maintenance_lock']='closed'
                if self.backend.http_status(URL+'/'+probe_name)!=403:raise BootstrapError('maintenance_lock_not_enforced')
            finally:
                if probe.is_file():probe.unlink()
            step='core_download'
            self.report['core_integrity']=self.backend.download_core(self.target,versions['core'])
            self.backend.wp(self.target,['core','verify-checksums','--version='+versions['core'],'--locale=en_US'],'core_checksums')
            config_path=self.target/'wp-config.php'
            fd=os.open(config_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'w') as stream:stream.write(config_php(config['database']))
            step='wordpress_install'
            self.backend.wp(self.target,['core','install','--url='+URL,'--title=APTREDLIGHT CMS','--admin_user='+config['admin_login'],'--admin_email='+config['admin_email'],'--skip-email','--prompt=admin_password'],step,(config['admin_password']+'\n').encode())
            self.backend.wp(self.target,['core','is-installed'],'wordpress_readback')
            self.report['wordpress_installed']=True
            self.checkpoint(config,known,'wordpress_installed')
            for option,value in [('blog_public','0'),('permalink_structure','/%postname%/'),('woocommerce_allow_tracking','no')]:
                self.backend.wp(self.target,['option','update',option,value],'cms_option')
            step='woocommerce_install'
            self.backend.wp(self.target,['plugin','install','woocommerce','--version='+versions['woo']],step)
            self.backend.wp(self.target,['plugin','verify-checksums','woocommerce'],'woocommerce_checksums')
            self.backend.wp(self.target,['plugin','activate','woocommerce'],'woocommerce_activate')
            self.backend.wp(self.target,['plugin','is-active','woocommerce'],'woocommerce_readback')
            self.report['woocommerce_active']=True
            step='brand_plugin_install'
            destination=self.target/'wp-content/plugins'/SLUG
            if destination.exists():raise BootstrapError('brand_plugin_target_not_empty')
            shutil.copytree(self.bundle/'plugin'/SLUG,destination)
            for item in (destination,*destination.rglob('*')):item.chmod(0o755 if item.is_dir() else 0o644)
            self.backend.wp(self.target,['plugin','activate',SLUG],'brand_plugin_activate')
            self.backend.wp(self.target,['plugin','is-active',SLUG],'brand_plugin_readback')
            self.report['brand_plugin_active']=True
            self.backend.wp(self.target,['rewrite','flush'],'cms_rewrite_options')
            step='service_credentials'
            service={'service_password':secrets.token_urlsafe(40),'service_email':'apt-growth-'+secrets.token_hex(8)+'@aptredlight.com'}
            raw=self.backend.wp(self.target,['eval',CREDENTIAL_PHP],step,json.dumps(service).encode())
            try:
                text=raw.decode();begin='APT_CMS_CREDENTIALS_BEGIN';end='APT_CMS_CREDENTIALS_END'
                if text.count(begin)!=1 or text.count(end)!=1:raise ValueError()
                creds=json.loads(text.split(begin,1)[1].split(end,1)[0])
                if not isinstance(creds,dict) or not str(creds.get('consumer_key','')).startswith('ck_') or not str(creds.get('consumer_secret','')).startswith('cs_') or not creds.get('application_password') or creds.get('service_role')!='apt_growth_product_operator' or not isinstance(creds.get('service_user_id'),int):raise ValueError()
            except Exception:raise BootstrapError('service_credentials_unconfirmed') from None
            known={'service_credentials':creds}
            self.checkpoint(config,known,'service_credentials_created')
            step='woocommerce_readonly_verification'
            self.child_htaccess(htaccess());self.report['maintenance_lock']='released_for_authenticated_verification'
            if self.backend.http_status(URL+'/wp-config.php')!=403:raise BootstrapError('config_access_not_denied')
            authorization='Basic '+base64.b64encode((creds['consumer_key']+':'+creds['consumer_secret']).encode()).decode()
            products=self.backend.http_json(URL+'/wp-json/wc/v3/products?per_page=10&context=edit&status=any',authorization)
            if not isinstance(products,list) or len(products)>10 or not all(isinstance(p,dict) and isinstance(p.get('id'),int) and isinstance(p.get('name'),str) and isinstance(p.get('sku'),str) for p in products):raise BootstrapError('woocommerce_readonly_verification_failed')
            self.report['readonly_product_test']={'passed':True,'returned_count':len(products)}
            self.report['api_read_verified']=True
            media_auth='Basic '+base64.b64encode((creds['service_username']+':'+creds['application_password']).encode()).decode()
            me=self.backend.http_json(URL+'/wp-json/wp/v2/users/me?context=edit',media_auth)
            if not isinstance(me,dict) or me.get('id')!=creds['service_user_id'] or me.get('username')!=creds['service_username'] or me.get('roles')!=['apt_growth_product_operator']:raise BootstrapError('media_identity_verification_failed')
            caps=me.get('capabilities',{})
            if not isinstance(caps,dict) or caps.get('upload_files') is not True or any(caps.get(k) for k in ('manage_options','manage_woocommerce','edit_shop_orders','edit_others_shop_orders','activate_plugins','edit_users')):raise BootstrapError('media_capability_verification_failed')
            self.report['media_read_verified']=True
            self.checkpoint(config,known,'ready')
            self.report['status']='ready'
            self.report['maintenance_lock']='released'
        except Exception as error:
            self.report['status']='failed' if self.report['cms_mutations_started'] else 'blocked'
            self.report['reason']=str(error) if isinstance(error,BootstrapError) else 'bootstrap_step_failed'
            self.report['last_step']=step
            self.report['manual_review_required']=self.report['cms_mutations_started']
            self.close_on_failure()
        self.report['front_preserved']=front_before==self.preserve_front()
        if not self.report['front_preserved']:
            self.report.update(status='failed',reason='frontend_changed_during_setup',manual_review_required=True)
        self.close_on_failure()
        try:atomic_private_json(self.receipt,self.report)
        except Exception:
            self.report.update(status='failed',reason='secure_receipt_write_failed')
            self.close_on_failure()
        return self.report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle-dir',required=True);parser.add_argument('--wp-cli',required=True);parser.add_argument('--receipt',required=True)
    args=parser.parse_args()
    try:
        bundle=Path(args.bundle_dir);wp_cli=Path(args.wp_cli);receipt=Path(args.receipt)
        for path in (bundle,wp_cli,receipt):
            if (not path.is_absolute() or '..' in path.parts or
                    PRIVATE not in path.resolve(strict=False).parents or not safe_chain(path)):
                raise BootstrapError('private_path_scope_rejected')
        if PRIVATE/'staging' not in bundle.parents or PRIVATE/'receipts' not in receipt.parents:
            raise BootstrapError('private_path_scope_rejected')
        raw=sys.stdin.buffer.read(32769)
        if len(raw)>32768:raise BootstrapError('input_over_limit')
        config=json.loads(raw);valid_input(config)
        lock_path=PRIVATE/'.bootstrap.lock'
        fd=os.open(lock_path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
        try:
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:raise BootstrapError('another_bootstrap_is_running') from None
            report=Bootstrap(bundle,wp_cli,receipt).run(config)
        finally:os.close(fd)
    except Exception as error:
        report={'schema':1,'status':'blocked','cms_url':URL,'reason':str(error) if isinstance(error,BootstrapError) else 'invalid_setup_input','cms_mutations_started':False,'writes_performed':False,'product_writes_performed':False,'wordpress_installed':False,'woocommerce_active':False,'brand_plugin_active':False,'api_read_verified':False,'media_read_verified':False}
    print(json.dumps(report,ensure_ascii=False,separators=(',',':')))
    return 0 if report['status']=='ready' else 3


if __name__=='__main__':sys.exit(main())
