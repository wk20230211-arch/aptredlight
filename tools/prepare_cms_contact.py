"""Prepare only a task-scoped RSA public contact channel over owner-pinned SSH."""
import argparse,json,pathlib,shlex,sys
from run_cms_bootstrap import child,ssh_arguments,SetupError
REMOTE=r'''import base64,fcntl,hashlib,json,os,pathlib,subprocess,tempfile
base=pathlib.Path('/home/u469397229/.aptredlight-cms-bootstrap')
assert not any(p.is_symlink() for p in (base,*base.parents))
assert os.getuid()==pathlib.Path('/home/u469397229').stat().st_uid
base.mkdir(mode=0o700,exist_ok=True)
assert base.is_dir() and base.stat().st_uid==os.getuid()
os.chmod(base,0o700)
lock=os.open(base/'.admin-contact.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
key=base/'admin-contact-private.pem'
if not key.exists():
 p=subprocess.run(['openssl','genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:3072'],capture_output=True,timeout=30,check=False)
 assert p.returncode==0 and b'PRIVATE KEY' in p.stdout
 fd=os.open(key,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'wb') as out:out.write(p.stdout)
assert not key.is_symlink() and key.is_file() and key.stat().st_uid==os.getuid() and key.stat().st_mode&0o777==0o600
pub=subprocess.run(['openssl','pkey','-in',str(key),'-pubout'],capture_output=True,timeout=10,check=False)
der=subprocess.run(['openssl','pkey','-pubin','-outform','DER'],input=pub.stdout,capture_output=True,timeout=10,check=False)
assert pub.returncode==0 and der.returncode==0 and b'BEGIN PUBLIC KEY' in pub.stdout
print(json.dumps({'schema':1,'status':'contact_channel_prepared','origin':'https://www.aptredlight.com/cms','key_sha256':hashlib.sha256(der.stdout).hexdigest(),'public_key_b64':base64.b64encode(pub.stdout).decode(),'website_files_modified':False,'database_modified':False},separators=(',',':')))
os.close(lock)
'''
def main():
 p=argparse.ArgumentParser();p.add_argument('--known-hosts',type=pathlib.Path,required=True);a=p.parse_args()
 try:
  result=child(ssh_arguments(a.known_hosts)+['python3 -c '+shlex.quote(REMOTE)],data=b'',timeout=60)
  if result.returncode:raise SetupError('contact_channel_preparation_failed')
  value=json.loads(result.stdout)
  if value.get('status')!='contact_channel_prepared' or value.get('origin')!='https://www.aptredlight.com/cms' or len(value.get('public_key_b64',''))>2000:raise SetupError('contact_public_receipt_invalid')
  print(json.dumps(value,separators=(',',':')))
 except Exception:
  print('{"status":"blocked","reason":"contact_channel_preparation_failed"}');return 1
 return 0
if __name__=='__main__':sys.exit(main())
