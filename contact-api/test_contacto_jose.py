import http.client
import io
import json
import smtplib
import threading
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

import app


class ContactoTest(unittest.TestCase):
    buzon = "josemercado.musica@gmail.com"

    def setUp(self):
        self.server = app.ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        self.worker = threading.Thread(target=self.server.serve_forever, args=(0.01,))
        self.worker.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.worker.join)
        self.addCleanup(self.server.shutdown)
        self.origin = "https://josemercado.cl"
        self.payload = {"nombre": "Consulta de prueba", "email": "test@example.com", "mensaje": "Consulta de prueba del portafolio."}

    def configured(self, **overrides):
        options = dict(
            ALLOWED_ORIGINS=[self.origin], CONTACT_SITE="josemercado.cl",
            SMTP_HOST="smtp.gmail.com", SMTP_USER=self.buzon, SMTP_PASS="prueba-local",
            FROM_EMAIL=self.buzon, TO_EMAIL=self.buzon,
            RATE_MAX=5, _intentos={}, _confirmaciones={}, CONFIRMACION_ACTIVA=True,
            CONFIRMACION_MAX_POR_HORA=20,
        )
        return patch.multiple(app, **(options | overrides))

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
        email = self.payload["email"]
        with self.configured(CONFIRMACION_ACTIVA=False), patch.object(app.smtplib, "SMTP") as client, \
                patch.object(app, "guardar_mensaje"), patch.object(app, "log"):
            status, origin, body = self.request("POST", "/contacto", self.origin, self.payload)
            self.assertEqual((status, origin), (200, self.origin))
            self.assertEqual(json.loads(body), {"ok": True, "confirmacion_enviada": False})
            smtp = client.return_value.__enter__.return_value
            smtp.starttls.assert_called_once()
            smtp.login.assert_called_once_with(self.buzon, "prueba-local")
            mensaje = smtp.send_message.call_args.args[0]
            self.assertEqual(mensaje["Subject"], "[josemercado.cl] Consulta de prueba")
            self.assertEqual(mensaje["To"], self.buzon)
            self.assertEqual(mensaje["From"], self.buzon)
            self.assertEqual(mensaje["Reply-To"], email)
            self.assertEqual(smtp.send_message.call_args.kwargs["to_addrs"], [self.buzon])

    def test_confirma_al_cliente_con_texto_fijo_y_sin_repetir(self):
        with self.configured(), patch.object(app, "enviar_por_smtp") as smtp, \
                patch.object(app, "guardar_mensaje"), patch.object(app, "log"):
            status, _, body = self.request("POST", "/contacto", self.origin, self.payload)
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body), {"ok": True, "confirmacion_enviada": True})
            principal, acuse = smtp.call_args_list
            self.assertEqual(principal.kwargs["destinatario"], self.buzon)
            self.assertEqual(acuse.kwargs["destinatario"], self.payload["email"])
            mensaje = acuse.args[0]
            self.assertEqual(mensaje["To"], self.payload["email"])
            self.assertEqual(mensaje["Subject"], "Recibí tu mensaje | José Mercado")
            self.assertEqual(mensaje["From"].addresses[0].addr_spec, self.buzon)
            self.assertEqual(mensaje["Reply-To"], self.buzon)
            self.assertEqual(mensaje["Auto-Submitted"], "auto-replied")
            self.assertIn("josemercado.cl", mensaje.get_content())
            self.assertNotIn(self.payload["mensaje"], mensaje.get_content())
            status, _, body = self.request("POST", "/contacto", self.origin, self.payload)
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body), {"ok": True, "confirmacion_enviada": False})
            self.assertEqual(smtp.call_count, 3)
            self.assertEqual(smtp.call_args.kwargs["destinatario"], self.buzon)

    def test_si_falla_el_acuse_la_consulta_sigue_aceptada(self):
        with self.configured(), patch.object(app, "enviar_por_smtp", side_effect=(
            None, smtplib.SMTPDataError(451, b"diagnostico SMTP")
        )) as smtp, patch.object(app, "guardar_mensaje") as guardar, patch.object(app, "log") as log, \
                redirect_stderr(io.StringIO()) as stderr:
            status, _, body = self.request("POST", "/contacto", self.origin, self.payload)
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body), {"ok": True, "confirmacion_enviada": False})
            guardar.assert_called_once()
            self.assertEqual(smtp.call_count, 2)
            self.assertEqual(log.call_args.args[0], {
                "evento": "error_confirmacion", "tipo": "SMTPDataError", "estado_smtp": 451
            })
            self.assertNotIn("diagnostico SMTP", stderr.getvalue())

    def test_no_confirma_si_falla_la_consulta_principal(self):
        with self.configured(), patch.object(app, "enviar_por_smtp", side_effect=(
            smtplib.SMTPAuthenticationError(535, b"auth")
        )) as smtp, patch.object(app, "guardar_mensaje") as guardar, patch.object(app, "log"), \
                redirect_stderr(io.StringIO()):
            status, _, body = self.request("POST", "/contacto", self.origin, self.payload)
            self.assertEqual(status, 502)
            self.assertFalse(json.loads(body)["ok"])
            smtp.assert_called_once()
            guardar.assert_not_called()

    def test_no_envia_a_destinatarios_multiples_ni_al_honeypot(self):
        with self.configured(), patch.object(app, "enviar_por_smtp") as smtp, patch.object(app, "log"):
            payload = self.payload | {"email": "test@example.com,other@example.com"}
            self.assertEqual(self.request("POST", "/contacto", self.origin, payload)[0], 400)
            payload = self.payload | {"sitio": "rellenado"}
            self.assertEqual(self.request("POST", "/contacto", self.origin, payload)[0], 200)
            smtp.assert_not_called()

    def test_tope_de_acuses_y_expiracion(self):
        with self.configured(CONFIRMACION_MAX_POR_HORA=2), patch.object(app.time, "monotonic", return_value=10) as clock:
            self.assertTrue(app.reservar_confirmacion("test@example.com"))
            self.assertFalse(app.reservar_confirmacion("Test@example.com"))
            self.assertTrue(app.reservar_confirmacion("another@example.com"))
            self.assertFalse(app.reservar_confirmacion("third@example.com"))
            clock.return_value += app.CONFIRMACION_VENTANA_SEG
            self.assertTrue(app.reservar_confirmacion("test@example.com"))
