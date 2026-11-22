"""Bounded, public-only HTTP checks; these do not establish Google indexing."""
import argparse
import concurrent.futures
import datetime
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse as urlparse
import urllib.request
import xml.etree.ElementTree as ET

ORIGIN = 'https://www.aptredlight.com'
PROJECT = 'appgprj_6addb8c872b081918d711d7bc0c5cbf4'
NS = '{http://www.sitemaps.org/schemas/sitemap/0.9}'
RELEASE_KEYS = ('schema', 'project_id', 'source_origin', 'source_commit',
                'sites_version', 'manifest_sha256', 'canonical_origin')
MAX_BODY = 2 * 1024 * 1024
LEGACY = {
    '/catalog.html': '/#collection', '/quality-process.html': '/#quality',
    '/rfq.html': '/#rfq-contact', '/products/t300-ultra.html': '/products/t300.html',
    '/products/a13-pro.html': '/products/a13.html',
    '/products/mask.html': '/products/smart-voice-mask.html',
    '/products/mat.html': '/products/light-mat.html',
}
INDEX_DIRS = ('/', '/de/', '/es/', '/fr/', '/guides/', '/solutions/', '/zh-CN/')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def trusted_url(url):
    parsed = urlparse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.netloc != 'www.aptredlight.com':
        raise ValueError('Unexpected public audit origin: ' + url)
    return parsed


class HttpClient:
    def __init__(self, seconds=420):
        self.deadline = time.monotonic() + seconds

    def __call__(self, url, pdf_head=False):
        trusted_url(url)
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Public audit total deadline reached')
        request = urllib.request.Request(url, headers={
            'User-Agent': 'APTREDLIGHT-Indexability-Audit/1.0',
            'Accept-Encoding': 'identity', 'Cache-Control': 'no-cache'})
        try:
            response = urllib.request.build_opener(NoRedirect).open(
                request, timeout=min(18, remaining))
        except urllib.error.HTTPError as error:
            response = error  # Preserve a 301 status and its Location.
        with response:
            if pdf_head:
                data = response.read(8)
            else:
                parts, size = [], 0
                while True:
                    if time.monotonic() >= self.deadline:
                        raise TimeoutError('Public audit total deadline reached')
                    chunk = response.read(min(16384, MAX_BODY + 1 - size))
                    if not chunk:
                        break
                    parts.append(chunk)
                    size += len(chunk)
                    if size > MAX_BODY:
                        raise ValueError('HTML/XML/JSON body exceeds audit size limit')
                data = b''.join(parts)
            return response.status, {k.lower(): v for k, v in response.headers.items()}, data


class Signals(HTMLParser):
    def __init__(self):
        super().__init__()
        self.canonicals, self.robots, self.refresh = [], [], False

    def handle_starttag(self, tag, attrs):
        attrs = {k.lower(): v or '' for k, v in attrs}
        if tag == 'link' and 'canonical' in attrs.get('rel', '').lower().split():
            self.canonicals.append(attrs.get('href', ''))
        if tag == 'meta':
            if attrs.get('name', '').lower() in ('robots', 'googlebot'):
                self.robots.append(attrs.get('content', ''))
            if attrs.get('http-equiv', '').lower() == 'refresh':
                self.refresh = True


def excluded(value):
    return bool(re.search(r'\b(?:noindex|none)\b', value.lower()))


def googlebot_allowed(robots, url):
    """Googlebot group selection, * / $ patterns, longest rule, Allow on ties."""
    groups, agents, rules, rule_directive_seen = [], [], [], False
    for raw in robots.splitlines() + ['User-agent: __end__']:
        line = raw.split('#', 1)[0].strip()
        if ':' not in line:
            continue
        name, value = [part.strip() for part in line.split(':', 1)]
        name = name.lower()
        if name == 'user-agent':
            if rule_directive_seen:
                groups.append((agents, rules))
                agents, rules, rule_directive_seen = [], [], False
            agents.append(value.lower())
        elif name in ('allow', 'disallow') and agents:
            rule_directive_seen = True
            if value:
                rules.append((name == 'allow', value))
    matches = []
    for agents, rules in groups:
        specificity = max((0 if a == '*' else len(a) for a in agents
                           if a == '*' or a in 'googlebot'), default=-1)
        if specificity >= 0:
            matches.append((specificity, rules))
    if not matches:
        return True
    selected = max(score for score, _ in matches)
    parsed = urlparse.urlsplit(url)
    path = parsed.path + ('?' + parsed.query if parsed.query else '')
    applicable = []
    for score, rules in matches:
        if score != selected:
            continue
        for allow, pattern in rules:
            end = pattern.endswith('$')
            body = pattern[:-1] if end else pattern
            regex = '^' + re.escape(body).replace(r'\*', '.*') + ('$' if end else '')
            if re.search(regex, path):
                applicable.append((len(body.replace('*', '').encode('utf-8')), allow))
    return max(applicable)[1] if applicable else True


class Audit:
    def __init__(self, pointer, fetch):
        self.pointer, self.fetch = dict(pointer), fetch
        self.report = {'checked_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                       'canonical_origin': ORIGIN, 'gsc_validation': 'not_checked',
                       'scope': 'Public HTTP prerequisites; not a Google indexing verdict',
                       'expected_release': self.pointer, 'results': [], 'errors': []}

    def direct(self, url, pdf_head=False):
        trusted_url(url)
        status, headers, data = self.fetch(url, pdf_head=pdf_head)
        if status != 200:
            raise ValueError('Expected direct HTTP 200: ' + url + ' (received ' + str(status) + ')')
        return headers, data

    def check_release(self, phase):
        _, data = self.direct(ORIGIN + '/source-release.json')
        release = json.loads(data)
        self.report['live_release_' + phase] = release
        if any(release.get(key) != self.pointer.get(key) for key in RELEASE_KEYS):
            self.report['release_mismatch'] = True

    def document(self, url):
        result = {'url': url, 'kind': 'sitemap_content', 'errors': []}
        try:
            pdf = urlparse.urlsplit(url).path.lower().endswith('.pdf')
            headers, data = self.direct(url, pdf_head=pdf)
            result['http_status'] = 200
            if excluded(headers.get('x-robots-tag', '')):
                raise ValueError('X-Robots-Tag excludes indexing')
            if pdf:
                if not data.startswith(b'%PDF-'):
                    raise ValueError('PDF URL did not return a PDF header')
            else:
                if 'text/html' not in headers.get('content-type', '').lower():
                    raise ValueError('Unexpected HTML Content-Type')
                signals = Signals()
                signals.feed(data.decode('utf-8-sig'))
                result['canonicals'] = signals.canonicals
                if signals.canonicals != [url]:
                    raise ValueError('Missing, duplicate, or conflicting canonical')
                if signals.refresh or any(excluded(value) for value in signals.robots):
                    raise ValueError('HTML contains noindex or meta refresh')
        except Exception as error:
            result['errors'].append(str(error))
        return result

    def alias(self, pair):
        source, target = pair
        result = {'url': source, 'expected_location': target, 'kind': 'redirect', 'errors': []}
        try:
            trusted_url(source)
            status, headers, _ = self.fetch(source)
            location = urlparse.urljoin(source, headers.get('location', ''))
            result.update(http_status=status, location=location)
            if status != 301 or location != target:
                raise ValueError('Expected one HTTP 301 to the exact canonical target')
            self.direct(urlparse.urldefrag(location)[0])
        except Exception as error:
            result['errors'].append(str(error))
        return result

    def run(self):
        try:
            if self.pointer.get('project_id') != PROJECT or self.pointer.get('canonical_origin') != ORIGIN:
                raise ValueError('Unexpected repository release identity')
            self.check_release('before')
            _, data = self.direct(ORIGIN + '/sitemap.xml')
            root = ET.fromstring(data)
            if root.tag != NS + 'urlset':
                raise ValueError('Primary sitemap must be a content URL urlset')
            if any(len(node.findall(NS + 'loc')) != 1 for node in root.findall(NS + 'url')):
                raise ValueError('Each sitemap content record must have exactly one loc')
            urls = [(node.text or '').strip() for node in root.findall(NS + 'url/' + NS + 'loc')]
            if not urls or len(urls) != len(set(urls)) or len(urls) > 1000:
                raise ValueError('Empty, duplicate, or over-limit sitemap (split audits above 1000 URLs)')
            for url in urls:
                parsed = trusted_url(url)
                if parsed.query or parsed.fragment or parsed.path.endswith('/index.html'):
                    raise ValueError('Noncanonical sitemap content URL: ' + url)
            self.report['sitemap_url_count'] = len(urls)
            _, data = self.direct(ORIGIN + '/robots.txt')
            robots = data.decode('utf-8-sig')
            if not re.search(r'(?im)^sitemap:\s*https://www\.aptredlight\.com/sitemap\.xml\s*$', robots):
                raise ValueError('robots.txt must advertise the canonical sitemap')
            if any(not googlebot_allowed(robots, url) for url in urls):
                raise ValueError('robots.txt blocks Googlebot from a sitemap content URL')
            _, data = self.direct(ORIGIN + '/wp-sitemap.xml')
            root = ET.fromstring(data)
            if (root.tag != NS + 'sitemapindex' or
                    [node.text for node in root.findall(NS + 'sitemap/' + NS + 'loc')] != [ORIGIN + '/sitemap.xml']):
                raise ValueError('Compatibility sitemap index must point only to the primary sitemap')
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                self.report['results'].extend(pool.map(self.document, urls))
            query = '?utm_source=seo-check'
            aliases = [(ORIGIN + directory + 'index.html' + query,
                        ORIGIN + directory + query) for directory in INDEX_DIRS]
            aliases += [(ORIGIN + source, ORIGIN + target) for source, target in LEGACY.items()]
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                self.report['results'].extend(pool.map(self.alias, aliases))
            self.check_release('after')
        except Exception as error:
            self.report['errors'].append(str(error))
        for result in self.report['results']:
            self.report['errors'].extend(result['url'] + ': ' + error for error in result['errors'])
        self.report['status'] = ('release_mismatch' if self.report.get('release_mismatch') else
                                 'failed' if self.report['errors'] else 'passed')
        return self.report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--release-pointer', default='.openai/site-release.json')
    parser.add_argument('--max-seconds', type=int, default=420)
    args = parser.parse_args()
    try:
        # Read once: concurrent main updates cannot silently change our expected release.
        pointer = json.loads(Path(args.release_pointer).read_text(encoding='utf-8'))
        report = Audit(pointer, HttpClient(max(1, min(args.max_seconds, 420)))).run()
    except Exception as error:
        report = {'checked_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  'status': 'failed', 'gsc_validation': 'not_checked', 'errors': [str(error)]}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key != 'results'}, ensure_ascii=False))
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
