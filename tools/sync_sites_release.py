"""Mirror a pinned Sites static release to a clean production directory."""
import concurrent.futures
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import urllib.parse
import urllib.request

ORIGIN = 'https://aptredlight-wellness.wk20230211.chatgpt.site'
PROJECT = 'appgprj_6addb8c872b081918d711d7bc0c5cbf4'
pointer = json.loads(Path('.openai/site-release.json').read_text())
if pointer['source_origin'] != ORIGIN or pointer['project_id'] != PROJECT:
    raise ValueError('Release source must be the approved APTREDLIGHT Sites project')

def download(path):
    request = urllib.request.Request(ORIGIN + '/' + urllib.parse.quote(path) + '?release=' + pointer['manifest_sha256'], headers={'User-Agent': 'APTREDLIGHT-Release-Sync/1.0', 'Cache-Control': 'no-cache'})
    with urllib.request.urlopen(request, timeout=90) as response:
        if urllib.parse.urlsplit(response.url).netloc != urllib.parse.urlsplit(ORIGIN).netloc:
            raise ValueError('Unexpected redirect origin')
        return response.read(100_000_001)

raw = download('release-manifest.json')
if hashlib.sha256(raw).hexdigest() != pointer['manifest_sha256']:
    raise ValueError('Manifest hash mismatch; do not publish an unpinned release')
manifest = json.loads(raw)
if manifest['project_id'] != PROJECT or manifest['schema'] != 1:
    raise ValueError('Unexpected manifest identity or schema')
out = Path(sys.argv[1]).resolve()
out.mkdir(parents=True, exist_ok=False)
seen = set()
for item in manifest['files']:
    path = PurePosixPath(item['path'])
    if path.is_absolute() or not path.parts or any(p in {'.','..'} or p.startswith('.') for p in path.parts) or '\\' in item['path']:
        raise ValueError('Unsafe release path')
    if item['path'] in seen:
        raise ValueError('Duplicate release path')
    seen.add(item['path'])
    if not 0 <= item['size'] <= 100_000_000:
        raise ValueError('Invalid file size')
if 'index.html' not in seen or len(seen) > 5000:
    raise ValueError('Incomplete or oversized release')

def mirror(item):
    data = item['content'].encode('utf-8') if 'content' in item else download(item['path'])
    if len(data) != item['size'] or hashlib.sha256(data).hexdigest() != item['sha256']:
        raise ValueError('File verification failed: ' + item['path'])
    path = out / item['path']
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
    list(pool.map(mirror, manifest['files']))
(out / '.htaccess').write_text(manifest['apache_htaccess'])
(out / 'release-manifest.json').write_bytes(raw)
(out / 'source-release.json').write_text(json.dumps(pointer, indent=2) + '\n')
print(f'Verified {len(seen)} files for Sites version {pointer["sites_version"]}')
