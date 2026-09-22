#!/usr/bin/env python3
"""Endpoint de contacto de mmjsystems.cl.

Recibe el formulario de la web estática (GitHub Pages) y lo reenvía por
correo a MMJ Systems. Solo usa la biblioteca estándar de Python.

Contrato:
  POST /contacto   JSON o formulario con:
    nombre (requerido, máx 80), email (requerido, máx 120),
    mensaje (requerido, máx 2000), empresa (opcional, máx 80),
    sitio (honeypot: si viene con contenido se responde éxito falso).
  Responde JSON {"ok": true} o {"ok": false, "error": "..."}.
  GET /salud  -> {"ok": true} (chequeo de vida).
  OPTIONS     -> preflight CORS.

Configuración por variables de entorno (ver mmj-contact-api.env.ejemplo):
  PORT, ALLOWED_ORIGINS, TO_EMAIL, FROM_EMAIL,
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS,
  RATE_MAX, RATE_VENTANA_SEG, STORE_FILE, LOG_FILE.
"""

import json
import os
import re
import smtplib
import time
import urllib.parse
from email.message import EmailMessage
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_BODY = 64 * 1024


def env(name, default=""):
    return os.environ.get(name, default)


PORT = int(env("PORT", "8471"))
ALLOWED_ORIGINS = [o.strip() for o in env("ALLOWED_ORIGINS", "").split(",") if o.strip()]
TO_EMAIL = env("TO_EMAIL", "contacto.mmjsystems@gmail.com")
FROM_EMAIL = env("FROM_EMAIL", "")
SMTP_HOST = env("SMTP_HOST", "")
SMTP_PORT = int(env("SMTP_PORT", "587"))
SMTP_USER = env("SMTP_USER", "")
SMTP_PASS = env("SMTP_PASS", "")
RATE_MAX = int(env("RATE_MAX", "5"))
RATE_VENTANA_SEG = int(env("RATE_VENTANA_SEG", "3600"))
STORE_FILE = env("STORE_FILE", "/var/lib/mmj-contact-api/mensajes.jsonl")
LOG_FILE = env("LOG_FILE", "/var/lib/mmj-contact-api/api.log")

_intentos = {}


def log(evento):
    linea = json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **evento}, ensure_ascii=False)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(linea + "\n")
    except OSError:
        pass


def guardar_mensaje(payload, ip):
    try:
        os.makedirs(os.path.dirname(STORE_FILE), exist_ok=True)
        with open(STORE_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "ip": ip,
                "nombre": payload["nombre"],
                "empresa": payload.get("empresa", ""),
                "email": payload["email"],
                "mensaje": payload["mensaje"],
            }, ensure_ascii=False) + "\n")
    except OSError:
        pass


def excede_limite(ip):
    ahora = time.time()
    marcas = [m for m in _intentos.get(ip, []) if ahora - m < RATE_VENTANA_SEG]
    if len(marcas) >= RATE_MAX:
        _intentos[ip] = marcas
        return True
    marcas.append(ahora)
    _intentos[ip] = marcas
    return False


def enviar_correo(payload):
    remitente = FROM_EMAIL or SMTP_USER
    msg = EmailMessage()
    empresa = payload.get("empresa", "").strip()
    asunto = "[mmjsystems.cl] " + payload["nombre"]
    if empresa:
        asunto += " — " + empresa
    msg["Subject"] = asunto
    msg["From"] = remitente
    msg["To"] = TO_EMAIL
    msg["Reply-To"] = payload["email"]
    msg.set_content(
        "Nombre: {}\nEmpresa: {}\nCorreo: {}\n\n{}".format(
            payload["nombre"], empresa or "-", payload["email"], payload["mensaje"]
        )
    )
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as s:
        s.starttls()
        if SMTP_USER:
            s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)


def validar(payload):
    nombre = str(payload.get("nombre", "")).strip()
    email = str(payload.get("email", "")).strip()
    mensaje = str(payload.get("mensaje", "")).strip()
    empresa = str(payload.get("empresa", "")).strip()
    if len(nombre) < 2 or len(nombre) > 80:
        return None, "nombre inválido"
    if not EMAIL_RE.match(email) or len(email) > 120:
        return None, "correo inválido"
    if len(mensaje) < 10 or len(mensaje) > 2000:
        return None, "mensaje inválido"
    if len(empresa) > 80:
        return None, "empresa inválida"
    return {"nombre": nombre, "email": email, "mensaje": mensaje, "empresa": empresa}, ""


class Handler(BaseHTTPRequestHandler):
    server_version = "MMJContact/1.0"

    def _origen_permitido(self):
        origen = self.headers.get("Origin", "")
        return origen if origen in ALLOWED_ORIGINS else ""

    def _responder(self, codigo, cuerpo, origen=""):
        datos = json.dumps(cuerpo).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(datos)))
        if origen:
            self.send_header("Access-Control-Allow-Origin", origen)
            self.send_header("Vary", "Origin")
        self.end_headers()
        self.wfile.write(datos)

    def do_OPTIONS(self):  # noqa: N802
        origen = self._origen_permitido()
        self.send_response(204)
        if origen:
            self.send_header("Access-Control-Allow-Origin", origen)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_GET(self):  # noqa: N802
        ruta = urllib.parse.urlparse(self.path).path
        if ruta == "/salud":
            self._responder(200, {"ok": True})
        else:
            self._responder(404, {"ok": False, "error": "no encontrado"})

    def do_POST(self):  # noqa: N802
        ruta = urllib.parse.urlparse(self.path).path
        origen = self._origen_permitido()
        try:
            ip = self.client_address[0]
        except (TypeError, IndexError):
            ip = "?"
        if ruta not in ("/contacto", "/"):
            self._responder(404, {"ok": False, "error": "no encontrado"}, origen)
            return
        try:
            largo = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            largo = 0
        if largo <= 0 or largo > MAX_BODY:
            self._responder(400, {"ok": False, "error": "cuerpo inválido"}, origen)
            return
        crudo = self.rfile.read(largo)
        ctype = self.headers.get("Content-Type", "")
        try:
            if "application/json" in ctype:
                payload = json.loads(crudo.decode("utf-8"))
            else:
                payload = {k: v[0] for k, v in
                           urllib.parse.parse_qs(crudo.decode("utf-8")).items()}
        except (ValueError, UnicodeDecodeError):
            self._responder(400, {"ok": False, "error": "cuerpo inválido"}, origen)
            return
        if not isinstance(payload, dict):
            self._responder(400, {"ok": False, "error": "cuerpo inválido"}, origen)
            return
        if str(payload.get("sitio", "")).strip():
            # Honeypot: parece bot, éxito falso sin hacer nada.
            log({"evento": "honeypot", "ip": ip})
            self._responder(200, {"ok": True}, origen)
            return
        datos, error = validar(payload)
        if error:
            self._responder(400, {"ok": False, "error": error}, origen)
            return
        if excede_limite(ip):
            log({"evento": "limite", "ip": ip})
            self._responder(429, {"ok": False, "error": "demasiados intentos"}, origen)
            return
        try:
            enviar_correo(datos)
        except Exception as exc:  # noqa: BLE001 - se reporta como fallo al cliente
            log({"evento": "error_correo", "ip": ip, "detalle": str(exc)[:200]})
            self._responder(502, {"ok": False, "error": "no se pudo enviar"}, origen)
            return
        guardar_mensaje(datos, ip)
        log({"evento": "mensaje", "ip": ip, "email": datos["email"]})
        self._responder(200, {"ok": True}, origen)

    def log_message(self, format, *args):  # noqa: A002 - firma de stdlib
        pass


def main():
    if not SMTP_HOST:
        raise SystemExit("Falta SMTP_HOST (ver mmj-contact-api.env.ejemplo).")
    servidor = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print("contact-api en 127.0.0.1:{}".format(PORT), flush=True)
    servidor.serve_forever()


if __name__ == "__main__":
    main()
