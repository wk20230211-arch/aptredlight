#!/usr/bin/env python3
"""Pinned static release validation and transactional, owner-scoped SSH deployment."""
import argparse
import base64
import hashlib
from html.parser import HTMLParser
import ipaddress
import json
import os
from pathlib import Path, PurePosixPath
import pwd
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from urllib.parse import urlsplit, urljoin, urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler
import uuid

PROJECT = 'appgprj_6addb8c872b081918d711d7bc0c5cbf4'
ORIGIN = 'https://www.aptredlight.com'
SOURCE_ORIGIN = 'https://aptredlight-wellness.wk20230211.chatgpt.site'
USER = 'u469397229'
INDEX = 'hostinger-release-manifest.json'
ORIGINAL = 'release-manifest.json'
POINTER_KEYS = {'schema','project_id','source_origin','source_commit','sites_version','manifest_sha256','canonical_origin'}
MAX_TOTAL = 512 * 1024 * 1024
MAX_FILE = 200 * 1024 * 1024
MAX_FILES = 5000


class DeployError(RuntimeError):
    def __init__(self, message, receipt=None):
        super().__init__(message)
        self.receipt = receipt or {}


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')


def require(condition, message):
    if not condition:
        raise DeployError(message)


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (ValueError, OSError, UnicodeError):
        raise DeployError('Required JSON could not be read; no reset was performed.') from None


def validate_pointer(value):
    require(isinstance(value, dict) and set(value) == POINTER_KEYS, 'Invalid release pointer fields.')
    require(type(value['schema']) is int and value['schema'] == 1 and value['project_id'] == PROJECT and value['canonical_origin'] == ORIGIN and value['source_origin'] == SOURCE_ORIGIN, 'Release pointer project/origin mismatch.')
    require(type(value['sites_version']) is int and value['sites_version'] > 0, 'Invalid Sites version.')
    require(isinstance(value['source_commit'],str) and re.fullmatch('[a-f0-9]{40}',value['source_commit']), 'Invalid source commit.')
    require(isinstance(value['manifest_sha256'],str) and re.fullmatch('[a-f0-9]{64}',value['manifest_sha256']), 'Invalid pinned manifest hash.')
    return value


def safe_path(value):
    require(isinstance(value,str) and value and len(value) <= 1024, 'Invalid release path.')
    require(not any(ord(c) < 32 or ord(c) == 127 for c in value) and '\\' not in value and ':' not in value and '%' not in value, 'Unsafe release path encoding.')
    path = PurePosixPath(value)
    require(not path.is_absolute() and str(path) == value and all(p not in ('','.','..') for p in path.parts), 'Release paths must be normalized relative paths.')
    forbidden = {'.git','.openai','.hostinger','node_modules','server','api','__pycache__'}
    require(not any(p.lower() in forbidden or p.lower().startswith('.env') for p in path.parts), 'Private or API path is forbidden.')
    require(not any(p.startswith('.') for p in path.parts) or value == '.htaccess', 'Hidden release paths are forbidden except .htaccess.')
    return value


def regular_under(root, name, required=True):
    safe_path(name)
    target = Path(root) / name
    current = Path(root)
    for part in PurePosixPath(name).parts:
        current = current / part
        require(not current.is_symlink(), 'Symlink found in a release or target path.')
    if required:
        require(target.is_file(), 'A required release file is missing or not a regular file.')
    elif target.exists():
        require(target.is_file(), 'A release target collides with a directory or special file.')
    return target


def file_rows(rows, allow_content=False):
    require(isinstance(rows,list) and 0 < len(rows) <= MAX_FILES, 'Invalid release file count.')
    result = {}
    total = 0
    for row in rows:
        require(isinstance(row,dict) and {'path','size','sha256'} <= set(row) and set(row) <= {'path','size','sha256','content'} if allow_content else isinstance(row,dict) and set(row) == {'path','size','sha256'}, 'Invalid manifest file fields.')
        name = safe_path(row['path'])
        require(name not in result and type(row['size']) is int and 0 <= row['size'] <= MAX_FILE, 'Duplicate path or invalid file size.')
        require(isinstance(row['sha256'],str) and re.fullmatch('[a-f0-9]{64}',row['sha256']), 'Invalid file digest.')
        if 'content' in row:
            require(isinstance(row['content'],str), 'Invalid embedded HTML source.')
        result[name] = row
        total += row['size']
    require(total <= MAX_TOTAL, 'Release exceeds the bounded static deployment size.')
    return result


class ScriptPaths(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            source = dict(attrs).get('src')
            if source:
                parsed = urlsplit(urljoin(ORIGIN + '/',source))
                if parsed.scheme == 'https' and parsed.netloc == 'www.aptredlight.com' and parsed.path.endswith('.js'):
                    name = parsed.path.lstrip('/')
                    if name not in self.paths:
                        self.paths.append(safe_path(name))


def key_paths(release):
    parser = ScriptPaths()
    parser.feed((Path(release) / 'index.html').read_text(encoding='utf-8'))
    require(parser.paths, 'Homepage must reference at least one verifiable local JavaScript file.')
    require(len(parser.paths) <= 40, 'Too many critical script probes.')
    return ['index.html', *parser.paths]


def validate_release(release_dir, pointer):
    pointer = validate_pointer(pointer)
    root = Path(release_dir)
    require(root.is_dir() and not root.is_symlink(), 'Release directory must be a real directory.')
    manifest = load_json(regular_under(root,INDEX))
    require(isinstance(manifest,dict) and set(manifest) == {'schema','project_id','canonical_origin','release','files'}, 'Invalid Hostinger index fields.')
    require(type(manifest['schema']) is int and manifest['schema'] == 1 and manifest['project_id'] == PROJECT and manifest['canonical_origin'] == ORIGIN and manifest['release'] == pointer, 'Hostinger index does not match the pinned release.')
    indexed = file_rows(manifest['files'])
    require(INDEX not in indexed, 'Hostinger index must not list itself.')
    require({'index.html','.htaccess','source-release.json',ORIGINAL} <= set(indexed), 'Required root release files are missing from the index.')
    for name, row in indexed.items():
        path = regular_under(root,name)
        require(path.stat().st_size == row['size'] and digest(path) == row['sha256'], 'Release file size/hash mismatch.')
    original_path = regular_under(root,ORIGINAL)
    require(digest(original_path) == pointer['manifest_sha256'], 'Original Sites manifest does not match the pinned SHA256.')
    original = load_json(original_path)
    require(isinstance(original,dict) and type(original.get('schema')) is int and original.get('schema') == 1 and original.get('project_id') == PROJECT and original.get('canonical_origin') == ORIGIN and isinstance(original.get('apache_htaccess'),str), 'Invalid original Sites manifest scope.')
    original_rows = file_rows(original.get('files'),allow_content=True)
    require(not ({INDEX,ORIGINAL,'source-release.json','.htaccess'} & set(original_rows)), 'Original Sites manifest contains unexpected deployment metadata paths.')
    require(set(indexed) == set(original_rows) | {ORIGINAL,'source-release.json','.htaccess'}, 'Self-declared index differs from the pinned original file set.')
    for name, row in original_rows.items():
        require(indexed[name]['size'] == row['size'] and indexed[name]['sha256'] == row['sha256'], 'Hostinger index changes a pinned original file digest.')
        if 'content' in row:
            require(regular_under(root,name).read_bytes() == row['content'].encode('utf-8'), 'Embedded HTML differs from the pinned original bytes.')
    require(regular_under(root,'.htaccess').read_bytes() == original['apache_htaccess'].encode('utf-8'), '.htaccess differs from the pinned original settings.')
    require(load_json(regular_under(root,'source-release.json')) == pointer, 'Source record differs from the pinned release.')
    actual = set()
    for path in root.rglob('*'):
        require(not path.is_symlink(), 'Symlinks are forbidden in the release tree.')
        if path.is_dir():
            safe_path(path.relative_to(root).as_posix())
        else:
            require(path.is_file(), 'Special files are forbidden.')
            actual.add(safe_path(path.relative_to(root).as_posix()))
    require(actual == set(indexed) | {INDEX}, 'Unlisted or missing release files were found.')
    require(set(key_paths(root)) <= set(indexed), 'Critical HTML/script paths are not pinned.')
    return manifest


def target_paths(web_root, transaction_id, strict_target=True):
    root = Path(web_root)
    require(root.is_absolute() and '..' not in root.parts and str(root) == os.path.normpath(str(root)) and not str(root).startswith('//'), 'Web root must be a normalized absolute path.')
    require(re.fullmatch('[a-f0-9]{32}',transaction_id or ''), 'Transaction ID must be 32 lowercase UUID hex characters.')
    if strict_target:
        require(str(root).endswith('/domains/aptredlight.com/public_html') and USER in root.parts, 'Refusing an unrelated Hostinger document root.')
        require(pwd.getpwuid(os.geteuid()).pw_name == USER, 'SSH account is not the configured Hostinger user.')
    require(root.is_dir() and not root.is_symlink() and root.resolve() == root, 'Web root must exist without symlink ancestors.')
    require(root.stat().st_uid == os.geteuid(), 'Web root must belong to the current SSH account.')
    base = root.parent / '.aptredlight-deploy'
    require(not base.is_symlink(), 'Private deployment directory must not be a symlink.')
    if base.exists():
        require(base.is_dir() and base.stat().st_uid == os.geteuid(), 'Private deployment directory has the wrong owner.')
    base.mkdir(mode=0o700,exist_ok=True)
    os.chmod(base,0o700)
    txn = base / ('txn-' + transaction_id)
    require(not txn.is_symlink(), 'Transaction directory must not be a symlink.')
    if txn.exists():
        require(txn.is_dir() and txn.stat().st_uid == os.geteuid(), 'Transaction directory has the wrong owner.')
    txn.mkdir(mode=0o700,exist_ok=True)
    os.chmod(txn,0o700)
    return root, base, txn


def write_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp-' + uuid.uuid4().hex)
    with open(temporary,'x',encoding='utf-8') as handle:
        os.chmod(temporary,0o600)
        json.dump(value,handle,ensure_ascii=False,sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary,path)


def receipt(meta, **extra):
    release = meta.get('release',{})
    return {'status':meta.get('status'),'sites_version':release.get('sites_version'),'source_commit':release.get('source_commit'),'time':now(),'backup_id':meta.get('id'),'backup_path':meta.get('backup_path'),'http_verified':False,'rollback_status':meta.get('rollback_status','not_required'),**extra}


def lock_read(base):
    lock = base / 'lock'
    require(not lock.is_symlink() and lock.is_dir(), 'Deployment lock is unavailable.')
    require(lock.stat().st_uid == os.geteuid() and not (lock / 'owner.json').is_symlink(), 'Deployment lock owner is invalid.')
    return load_json(lock / 'owner.json')


def lock_check(base, transaction_id):
    require(lock_read(base).get('transaction_id') == transaction_id, 'Another deployment owns the cooperative lock.')


def lock_release(base, transaction_id):
    lock_check(base,transaction_id)
    (base / 'lock' / 'owner.json').unlink()
    (base / 'lock').rmdir()


def read_transaction(root, base, txn, transaction_id):
    lock_check(base,transaction_id)
    path = txn / 'transaction.json'
    require(not path.is_symlink(), 'Transaction metadata must not be a symlink.')
    meta = load_json(path)
    require(isinstance(meta,dict) and meta.get('schema') == 1 and meta.get('id') == transaction_id and meta.get('web_root') == str(root), 'Transaction target mismatch.')
    backup = txn / 'backup'
    require(meta.get('backup_path') == str(backup), 'Transaction backup path escaped its private directory.')
    require(not backup.is_symlink() and backup.is_dir() and backup.resolve() == backup and backup.stat().st_uid == os.geteuid(), 'Transaction backup directory is not a real directory owned by the SSH account.')
    for key in ('existing','missing','touched'):
        values = meta.get(key)
        require(isinstance(values,list) and len(values) <= MAX_FILES and all(isinstance(value,str) for value in values), 'Invalid transaction path list.')
        for value in values:
            safe_path(value)
        require(len(set(values)) == len(values), 'Transaction path list contains duplicates.')
    existing, missing, touched = set(meta['existing']), set(meta['missing']), set(meta['touched'])
    require(not existing.intersection(missing) and touched <= existing | missing, 'Transaction path lists are inconsistent.')
    hashes = meta.get('backup_hashes')
    require(isinstance(hashes,dict) and set(hashes) == existing, 'Transaction backup hash index is inconsistent.')
    for name, value in hashes.items():
        safe_path(name)
        require(isinstance(value,str) and re.fullmatch('[a-f0-9]{64}',value), 'Transaction backup digest is invalid.')
    manifest = load_json(txn / 'manifest.json')
    require(isinstance(manifest,dict) and existing | missing == set(file_rows(manifest.get('files'))) and manifest.get('release') == meta.get('release'), 'Transaction file scope differs from its verified manifest.')
    validate_pointer(meta.get('release'))
    validate_pointer(meta.get('old_release'))
    return meta


def unpack_archive(archive_path, staging, manifest):
    indexed = file_rows(manifest['files'])
    expected = set(indexed) | {INDEX}
    require(not staging.exists(), 'Staging directory already exists.')
    staging.mkdir(mode=0o700)
    with tarfile.open(archive_path,'r:*') as archive:
        entries = archive.getmembers()
        require(len(entries) == len(expected) and len({item.name for item in entries}) == len(entries), 'Archive has duplicate or unexpected entries.')
        require({safe_path(item.name) for item in entries} == expected and all(item.isfile() for item in entries), 'Archive must contain only indexed regular files.')
        for item in entries:
            expected_size = indexed[item.name]['size'] if item.name in indexed else item.size
            require(item.size == expected_size and item.size <= MAX_FILE, 'Archive file size differs from the verified index.')
            output = staging / item.name
            output.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
            source = archive.extractfile(item)
            require(source is not None, 'Archive file is unavailable.')
            with source, open(output,'xb') as destination:
                shutil.copyfileobj(source,destination)
            os.chmod(output,0o600)


def remote_prepare(web_root, transaction_id, manifest, archive_path, allow_downgrade=False, strict_target=True):
    root, base, txn = target_paths(web_root,transaction_id,strict_target)
    require(not (txn / 'transaction.json').exists(), 'Transaction IDs cannot be reused.')
    archive_path = Path(archive_path)
    require(archive_path.is_file() and not archive_path.is_symlink() and archive_path.resolve().parent == txn, 'Archive must be inside the private transaction directory.')
    validate_pointer(manifest.get('release'))
    acquired = False
    try:
        try:
            (base / 'lock').mkdir(mode=0o700)
        except FileExistsError:
            raise DeployError('Another deployment holds the cooperative lock; nothing was overwritten.') from None
        write_json(base / 'lock' / 'owner.json',{'transaction_id':transaction_id,'at':now()})
        acquired = True
        old = validate_pointer(load_json(regular_under(root,'source-release.json')))
        new = manifest['release']
        require(allow_downgrade or new['sites_version'] >= old['sites_version'], 'Refusing a version downgrade; use the explicit rollback command.')
        require(new['sites_version'] != old['sites_version'] or new == old, 'Same Sites version has a different source/manifest pointer.')
        staging = txn / 'staging'
        unpack_archive(archive_path,staging,manifest)
        require(validate_release(staging,new) == manifest, 'Staged index differs from the supplied verified manifest.')
        backup = txn / 'backup'
        backup.mkdir(mode=0o700)
        existing, missing, hashes = [], [], {}
        for name in file_rows(manifest['files']):
            path = regular_under(root,name,required=False)
            if path.exists():
                destination = backup / name
                destination.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
                shutil.copyfile(path,destination,follow_symlinks=False)
                os.chmod(destination,0o600)
                hashes[name] = digest(destination)
                require(hashes[name] == digest(path), 'Target changed during backup; no files were overwritten.')
                existing.append(name)
            else:
                missing.append(name)
        meta = {'schema':1,'id':transaction_id,'web_root':str(root),'status':'prepared','release':new,'old_release':old,'backup_path':str(backup),'existing':existing,'missing':missing,'backup_hashes':hashes,'touched':[],'rollback_status':'not_required','prepared_at':now()}
        write_json(txn / 'manifest.json',manifest)
        write_json(txn / 'transaction.json',meta)
        write_json(txn / 'missing-files.json',missing)
        return receipt(meta)
    except Exception:
        if acquired:
            lock_release(base,transaction_id)
        raise


def atomic_copy(source, destination):
    destination.parent.mkdir(parents=True,exist_ok=True)
    require(not destination.is_symlink(), 'Refusing to overwrite a symlink.')
    descriptor, temporary = tempfile.mkstemp(prefix='.aptredlight-',dir=destination.parent)
    try:
        with os.fdopen(descriptor,'wb') as output, open(source,'rb') as input_file:
            shutil.copyfileobj(input_file,output)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary,0o644)
        os.replace(temporary,destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def verify_applied(root, manifest):
    for name, row in file_rows(manifest['files']).items():
        path = regular_under(root,name)
        require(path.stat().st_size == row['size'] and digest(path) == row['sha256'], 'Published file verification failed.')
    require(load_json(regular_under(root,'source-release.json')) == manifest['release'], 'Published source record differs from the release.')


def remote_apply(web_root, transaction_id, strict_target=True):
    root, base, txn = target_paths(web_root,transaction_id,strict_target)
    meta = read_transaction(root,base,txn,transaction_id)
    require(meta['status'] == 'prepared', 'Transaction is not prepared.')
    manifest = load_json(txn / 'manifest.json')
    require(validate_release(txn / 'staging',meta['release']) == manifest, 'Staging changed after preparation.')
    require(load_json(regular_under(root,'source-release.json')) == meta['old_release'], 'Live source changed after preparation; nothing was overwritten.')
    for name in meta['existing']:
        require(digest(regular_under(root,name)) == meta['backup_hashes'][name], 'A live file changed after backup; nothing was overwritten.')
    for name in meta['missing']:
        require(not regular_under(root,name,required=False).exists(), 'A previously absent file appeared; nothing was overwritten.')
    meta['status'] = 'applying'
    write_json(txn / 'transaction.json',meta)
    names = sorted(file_rows(manifest['files']),key=lambda name:(name == 'source-release.json',name == '.htaccess',name))
    try:
        for name in names:
            target = regular_under(root,name,required=False)
            meta['touched'].append(name)
            write_json(txn / 'transaction.json',meta)
            atomic_copy(txn / 'staging' / name,target)
        verify_applied(root,manifest)
        meta['status'] = 'applied'
        meta['applied_at'] = now()
        write_json(txn / 'transaction.json',meta)
        return receipt(meta)
    except Exception:
        try:
            restored = remote_rollback(web_root,transaction_id,strict_target=strict_target)
        except Exception:
            raise DeployError('Apply failed and automatic restoration could not be confirmed; keep the private backup and lock.',receipt(meta,rollback_status='failed')) from None
        raise DeployError('Apply failed; the previous release was restored.',restored) from None


def remote_rollback(web_root, transaction_id, strict_target=True):
    root, base, txn = target_paths(web_root,transaction_id,strict_target)
    meta = read_transaction(root,base,txn,transaction_id)
    require(meta['status'] in ('prepared','applying','applied','rollback_failed'), 'Transaction cannot be restored in its current state.')
    try:
        manifest = load_json(txn / 'manifest.json')
        if meta['status'] == 'applied':
            require(load_json(regular_under(root,'source-release.json')) == meta['release'], 'Live source changed after apply; refusing to overwrite another release during rollback.')
            verify_applied(root,manifest)
        elif meta['status'] in ('applying','rollback_failed') and meta['touched']:
            live = load_json(regular_under(root,'source-release.json'))
            require(live in (meta['old_release'],meta['release']), 'Live source changed outside this transaction; unsafe rollback was refused.')
            indexed = file_rows(manifest['files'])
            for name in meta['touched']:
                path = regular_under(root,name,required=False)
                if path.exists():
                    allowed = {indexed[name]['sha256']}
                    if name in meta['backup_hashes']:
                        allowed.add(meta['backup_hashes'][name])
                    require(digest(path) in allowed, 'A touched file changed outside this transaction; unsafe rollback was refused.')
        names = sorted(set(meta['touched']),key=lambda name:(name == 'source-release.json',name))
        for name in names:
            target = regular_under(root,name,required=False)
            if name in meta['existing']:
                backup = regular_under(Path(meta['backup_path']),name)
                require(digest(backup) == meta['backup_hashes'][name], 'Backup digest changed; refusing unsafe restoration.')
                atomic_copy(backup,target)
                require(digest(target) == meta['backup_hashes'][name], 'Restored file digest mismatch.')
            else:
                require(name in meta['missing'], 'Unrecognized new file in restore metadata.')
                if target.exists():
                    target.unlink()
        if meta['touched']:
            require(load_json(regular_under(root,'source-release.json')) == meta['old_release'], 'Previous source record could not be restored.')
        meta['status'] = 'rolled_back'
        meta['rollback_status'] = 'rolled_back'
        meta['restored_at'] = now()
        write_json(txn / 'transaction.json',meta)
        lock_release(base,transaction_id)
        return receipt(meta)
    except Exception:
        meta['status'] = 'rollback_failed'
        meta['rollback_status'] = 'failed'
        write_json(txn / 'transaction.json',meta)
        raise DeployError('Restoration was not confirmed; private backup and cooperative lock were retained.',receipt(meta)) from None


def remote_finalize(web_root, transaction_id, strict_target=True):
    root, base, txn = target_paths(web_root,transaction_id,strict_target)
    meta = read_transaction(root,base,txn,transaction_id)
    require(meta['status'] == 'applied', 'Only an applied transaction can be finalized.')
    verify_applied(root,load_json(txn / 'manifest.json'))
    meta['status'] = 'finalized'
    meta['finalized_at'] = now()
    write_json(txn / 'transaction.json',meta)
    try:
        require(not (txn / 'staging').is_symlink(), 'Staging cleanup refuses symlinks.')
        shutil.rmtree(txn / 'staging')
        (txn / 'archive.tar').unlink()
        meta['staging_cleanup'] = 'removed_archive_and_staging'
    except (OSError,DeployError):
        meta['staging_cleanup'] = 'retained_private_cleanup_required'
    write_json(txn / 'transaction.json',meta)
    lock_release(base,transaction_id)
    return receipt(meta,staging_cleanup=meta['staging_cleanup'])


def create_archive(release, manifest, destination):
    with tarfile.open(destination,'w') as archive:
        for name in sorted(set(file_rows(manifest['files'])) | {INDEX}):
            archive.add(regular_under(Path(release),name),arcname=name,recursive=False)


class CanonicalRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlsplit(newurl)
        require(parsed.scheme == 'https' and parsed.netloc == 'www.aptredlight.com', 'HTTP verification redirected outside the canonical HTTPS site.')
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def verify_http(release, manifest, transaction_id, opener=None):
    opener = opener or build_opener(CanonicalRedirects())
    paths = ['source-release.json',*key_paths(release)]
    indexed = file_rows(manifest['files'])
    verified = []
    probes = [('source-release.json',False)] + [(name,True) for name in paths]
    for name, cache_bust in probes:
        url = ORIGIN + '/' + name
        if cache_bust:
            url += '?' + urlencode({'apt_deploy_check':transaction_id})
        request = Request(url,headers={'Cache-Control':'no-cache','Pragma':'no-cache','Accept-Encoding':'identity','User-Agent':'APTREDLIGHT-release-verifier/1.0'})
        with opener.open(request,timeout=30) as response:
            require(response.status == 200, 'Canonical HTTP verification did not return 200.')
            parsed = urlsplit(response.geturl())
            require(parsed.scheme == 'https' and parsed.netloc == 'www.aptredlight.com', 'Canonical HTTP response origin mismatch.')
            data = response.read(indexed[name]['size'] + 1)
        require(len(data) == indexed[name]['size'] and hashlib.sha256(data).hexdigest() == indexed[name]['sha256'], 'Canonical HTTP byte hash differs from the pinned release.')
        if name == 'source-release.json':
            require(json.loads(data) == manifest['release'], 'Canonical source record differs from the pinned release.')
        if name not in verified:
            verified.append(name)
    return verified


def ssh_args(args, command):
    require(args.user == USER, 'SSH user must be the verified configured user.')
    require(type(args.port) is int and 1 <= args.port <= 65535, 'Invalid SSH port.')
    require(isinstance(args.host,str) and len(args.host) <= 253 and not any(c.isspace() for c in args.host), 'Invalid SSH host.')
    try:
        ipaddress.ip_address(args.host)
    except ValueError:
        require(re.fullmatch('[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?',args.host), 'Invalid SSH hostname.')
    require(Path(args.known_hosts).is_file() and not Path(args.known_hosts).is_symlink(), 'Explicit trusted known_hosts file is required.')
    return ['ssh','-F','/dev/null','-p',str(args.port),'-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(Path(args.known_hosts).resolve()),'-o','IdentityFile=none','-o','IdentitiesOnly=no','-o','PreferredAuthentications=publickey','-o','PasswordAuthentication=no','-o','KbdInteractiveAuthentication=no','-o','ForwardAgent=no','-o','ConnectTimeout=20','--',args.user+'@'+args.host,command]


def run_remote(args, operation, transaction_id, pointer):
    encoded = base64.b64encode(json.dumps(pointer,separators=(',',':')).encode()).decode()
    command = shlex.join(['python3','-','_remote',operation,'--web-root',args.web_root,'--transaction-id',transaction_id,'--pointer-b64',encoded])
    if args.command == 'rollback':
        command += ' --allow-downgrade'
    result = subprocess.run(ssh_args(args,command),input=Path(__file__).read_bytes(),capture_output=True,timeout=300)
    try:
        value = json.loads(result.stdout)
    except (ValueError,UnicodeError):
        raise DeployError('SSH/Python3 step did not return a confirmed receipt. Python3 and shell access are required.') from None
    if result.returncode or value.get('status') == 'failed':
        raise DeployError('Remote deployment step was not confirmed.',value)
    return value


def remote_entry(args):
    pointer = validate_pointer(json.loads(base64.b64decode(args.pointer_b64)))
    root, base, txn = target_paths(args.web_root,args.transaction_id)
    if args.operation == 'bootstrap':
        require(not (txn / 'archive.tar').exists() and not (txn / 'transaction.json').exists(), 'Transaction ID has already been used.')
        return {'status':'staging_ready','archive_path':str(txn / 'archive.tar'),'http_verified':False}
    if args.operation == 'prepare':
        archive_path = txn / 'archive.tar'
        with tarfile.open(archive_path,'r:*') as archive:
            entries = archive.getmembers()
            require(len(entries) <= MAX_FILES + 1 and all(item.isfile() for item in entries), 'Archive contains unsupported entries.')
            for item in entries:
                safe_path(item.name)
            matches = [item for item in entries if item.name == INDEX]
            require(len(matches) == 1 and matches[0].size < 4 * 1024 * 1024, 'Staged index is unavailable or oversized.')
            manifest = json.load(archive.extractfile(matches[0]))
        require(manifest.get('release') == pointer, 'Remote archive pointer differs from the caller-pinned release.')
        return remote_prepare(args.web_root,args.transaction_id,manifest,archive_path,args.allow_downgrade)
    if args.operation == 'apply':
        return remote_apply(args.web_root,args.transaction_id)
    if args.operation == 'restore':
        return remote_rollback(args.web_root,args.transaction_id)
    return remote_finalize(args.web_root,args.transaction_id)


def deploy(args, manifest):
    transaction_id = uuid.uuid4().hex
    pointer = manifest['release']
    state = {'status':'failed','sites_version':pointer['sites_version'],'source_commit':pointer['source_commit'],'time':now(),'backup_id':transaction_id,'http_verified':False,'rollback_status':'not_required'}
    prepared = False
    prepare_attempted = False
    finalized = False
    try:
        bootstrap = run_remote(args,'bootstrap',transaction_id,pointer)
        expected = str(Path(args.web_root).parent / '.aptredlight-deploy' / ('txn-'+transaction_id) / 'archive.tar')
        require(bootstrap.get('archive_path') == expected, 'Unexpected remote staging destination.')
        with tempfile.TemporaryDirectory(prefix='aptredlight-deploy-') as directory:
            archive = Path(directory) / 'release.tar'
            create_archive(args.release,manifest,archive)
            command = 'umask 077; set -C; cat > ' + shlex.quote(expected)
            with archive.open('rb') as handle:
                uploaded = subprocess.run(ssh_args(args,command),stdin=handle,capture_output=True,timeout=300)
            require(uploaded.returncode == 0, 'Private staging upload was not confirmed.')
        prepare_attempted = True
        state.update(run_remote(args,'prepare',transaction_id,pointer))
        prepared = True
        state.update(run_remote(args,'apply',transaction_id,pointer))
        verified = verify_http(args.release,manifest,transaction_id)
        state.update(run_remote(args,'finalize',transaction_id,pointer))
        finalized = True
        state.update(status='rollback_release_deployed' if args.command == 'rollback' else 'deployed',http_verified=True,http_normal_source_verified=True,http_verified_paths=verified,time=now())
        return state
    except Exception as error:
        extra = error.receipt if isinstance(error,DeployError) else {}
        state.update(extra)
        if (prepared or prepare_attempted) and not finalized and state.get('rollback_status') != 'rolled_back':
            try:
                restored = run_remote(args,'restore',transaction_id,pointer)
                state.update(restored)
            except Exception:
                state['rollback_status'] = 'unconfirmed'
        state.update(status='failed',http_verified=False,time=now())
        raise DeployError('Deployment did not pass canonical HTTP verification; inspect the rollback receipt before retrying.',state) from None


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command',required=True)
    for name in ['validate','deploy','rollback']:
        command = sub.add_parser(name)
        command.add_argument('--release',required=True)
        command.add_argument('--pointer',required=True)
        command.add_argument('--receipt')
        if name != 'validate':
            command.add_argument('--host',required=True)
            command.add_argument('--port',required=True,type=int)
            command.add_argument('--user',required=True)
            command.add_argument('--web-root',required=True)
            command.add_argument('--known-hosts',required=True)
    remote = sub.add_parser('_remote',help=argparse.SUPPRESS)
    remote.add_argument('operation',choices=['bootstrap','prepare','apply','restore','finalize'])
    remote.add_argument('--web-root',required=True)
    remote.add_argument('--transaction-id',required=True)
    remote.add_argument('--pointer-b64',required=True)
    remote.add_argument('--allow-downgrade',action='store_true')
    return p


def main():
    args = parser().parse_args()
    result = None
    try:
        if args.command == '_remote':
            result = remote_entry(args)
        else:
            manifest = validate_release(args.release,load_json(args.pointer))
            if args.command == 'validate':
                result = {'status':'validated','sites_version':manifest['release']['sites_version'],'source_commit':manifest['release']['source_commit'],'files':len(manifest['files']),'time':now(),'http_verified':False,'rollback_status':'not_required'}
            else:
                result = deploy(args,manifest)
        if getattr(args,'receipt',None):
            write_json(Path(args.receipt),result)
        print(json.dumps(result,separators=(',',':')))
        return 0
    except Exception as error:
        result = error.receipt if isinstance(error,DeployError) and error.receipt else {'status':'failed','time':now(),'http_verified':False,'rollback_status':'not_required'}
        result = {**result,'status':'failed','error':str(error) if isinstance(error,DeployError) else 'Deployment step failed; no success is claimed.'}
        if getattr(args,'receipt',None):
            write_json(Path(args.receipt),result)
        print(json.dumps(result,separators=(',',':')))
        return 1


if __name__ == '__main__':
    sys.exit(main())
