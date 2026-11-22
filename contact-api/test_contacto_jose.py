import http.client
import json
import threading
import unittest
from unittest.mock import patch

import app


class ContactoTest(unittest.TestCase):
    def setUp(self):
        self.server = app.ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        self.worker = threading.Thread(target=self.server.serve_forever, args=(0.01,))
        self.worker.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.worker.join)
        self.addCleanup(self.server.shutdown)
        self.origin = "https://josemercado.cl"
        self.payload = {"nombre": "Consulta de prueba", "email": "test@example.com", "mensaje": "Consulta de prueba del portafolio."}

    def request(self, method, path, origin, payload=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=2)
        try:
            conn.request(method, path, json.dumps(payload) if payload else None, {
                "Origin": origin, "Content-Type": "application/json"
            })
            response = conn.getresponse()
            return response.status, response.getheader("Access-Control-Allow-Origin"), response.read()
        finally:
            conn.close()

    def test_origenes_y_configuracion_pendiente(self):
        with patch.multiple(app, ALLOWED_ORIGINS=[self.origin], SMTP_PASS=""), patch.object(app, "enviar_correo") as enviar:
            self.assertEqual(self.request("GET", "/salud", self.origin)[0], 200)
            self.assertEqual(self.request("OPTIONS", "/contacto", self.origin)[:2], (204, self.origin))
            self.assertEqual(self.request("POST", "/contacto", "https://mmjsystems.cl", self.payload)[:2], (403, None))
            self.assertEqual(self.request("POST", "/contacto", self.origin, self.payload)[:2], (503, self.origin))
            enviar.assert_not_called()

    def test_asunto_destino_y_reply_to_propios(self):
        buzon = "josemercado.musica@gmail.com"
        email = self.payload["email"]
        with patch.multiple(
            app, ALLOWED_ORIGINS=[self.origin], CONTACT_SITE="josemercado.cl",
            SMTP_HOST="smtp.gmail.com", SMTP_USER=buzon, SMTP_PASS="prueba-local",
            FROM_EMAIL=buzon, TO_EMAIL=buzon, _intentos={}
        ), patch.object(app.smtplib, "SMTP") as client, patch.object(app, "guardar_mensaje"), patch.object(app, "log"):
            self.assertEqual(self.request("POST", "/contacto", self.origin, self.payload)[:2], (200, self.origin))
            smtp = client.return_value.__enter__.return_value
            smtp.starttls.assert_called_once()
            smtp.login.assert_called_once_with(buzon, "prueba-local")
            mensaje = smtp.send_message.call_args.args[0]
            self.assertEqual(mensaje["Subject"], "[josemercado.cl] Consulta de prueba")
            self.assertEqual(mensaje["To"], buzon)
            self.assertEqual(mensaje["From"], buzon)
            self.assertEqual(mensaje["Reply-To"], email)
