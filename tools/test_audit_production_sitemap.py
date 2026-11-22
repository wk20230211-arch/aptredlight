"""Offline fixtures for public audit failures that must not produce false success."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

import audit_production_sitemap as audit


def page(url, extra=''):
    return ('<html><head><link rel="canonical" href="' + url + '">' + extra + '</head></html>').encode()


class Fixture:
    def __init__(self):
        self.pointer = dict(zip(audit.RELEASE_KEYS, (1, audit.PROJECT, 'https://example.chatgpt.site',
                                                   'abc123', 51, 'manifest123', audit.ORIGIN)))
        self.urls = [audit.ORIGIN + '/', audit.ORIGIN + '/guide.html', audit.ORIGIN + '/buyer.pdf']
        self.responses = {}
        self.calls = []
        self.set_maps()
        for url in self.urls:
            self.responses[url] = (200, {'content-type': 'text/html'}, page(url))
        self.responses[self.urls[-1]] = (200, {'content-type': 'application/pdf'}, b'%PDF-1.7')
        self.responses[audit.ORIGIN + '/robots.txt'] = (200, {},
            ('User-agent: *\nAllow: /\nSitemap: ' + audit.ORIGIN + '/sitemap.xml\n').encode())
        self.responses[audit.ORIGIN + '/source-release.json'] = (200, {}, json.dumps(self.pointer).encode())
        for directory in audit.INDEX_DIRS:
            query = '?utm_source=seo-check'
            source, target = audit.ORIGIN + directory + 'index.html' + query, audit.ORIGIN + directory + query
            self.responses[source] = (301, {'location': target}, b'')
            self.responses[target] = (200, {'content-type': 'text/html'}, page(audit.ORIGIN + directory))
        for source, target in audit.LEGACY.items():
            self.responses[audit.ORIGIN + source] = (301, {'location': target}, b'')
            final = audit.ORIGIN + target.split('#')[0]
            self.responses.setdefault(final, (200, {'content-type': 'text/html'}, page(final)))

    def set_maps(self):
        content = '<urlset xmlns="' + audit.NS[1:-1] + '">' + ''.join(
            '<url><loc>' + url + '</loc></url>' for url in self.urls) + '</urlset>'
        index = '<sitemapindex xmlns="' + audit.NS[1:-1] + '"><sitemap><loc>' + audit.ORIGIN + '/sitemap.xml</loc></sitemap></sitemapindex>'
        self.responses[audit.ORIGIN + '/sitemap.xml'] = (200, {}, content.encode())
        self.responses[audit.ORIGIN + '/wp-sitemap.xml'] = (200, {}, index.encode())

    def fetch(self, url, pdf_head=False):
        self.calls.append((url, pdf_head))
        return self.responses[url]

    def run(self):
        return audit.Audit(self.pointer, self.fetch).run()


class AuditFixtures(unittest.TestCase):
    def test_arbitrary_sitemap_size_and_pdf_head(self):
        fixture = Fixture()
        report = fixture.run()
        self.assertEqual(report['status'], 'passed', report)
        self.assertEqual(report['sitemap_url_count'], 3)
        self.assertIn((fixture.urls[-1], True), fixture.calls)
        self.assertEqual(report['gsc_validation'], 'not_checked')
        self.assertFalse(any('#' in url for url, _ in fixture.calls))

    def test_noncanonical_and_duplicate_sitemap_urls(self):
        for bad in ('http://www.aptredlight.com/', 'https://aptredlight.com/',
                    'https://www.aptredlight.com/index.html', 'https://www.aptredlight.com/?x=1',
                    'https://www.aptredlight.com/#part', audit.ORIGIN + '/'):
            with self.subTest(bad=bad):
                fixture = Fixture()
                fixture.urls.append(bad)
                fixture.set_maps()
                self.assertEqual(fixture.run()['status'], 'failed')

    def test_each_sitemap_content_record_requires_one_location(self):
        for record in ('<url/>', '<url><loc>' + audit.ORIGIN + '/</loc><loc>' + audit.ORIGIN + '/other</loc></url>'):
            fixture = Fixture()
            fixture.responses[audit.ORIGIN + '/sitemap.xml'] = (200, {},
                ('<urlset xmlns="' + audit.NS[1:-1] + '">' + record + '</urlset>').encode())
            self.assertEqual(fixture.run()['status'], 'failed')

    def test_html_exclusions_and_conflicting_canonical(self):
        for extra in ('<meta name="robots" content="none">', '<meta name="Googlebot" content="noindex">',
                      '<meta http-equiv="refresh" content="0;url=/">', '<link rel="canonical" href="/other">'):
            with self.subTest(extra=extra):
                fixture = Fixture()
                url = fixture.urls[1]
                fixture.responses[url] = (200, {'content-type': 'text/html'}, page(url, extra))
                self.assertEqual(fixture.run()['status'], 'failed')

    def test_missing_canonical_xrobots_and_bad_pdf(self):
        for body, headers in ((b'<html></html>', {'content-type': 'text/html'}),
                              (page(audit.ORIGIN + '/guide.html'), {'content-type': 'text/html', 'x-robots-tag': 'Googlebot: noindex'})):
            fixture = Fixture()
            fixture.responses[fixture.urls[1]] = (200, headers, body)
            self.assertEqual(fixture.run()['status'], 'failed')
        fixture = Fixture()
        fixture.responses[fixture.urls[-1]] = (200, {}, b'not pdf')
        self.assertEqual(fixture.run()['status'], 'failed')

    def test_sitemap_content_must_not_redirect(self):
        fixture = Fixture()
        fixture.responses[fixture.urls[1]] = (301, {'location': audit.ORIGIN + '/'}, b'')
        self.assertEqual(fixture.run()['status'], 'failed')

    def test_index_query_loss_302_extra_hop_and_external_location(self):
        source = audit.ORIGIN + '/index.html?utm_source=seo-check'
        for status, location in ((301, '/'), (302, '/?utm_source=seo-check'),
                                 (301, 'https://other.example/')):
            fixture = Fixture()
            fixture.responses[source] = (status, {'location': location}, b'')
            self.assertEqual(fixture.run()['status'], 'failed')
        fixture = Fixture()
        fixture.responses[audit.ORIGIN + '/?utm_source=seo-check'] = (301, {'location': '/'}, b'')
        self.assertEqual(fixture.run()['status'], 'failed')

    def test_legacy_location_fragment_must_match(self):
        fixture = Fixture()
        fixture.responses[audit.ORIGIN + '/catalog.html'] = (301, {'location': '/'}, b'')
        self.assertEqual(fixture.run()['status'], 'failed')

    def test_robots_blocks_and_compatibility_sitemap(self):
        for rules in ('User-agent: *\nDisallow: /\n', 'User-agent: Googlebot\nDisallow: /*.html$\n'):
            fixture = Fixture()
            fixture.responses[audit.ORIGIN + '/robots.txt'] = (200, {},
                (rules + 'Sitemap: ' + audit.ORIGIN + '/sitemap.xml\n').encode())
            self.assertEqual(fixture.run()['status'], 'failed')
        fixture = Fixture()
        fixture.responses[audit.ORIGIN + '/wp-sitemap.xml'] = (200, {}, b'<urlset/>')
        self.assertEqual(fixture.run()['status'], 'failed')

    def test_google_robots_longest_rule_and_specific_group(self):
        rules = 'User-agent: *\nDisallow: /\nUser-agent: Googlebot\nDisallow: /private/*\nAllow: /private/public$\n'
        self.assertTrue(audit.googlebot_allowed(rules, audit.ORIGIN + '/guide.html'))
        self.assertFalse(audit.googlebot_allowed(rules, audit.ORIGIN + '/private/a'))
        self.assertTrue(audit.googlebot_allowed(rules, audit.ORIGIN + '/private/public'))

    def test_googlebot_empty_disallow_overrides_wildcard_and_adjacent_agents_share_rules(self):
        for rules in ('User-agent: *\nDisallow: /\nUser-agent: Googlebot\nDisallow:\n',
                      'User-agent: Googlebot\nDisallow:\nUser-agent: *\nDisallow: /\n'):
            self.assertTrue(audit.googlebot_allowed(rules, audit.ORIGIN + '/guide.html'))
        shared = 'User-agent: Googlebot\nUser-agent: Bingbot\nDisallow: /private/\n'
        self.assertFalse(audit.googlebot_allowed(shared, audit.ORIGIN + '/private/a'))

    def test_release_mismatch_before_or_during_audit(self):
        for change_after in (False, True):
            fixture = Fixture()
            calls = 0
            original = fixture.fetch
            def fetch(url, pdf_head=False):
                nonlocal calls
                if url.endswith('/source-release.json'):
                    calls += 1
                    if not change_after or calls > 1:
                        return 200, {}, json.dumps({**fixture.pointer, 'sites_version': 52}).encode()
                return original(url, pdf_head)
            report = audit.Audit(fixture.pointer, fetch).run()
            self.assertEqual(report['status'], 'release_mismatch')
            self.assertEqual(report['expected_release']['sites_version'], 51)

    def test_network_failure_is_reported(self):
        def broken(*args, **kwargs):
            raise TimeoutError('fixture timeout')
        report = audit.Audit(Fixture().pointer, broken).run()
        self.assertEqual(report['status'], 'failed')
        self.assertIn('fixture timeout', report['errors'][0])

    def test_cli_missing_pointer_still_writes_report(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'report.json'
            with patch.object(audit.sys, 'argv', ['audit', '--release-pointer', directory + '/missing', '--output', str(output)]):
                self.assertEqual(audit.main(), 1)
            self.assertEqual(json.loads(output.read_text())['status'], 'failed')


class ClientFixtures(unittest.TestCase):
    def test_301_http_error_preserves_location(self):
        error = urllib.error.HTTPError(audit.ORIGIN + '/index.html', 301, 'moved', {'Location': '/'}, io.BytesIO(b''))
        with patch.object(audit.urllib.request, 'build_opener') as opener:
            opener.return_value.open.side_effect = error
            status, headers, data = audit.HttpClient()(audit.ORIGIN + '/index.html')
        self.assertEqual((status, headers['location']), (301, '/'))

    def test_pdf_read_only_8_bytes_and_large_html_rejected(self):
        class Response(io.BytesIO):
            status = 200
            headers = {'Content-Type': 'application/pdf'}
            def read(self, size=-1):
                self.requested = size
                return super().read(size)
        response = Response(b'%PDF-1.7' + b'x' * (audit.MAX_BODY + 10))
        with patch.object(audit.urllib.request, 'build_opener') as opener:
            opener.return_value.open.return_value = response
            data = audit.HttpClient()(audit.ORIGIN + '/large.pdf', pdf_head=True)[2]
        self.assertEqual(len(data), 8)
        self.assertEqual(response.requested, 8)
        response = Response(b'x' * (audit.MAX_BODY + 10))
        with patch.object(audit.urllib.request, 'build_opener') as opener:
            opener.return_value.open.return_value = response
            with self.assertRaisesRegex(ValueError, 'size limit'):
                audit.HttpClient()(audit.ORIGIN + '/large.html')

    def test_deadline_and_foreign_origin_rejected_before_network(self):
        client = audit.HttpClient()
        client.deadline = 0
        with patch.object(audit.urllib.request, 'build_opener') as opener:
            with self.assertRaises(TimeoutError):
                client(audit.ORIGIN + '/')
            with self.assertRaises(ValueError):
                audit.HttpClient()('https://other.example/')
            opener.assert_not_called()


if __name__ == '__main__':
    unittest.main()
