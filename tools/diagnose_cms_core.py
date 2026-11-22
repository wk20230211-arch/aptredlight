#!/usr/bin/env python3
"""Read-only diagnosis for the single known failed CMS bootstrap run. No recovery writes."""
import argparse
import importlib.util
import json
from pathlib import Path
import shlex
import sys

REMOTE = r'''
import hashlib,json,os,pathlib,re,shutil,stat,subprocess,urllib.parse,urllib.request
ROOT=pathlib.Path('/home/u469397229/domains/aptredlight.com/public_html')
CMS=ROOT/'cms'
PRIVATE=pathlib.Path('/home/u469397229/.aptredlight-cms-bootstrap')
RECEIPT=PRIVATE/'receipts/run-45022484164-1.json'
PHAR=PRIVATE/'staging/run-45022484164-1/wp-cli.phar'
SHA='be928f6b8ca1e8dfb9d2f4b75a13aa4aee0896f8a9a0a1c45cd5d2c98605e6172e6d014dda2e27f88c98befc16c040cbb2bd1bfa121510ea5cdf5f6a30fe8832'
URL='https://api.wordpress.org/core/checksums/1.0/?version=7.1.5&locale=en_US'
report={'schema':1,'status':'blocked','cms_url':'https://www.aptredlight.com/cms','diagnostic_run':'45022484164-1','writes_performed':False,'official_checksums_verified':False}
class Gate(Exception): pass
def check(ok,code):
 if not ok: raise Gate(code)
def nonsymlink(path):
 check(not any(p.is_symlink() for p in (path,*path.parents)),'symlink_refused')
def safe_path(name):
 check(isinstance(name,str) and 0<len(name)<=240 and re.fullmatch(r'[A-Za-z0-9_./-]+',name) is not None,'manifest_path_invalid')
 parts=pathlib.PurePosixPath(name)
 check(not parts.is_absolute() and not any(p in ('','.','..') for p in name.split('/')),'manifest_path_invalid')
 return name
def clean(data):
 text=data.decode('utf-8','replace') if isinstance(data,bytes) else str(data)
 text=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',text)
 text=text.replace(str(CMS),'<cms>').replace(str(PRIVATE),'<private>')
 text=re.sub(r'https?://[^\s/@:]+:[^\s/@]+@','https://<redacted>@',text)
 text=re.sub(r'[A-Za-z0-9.!#$%&*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}','<email>',text)
 text=re.sub(r'(?<![0-9])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9])','<address>',text)
 return [line[:320] for line in text.splitlines() if line.strip()][:32]
class OfficialOnly(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):
  target=urllib.parse.urlsplit(newurl)
  check(target.scheme=='https' and target.hostname=='api.wordpress.org' and not target.username,'official_redirect_refused')
  return super().redirect_request(req,fp,code,msg,headers,newurl)
def official():
 opener=urllib.request.build_opener(OfficialOnly)
 try:
  with opener.open(urllib.request.Request(URL,headers={'User-Agent':'APTREDLIGHT-Core-Integrity-Diagnostic/1.0'}),timeout=35) as response:
   final=urllib.parse.urlsplit(response.geturl())
   check(final.scheme=='https' and final.hostname=='api.wordpress.org','official_origin_invalid')
   raw=response.read(2*1024*1024+1)
  check(len(raw)<=2*1024*1024,'manifest_size_limit')
  payload=json.loads(raw)
 except Gate: raise
 except Exception as exc:
  return {'status':'unavailable','error_class':type(exc).__name__}
 check(isinstance(payload,dict) and isinstance(payload.get('checksums'),dict),'manifest_shape_invalid')
 checksums=payload['checksums']
 check(100<=len(checksums)<=6000,'manifest_count_invalid')
 checked=[]
 for name,digest in checksums.items():
  safe_path(name)
  check(isinstance(digest,str) and re.fullmatch(r'[0-9a-fA-F]{32}',digest) is not None,'manifest_digest_invalid')
  checked.append((name,digest.lower()))
 matched=0;missing=[];mismatch=[];total=0
 for name,digest in checked:
  path=CMS/name
  nonsymlink(path)
  if not path.exists(): missing.append(name);continue
  check(path.is_file(),'core_file_not_regular')
  size=path.stat().st_size
  check(size<=32*1024*1024,'core_file_size_limit')
  total+=size
  check(total<=192*1024*1024,'core_total_size_limit')
  md5=hashlib.md5()
  with path.open('rb') as stream:
   while True:
    block=stream.read(1024*1024)
    if not block:break
    md5.update(block)
  if md5.hexdigest()==digest:matched+=1
  else:mismatch.append(name)
 return {'status':'verified' if not missing and not mismatch else 'mismatch','manifest_count':len(checked),'matched_count':matched,'missing_count':len(missing),'mismatch_count':len(mismatch),'missing_paths':missing[:32],'mismatch_paths':mismatch[:32],'hashed_bytes':total}
try:
 for path in (ROOT,CMS,PRIVATE,RECEIPT,PHAR):nonsymlink(path)
 check(CMS.is_dir() and RECEIPT.is_file() and PHAR.is_file(),'known_failed_install_not_found')
 check(RECEIPT.stat().st_size<=1024*1024,'receipt_size_limit')
 prior=json.loads(RECEIPT.read_text())
 check(prior.get('reason')=='core_checksums_failed' and prior.get('last_step')=='core_download' and prior.get('wordpress_installed') is False and prior.get('cms_url')==report['cms_url'],'known_receipt_mismatch')
 check(not (CMS/'wp-config.php').exists() and not (ROOT/'wp-config.php').exists(),'wp_config_present_refused')
 for path in (CMS/'wp-config.php',ROOT/'wp-config.php'):nonsymlink(path)
 ht=CMS/'.htaccess';nonsymlink(ht)
 check(ht.is_file() and ht.stat().st_size<=65536,'maintenance_missing')
 maintenance=ht.read_text()
 check('Require all denied' in maintenance and 'DirectoryIndex index.php' in maintenance,'maintenance_not_closed')
 check(hashlib.sha512(PHAR.read_bytes()).hexdigest()==SHA,'wp_cli_hash_mismatch')
 check(shutil.which('php') is not None,'php_unavailable')
 # Verify the full core tree contains no symlinks before invoking WP-CLI, which
 # scans extra files too. This never reads wp-config or traverses another domain.
 directories=0;files=0
 for current,dirs,names in os.walk(CMS,followlinks=False):
  directories+=1;files+=len(names)
  check(directories<=1500 and files<=10000,'core_tree_bound_exceeded')
  for name in dirs+names:nonsymlink(pathlib.Path(current)/name)
 env=os.environ.copy()
 for key in ('WP_CLI_PACKAGES_DIR','WP_CLI_PHP_ARGS','MYSQL_PWD','APTREDLIGHT_CMS_DATABASE','HOSTINGER_SSH_PRIVATE_KEY'):env.pop(key,None)
 env['WP_CLI_CONFIG_PATH']='/dev/null'
 command=['php',str(PHAR),'--path='+str(CMS),'--skip-plugins','--skip-themes','--skip-packages','--no-color','core','verify-checksums','--version=7.1.5','--locale=en_US']
 try:
  result=subprocess.run(command,capture_output=True,timeout=75,cwd=str(PHAR.parent),env=env,check=False)
  check(len(result.stdout)<=256*1024 and len(result.stderr)<=256*1024,'wp_cli_output_limit')
  report['wp_cli']={'exit_code':result.returncode,'stdout':clean(result.stdout),'stderr':clean(result.stderr)}
 except subprocess.TimeoutExpired:report['wp_cli']={'error_class':'TimeoutExpired'}
 report['official_manifest']=official()
 report['official_checksums_verified']=report['official_manifest'].get('status')=='verified'
 report['status']='diagnosed'
 if report['official_checksums_verified']:
  report['finding']='core_bytes_match_official_manifest' if report['wp_cli'].get('exit_code')==0 else 'wp_cli_verification_failed_but_core_bytes_match_official_manifest'
 else:report['finding']='core_integrity_not_confirmed'
 # Recheck no external process altered the closed maintenance guard/config gate.
 check(not (CMS/'wp-config.php').exists() and not (ROOT/'wp-config.php').exists(),'wp_config_changed_during_diagnostic')
 check(ht.read_text()==maintenance,'maintenance_changed_during_diagnostic')
except Gate as exc:
 report['status']='blocked';report['reason']=str(exc)
except Exception as exc:
 report['status']='blocked';report['reason']='diagnostic_exception';report['error_class']=type(exc).__name__
print(json.dumps(report,separators=(',',':')))
'''

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runner', type=Path, required=True)
    parser.add_argument('--known-hosts', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args(argv)
    spec = importlib.util.spec_from_file_location('apt_cms_runner', args.runner)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    result = runner.child(runner.ssh_arguments(args.known_hosts) + ['python3 -c ' + shlex.quote(REMOTE)], timeout=160)
    if result.returncode != 0:
        report = {'schema':1,'status':'blocked','reason':'ssh_diagnostic_failed','writes_performed':False,'exit_code':result.returncode}
    else:
        report = json.loads(result.stdout)
        if not isinstance(report, dict) or report.get('writes_performed') is not False or report.get('status') not in ('diagnosed','blocked'):
            raise ValueError('invalid_diagnostic_receipt')
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(report, indent=2) + '\n')
    args.receipt.chmod(0o600)
    print(json.dumps(report, indent=2))
    return 0 if report['status']=='diagnosed' else 3

if __name__ == '__main__':
    sys.exit(main())
