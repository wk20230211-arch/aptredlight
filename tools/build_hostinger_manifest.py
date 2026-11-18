"""Seal the verified static release as a deterministic Hostinger deployment artifact."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath

PROJECT = 'appgprj_6addb8c872b081918d711d7bc0c5cbf4'
ORIGIN = 'https://www.aptredlight.com'
INDEX = 'hostinger-release-manifest.json'

def seal(release, pointer_path):
    release = Path(release).resolve()
    pointer = json.loads(Path(pointer_path).read_text())
    if pointer.get('project_id') != PROJECT or pointer.get('canonical_origin') != ORIGIN:
        raise ValueError('The pinned release is not the approved APTREDLIGHT project')
    raw = (release / 'release-manifest.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != pointer.get('manifest_sha256'):
        raise ValueError('Unpinned Sites release manifest')
    manifest = json.loads(raw)
    if manifest.get('schema') != 1 or manifest.get('project_id') != PROJECT or manifest.get('canonical_origin') != ORIGIN:
        raise ValueError('Unexpected Sites release identity')
    expected = {'.htaccess', 'source-release.json', 'release-manifest.json'}
    for item in manifest['files']:
        name = item['path']; path = PurePosixPath(name)
        if not name or path.is_absolute() or path.as_posix() != name or '\\' in name or any(p in {'.', '..'} or p.startswith('.') for p in path.parts):
            raise ValueError('Unsafe release path')
        if name in expected:
            raise ValueError('Duplicate or reserved release path')
        expected.add(name)
        file = release / name
        if file.is_symlink() or not file.is_file():
            raise ValueError('Missing file or symlink in release')
        contents = file.read_bytes()
        if len(contents) != item['size'] or hashlib.sha256(contents).hexdigest() != item['sha256']:
            raise ValueError('Release checksum mismatch: ' + name)
        if 'content' in item and contents != item['content'].encode('utf-8'):
            raise ValueError('Inline content mismatch: ' + name)
    if (release / '.htaccess').read_bytes() != manifest['apache_htaccess'].encode('utf-8'):
        raise ValueError('Apache configuration differs from the pinned release')
    if json.loads((release / 'source-release.json').read_text()) != pointer:
        raise ValueError('Release receipt differs from the pinned source')
    actual = set()
    for file in release.rglob('*'):
        if file.is_symlink():
            raise ValueError('Release contains a symlink')
        if file.is_file() and file.relative_to(release).as_posix() != INDEX:
            actual.add(file.relative_to(release).as_posix())
    if actual != expected:
        raise ValueError('Unexpected or missing files in the deployment artifact')
    files = []
    for name in sorted(actual):
        contents = (release / name).read_bytes()
        files.append({'path': name, 'size': len(contents), 'sha256': hashlib.sha256(contents).hexdigest()})
    result = {'schema': 1, 'project_id': PROJECT, 'canonical_origin': ORIGIN, 'release': pointer, 'files': files}
    (release / INDEX).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return result

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--release', required=True)
    parser.add_argument('--pointer', required=True)
    args = parser.parse_args()
    result = seal(args.release, args.pointer)
    print(json.dumps({'sites_version': result['release']['sites_version'], 'files': len(result['files']), 'checksum_index': INDEX}))
