"""Behavior of the actual static image; run via tests/run_health.py."""
import os
import unittest

from docker_support import container, docker, image_config, probe, wait_http


class StaticImageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.image = os.environ.get('MMJ_WEB_TEST_IMAGE')
        if not cls.image:
            raise RuntimeError('Run python3 tests/run_health.py to build the candidate images')

    def test_probe_fails_when_required_stylesheet_is_missing(self):
        with container(self.image) as name:
            wait_http(name)
            self.assertEqual(probe(name, self.image).returncode, 0)
            docker('exec', name, 'rm', '/usr/share/nginx/html/styles.css')
            failed = probe(name, self.image)
            self.assertNotEqual(failed.returncode, 0,
                                'a working index must not hide a missing required stylesheet')

    def test_root_readiness_response_is_not_cacheable(self):
        with container(self.image) as name:
            wait_http(name)
            response = docker('exec', name, 'curl', '-q', '--noproxy', '*',
                              '--silent', '--max-time', '1', '--dump-header', '-',
                              '--output', '/dev/null', 'http://127.0.0.1/')
            self.assertIn('cache-control: no-store\r\n',
                          response.stdout.lower().replace('\n', '\r\n'))

    def test_final_image_has_bounded_probe_and_its_executables(self):
        health = image_config(self.image)['Healthcheck']
        self.assertEqual(health['Test'], ['CMD', '/usr/local/bin/mmj-web-health'])
        self.assertEqual(health['Interval'], 30_000_000_000)
        self.assertEqual(health['Timeout'], 5_000_000_000)
        self.assertEqual(health['StartPeriod'], 60_000_000_000)
        self.assertEqual(health['Retries'], 3)
        with container(self.image) as name:
            wait_http(name)
            docker('exec', name, 'sh', '-c',
                   'test -x /usr/local/bin/mmj-web-health; '
                   'command -v curl; command -v cmp; command -v mktemp')
            self.assertEqual(probe(name, self.image).returncode, 0)

    def test_each_required_file_is_served_byte_for_byte(self):
        with container(self.image) as name:
            wait_http(name)
            for path, file in (('/', 'index.html'), ('/styles.css', 'styles.css'),
                               ('/main.js', 'main.js')):
                with self.subTest(path=path):
                    actual = docker('exec', name, 'curl', '-q', '--noproxy', '*',
                                    '--silent', '--max-time', '1',
                                    '--write-out', '\n%{http_code}', 'http://127.0.0.1' + path)
                    body, status = actual.stdout.rsplit('\n', 1)
                    self.assertEqual(status, '200')
                    expected = docker('exec', name, 'cat', '/usr/share/nginx/html/' + file)
                    self.assertEqual(body, expected.stdout)
            missing = docker('exec', name, 'curl', '-q', '--noproxy', '*', '--silent',
                             '--max-time', '1', '--output', '/dev/null', '--write-out',
                             '%{http_code}', 'http://127.0.0.1/not-a-real-mmj-file')
            self.assertEqual(missing.stdout, '404')

    def test_missing_index_or_javascript_fails_probe(self):
        for file in ('index.html', 'main.js'):
            with self.subTest(file=file), container(self.image) as name:
                wait_http(name)
                docker('exec', name, 'rm', '/usr/share/nginx/html/' + file)
                self.assertNotEqual(probe(name, self.image).returncode, 0)

    def test_empty_asset_fails_probe(self):
        with container(self.image) as name:
            wait_http(name)
            docker('exec', name, 'truncate', '-s', '0', '/usr/share/nginx/html/main.js')
            self.assertNotEqual(probe(name, self.image).returncode, 0)

    def test_wrong_http_bodies_redirects_and_fake_404_fail_probe(self):
        fixtures = {
            'wrong-body': 'location = /styles.css { return 200 "not the stylesheet"; }',
            'redirect': 'location = /styles.css { return 302 /main.js; }',
            'missing-endpoint': 'location = /styles.css { return 404; }',
            'fake-404': 'location = /__mmj_health_missing__ { return 200 "not found"; }',
        }
        for case, location in fixtures.items():
            config = ('server { listen 80; root /usr/share/nginx/html; index index.html; '
                      'location / { try_files $uri $uri/ =404; } ' + location + ' }')
            command = ('-c', 'printf %s "$1" > /etc/nginx/conf.d/default.conf; '
                       'exec nginx -g "daemon off;"', 'fixture', config)
            with self.subTest(case=case), container(self.image, entrypoint='sh', command=command) as name:
                wait_http(name)
                self.assertNotEqual(probe(name, self.image).returncode, 0)

    def test_probe_ignores_proxy_environment(self):
        proxies = {key: 'http://192.0.2.1:9' for key in (
            'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy')}
        proxies.update({'NO_PROXY': '', 'no_proxy': ''})
        with container(self.image) as name:
            wait_http(name)
            self.assertEqual(probe(name, self.image, environment=proxies).returncode, 0)

    def test_preview_noindex_header_is_preserved(self):
        with container(self.image) as name:
            wait_http(name)
            headers = docker('exec', name, 'curl', '-q', '--noproxy', '*', '--silent',
                             '--max-time', '1', '--dump-header', '-', '--output', '/dev/null',
                             '--header', 'Host: preview.sslip.io', 'http://127.0.0.1/')
            self.assertIn('x-robots-tag: noindex, nofollow', headers.stdout.lower())


if __name__ == '__main__':
    unittest.main()
