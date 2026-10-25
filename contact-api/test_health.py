"""Real HTTP handler tests with synthetic settings and forbidden mail/writes.

HTTPServer handles one queued request synchronously: tests and health routes
never start a thread or connect to an SMTP server.
"""
from contextlib import ExitStack
import http.client
from http.server import HTTPServer
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class ContactHealthTests(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.directory = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix='mmj-health-')))
        settings = {
            'HOST': '127.0.0.1', 'PORT': '8471',
            'SMTP_HOST': 'smtp.example.invalid', 'SMTP_PORT': '587',
            'SMTP_USER': 'sender@example.invalid', 'SMTP_PASS': 'synthetic-not-a-secret',
            'FROM_EMAIL': 'sender@example.invalid', 'TO_EMAIL': 'recipient@example.invalid',
            'ALLOWED_ORIGINS': 'https://site.example.invalid',
            'STORE_FILE': str(self.directory / 'must-not-exist.jsonl'),
            'LOG_FILE': str(self.directory / 'must-not-exist.log'),
        }
        spec = importlib.util.spec_from_file_location('mmj_contact_under_test',
                                                       Path(__file__).with_name('app.py'))
        self.app = importlib.util.module_from_spec(spec)
        with patch.dict(os.environ, settings, clear=True):
            spec.loader.exec_module(self.app)
        self.forbidden = []
        for target in ('enviar_correo', 'guardar_mensaje', 'log'):
            self.forbidden.append(stack.enter_context(patch.object(
                self.app, target, side_effect=AssertionError('health must not send or write'))))
        for target in ('smtplib.SMTP.sendmail', 'smtplib.SMTP.send_message',
                       'smtplib.SMTP', 'smtplib.SMTP_SSL', 'threading.Thread.start'):
            self.forbidden.append(stack.enter_context(patch(
                target, side_effect=AssertionError('health must not connect/send/start threads'))))
        self.server = HTTPServer(('127.0.0.1', 0), self.app.Handler)
        self.server.timeout = 0.5
        stack.callback(self.server.server_close)

    def tearDown(self):
        for forbidden in self.forbidden:
            forbidden.assert_not_called()
        self.assertEqual(list(self.directory.iterdir()), [])
        self.assertEqual(self.app._intentos, {})

    def request(self, path, *, method='GET', headers=None):
        client = http.client.HTTPConnection(*self.server.server_address, timeout=1)
        try:
            client.request(method, path, headers=headers or {})
            self.server.handle_request()
            response = client.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            client.close()

    def test_salud_preserves_public_format_without_configuration(self):
        self.app.SMTP_HOST = ''
        self.app.SMTP_USER = ''
        self.app.SMTP_PASS = ''
        status, headers, raw = self.request('/salud', headers={'Authorization': 'invalid'})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw), {'ok': True})
        self.assertEqual(int(headers['Content-Length']), len(raw))

    def test_salud_is_not_cacheable(self):
        status, headers, raw = self.request('/salud')
        self.assertEqual(status, 200)
        self.assertEqual(headers.get('Cache-Control'), 'no-store')

    def test_readiness_ok_when_storage_is_writable_and_leaves_no_probe(self):
        status, headers, raw = self.request('/salud/listo')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw), {'ok': True})
        self.assertEqual(headers.get('Cache-Control'), 'no-store')
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_readiness_503_sanitized_when_storage_is_unwritable(self):
        self.app.STORE_FILE = '/proc/mmj-no-escribible/mensajes.jsonl'
        status, headers, raw = self.request('/salud/listo')
        self.assertEqual(status, 503)
        self.assertEqual(json.loads(raw), {'ok': False, 'error': 'no disponible'})
        self.assertNotIn(b'/proc', raw)
        self.assertEqual(headers.get('Cache-Control'), 'no-store')


if __name__ == '__main__':
    unittest.main()
