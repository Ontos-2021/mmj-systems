import io
import json
import smtplib
import tempfile
import unittest
from contextlib import redirect_stdout
from http.client import HTTPConnection
from http.server import HTTPServer
from pathlib import Path
from threading import Thread
from unittest.mock import patch

import app


class ContactoTest(unittest.TestCase):
    def setUp(self):
        carpeta = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.log_file = carpeta / "api.log"
        self.to_email = "clientes@mmjsystems.cl"
        self.email = "prueba+contacto@example.com"
        self.enterContext(patch.multiple(
            app,
            ALLOWED_ORIGINS=["https://mmjsystems.cl", "https://preview.example.test"],
            CONFIRMACION_ACTIVA=True,
            TO_EMAIL=self.to_email,
            FROM_EMAIL="mmj@example.test",
            SMTP_HOST="smtp.example.test",
            SMTP_USER="",
            LOG_FILE=str(self.log_file),
            STORE_FILE=str(carpeta / "mensajes.jsonl"),
            _intentos={},
            _confirmaciones={},
        ))
        self.smtp = self.enterContext(patch.object(app.smtplib, "SMTP"))
        self.transporte = self.smtp.return_value.__enter__.return_value
        self.salida = self.enterContext(redirect_stdout(io.StringIO()))
        self.servidor = HTTPServer(("127.0.0.1", 0), app.Handler)
        self.addCleanup(self.servidor.server_close)

    def post(self, *, origen="https://mmjsystems.cl", ruta="/contacto", **campos):
        datos = {
            "nombre": "Persona de prueba",
            "email": self.email,
            "mensaje": "Consulta ficticia que no debe aparecer en el acuse.",
            **campos,
        }
        self.servidor.timeout = 5
        hilo = Thread(target=self.servidor.handle_request)
        hilo.start()
        conexion = HTTPConnection("127.0.0.1", self.servidor.server_port, timeout=5)
        try:
            conexion.request("POST", ruta, json.dumps(datos), {
                "Content-Type": "application/json",
                "Origin": origen,
            })
            respuesta = conexion.getresponse()
            self.referencia = respuesta.getheader("X-MMJ-Confirmacion-ID")
            return respuesta.status, json.loads(respuesta.read())
        finally:
            conexion.close()
            hilo.join(6)
            self.assertFalse(hilo.is_alive())

    def test_aviso_interno_y_acuse_html_y_texto(self):
        self.assertEqual(self.post(), (200, {"ok": True}))
        aviso, acuse = self.transporte.send_message.call_args_list
        self.assertEqual(aviso.args[0]["To"], self.to_email)
        self.assertEqual(aviso.args[0]["Reply-To"], self.email)
        self.assertEqual(acuse.kwargs["to_addrs"], [self.email])
        correo = acuse.args[0]
        self.assertEqual(correo["To"], self.email)
        self.assertEqual(correo["Reply-To"], self.to_email)
        self.assertEqual(correo["Auto-Submitted"], "auto-replied")
        self.assertEqual(correo.get_content_type(), "multipart/alternative")
        self.assertRegex(self.referencia, r"^[a-f0-9]{32}$")
        self.assertEqual(json.loads(self.salida.getvalue()), {
            "evento": "confirmacion_aceptada", "referencia": self.referencia,
        })
        self.assertTrue(self.transporte.starttls.call_args.kwargs["context"].check_hostname)
        for formato in ("plain", "html"):
            cuerpo = correo.get_body(preferencelist=(formato,)).get_content()
            self.assertIn("Gracias por contactarnos", cuerpo)
            self.assertIn("José Mercado", cuerpo)
            self.assertNotIn("Persona de prueba", cuerpo)
            self.assertNotIn("Consulta ficticia", cuerpo)
        self.assertNotIn("<img", correo.get_body(preferencelist=("html",)).get_content())

    def test_flag_apagada_y_origen_no_publico_solo_avisan_al_equipo(self):
        with patch.object(app, "CONFIRMACION_ACTIVA", False):
            self.assertEqual(self.post(), (200, {"ok": True}))
            self.assertIsNone(self.referencia)
        self.assertEqual(self.post(origen="https://preview.example.test"), (200, {"ok": True}))
        self.assertEqual(self.post(origen=""), (200, {"ok": True}))
        self.assertEqual(self.post(ruta="/"), (200, {"ok": True}))
        self.assertEqual(self.transporte.send_message.call_count, 4)

    def test_fallo_del_aviso_no_envia_acuse(self):
        self.transporte.send_message.side_effect = smtplib.SMTPException("fallo simulado")
        self.assertEqual(self.post()[0], 502)
        self.assertEqual(self.transporte.send_message.call_count, 1)

    def test_fallo_del_acuse_no_invalida_el_formulario(self):
        self.transporte.send_message.side_effect = [None, smtplib.SMTPException("fallo simulado")]
        self.assertEqual(self.post(), (200, {"ok": True}))
        self.assertEqual(self.transporte.send_message.call_count, 2)
        eventos = [json.loads(linea) for linea in self.log_file.read_text().splitlines()]
        self.assertEqual(eventos[-1]["evento"], "error_confirmacion")
        self.assertNotIn("email", eventos[-1])
        self.assertEqual(json.loads(self.salida.getvalue()), {
            "evento": "error_confirmacion", "referencia": self.referencia, "tipo": "SMTPException",
        })

    def test_no_confirma_honeypot_ni_destinatarios_invalidos(self):
        self.assertEqual(self.post(sitio="bot"), (200, {"ok": True}))
        self.assertEqual(self.post(email="prueba@example.com,grupo")[0], 400)
        self.transporte.send_message.assert_not_called()

    def test_limites_de_acuse_no_bloquean_nuevas_consultas(self):
        with patch.object(app, "CONFIRMACIONES_MAX", 2):
            for email in (self.email, self.email.upper(), "otro@example.com", "tercero@example.com"):
                self.assertEqual(self.post(email=email), (200, {"ok": True}))
        llamadas = self.transporte.send_message.call_args_list
        self.assertEqual(len(llamadas), 6)  # Cuatro avisos y dos acuses.
        destinos = [c.kwargs["to_addrs"] for c in llamadas if c.kwargs["to_addrs"]]
        self.assertEqual(destinos, [[self.email], ["otro@example.com"]])

    def test_ventana_de_acuse_expira(self):
        with patch.object(app.time, "monotonic", return_value=100.0) as reloj:
            self.assertTrue(app.reservar_confirmacion(self.email))
            self.assertFalse(app.reservar_confirmacion(self.email))
            reloj.return_value += app.CONFIRMACIONES_VENTANA_SEG
            self.assertTrue(app.reservar_confirmacion(self.email))


if __name__ == "__main__":
    unittest.main()
