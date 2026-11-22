#!/usr/bin/env python3
"""Endpoint de contacto para una web estática.

Recibe el formulario de la web estática (GitHub Pages) y lo reenvía por
correo al buzón configurado. Solo usa la biblioteca estándar de Python.

Contrato:
  POST /contacto   JSON o formulario con:
    nombre (requerido, máx 80), email (requerido, máx 120),
    mensaje (requerido, máx 2000), empresa (opcional, máx 80),
    sitio (honeypot: si viene con contenido se responde éxito falso).
  Responde JSON {"ok": true, "confirmacion_enviada": true/false}
  o {"ok": false, "error": "..."}.
  GET /salud  -> {"ok": true} (chequeo de vida).
  OPTIONS     -> preflight CORS.

Configuración por variables de entorno (ver mmj-contact-api.env.ejemplo):
  HOST, PORT, ALLOWED_ORIGINS, CONTACT_SITE, TO_EMAIL, FROM_EMAIL,
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS,
  RATE_MAX, RATE_VENTANA_SEG, STORE_FILE, LOG_FILE,
  CONFIRMACION_ACTIVA, CONFIRMACION_MAX_POR_HORA.
"""

import json
import os
import re
import smtplib
import ssl
import sys
import time
import urllib.parse
from email.errors import HeaderParseError
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_BODY = 64 * 1024


def env(name, default=""):
    return os.environ.get(name, default)


HOST = env("HOST", "127.0.0.1")
PORT = int(env("PORT", "8471"))
ALLOWED_ORIGINS = [o.strip() for o in env("ALLOWED_ORIGINS", "").split(",") if o.strip()]
CONTACT_SITE = env("CONTACT_SITE", "josemercado.cl")
TO_EMAIL = env("TO_EMAIL", "")
FROM_EMAIL = env("FROM_EMAIL", "")
SMTP_HOST = env("SMTP_HOST", "")
SMTP_PORT = int(env("SMTP_PORT", "587"))
SMTP_USER = env("SMTP_USER", "")
SMTP_PASS = env("SMTP_PASS", "")
RATE_MAX = int(env("RATE_MAX", "5"))
RATE_VENTANA_SEG = int(env("RATE_VENTANA_SEG", "3600"))
STORE_FILE = env("STORE_FILE", "/var/lib/mmj-contact-api/mensajes.jsonl")
LOG_FILE = env("LOG_FILE", "/var/lib/mmj-contact-api/api.log")
CONFIRMACION_ACTIVA = env("CONFIRMACION_ACTIVA").strip().lower() in {"1", "true"}
CONFIRMACION_MAX_POR_HORA = int(env("CONFIRMACION_MAX_POR_HORA", "20"))
CONFIRMACION_VENTANA_SEG = 3600
CONFIRMACION_ASUNTO = "Recibí tu mensaje | José Mercado"
CONFIRMACION_TEXTO = """Recibí tu mensaje.

Gracias por escribirme. Recibí tu consulta y te responderé personalmente a esta dirección.

Si quieres agregar algo, responde directamente a este correo.

José Mercado
https://josemercado.cl/

Este correo es automático. Si no enviaste una consulta, puedes ignorarlo.
"""
CONFIRMACION_HTML = Path(__file__).with_name("confirmacion.html")
CONFIRMACION_MONOGRAMA = Path(__file__).with_name("monograma-jm.png")

_intentos = {}
_confirmaciones = {}
_lock_confirmaciones = Lock()


def correo_configurado():
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASS and TO_EMAIL)


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


def log_error_smtp(evento, exc):
    # Log the error class and SMTP status, never the credentials, addresses or reply text.
    datos = {"evento": evento, "tipo": type(exc).__name__}
    if isinstance(exc, smtplib.SMTPResponseException):
        datos["estado_smtp"] = exc.smtp_code
    log(datos)
    print(json.dumps(datos), file=sys.stderr, flush=True)


def excede_limite(ip):
    ahora = time.time()
    marcas = [m for m in _intentos.get(ip, []) if ahora - m < RATE_VENTANA_SEG]
    if len(marcas) >= RATE_MAX:
        _intentos[ip] = marcas
        return True
    marcas.append(ahora)
    _intentos[ip] = marcas
    return False


def reservar_confirmacion(email):
    if not CONFIRMACION_ACTIVA:
        return False
    ahora = time.monotonic()
    destino = email.casefold()
    with _lock_confirmaciones:
        for correo, marca in list(_confirmaciones.items()):
            if ahora - marca >= CONFIRMACION_VENTANA_SEG:
                del _confirmaciones[correo]
        if destino in _confirmaciones or len(_confirmaciones) >= CONFIRMACION_MAX_POR_HORA:
            return False
        _confirmaciones[destino] = ahora
        return True


def enviar_por_smtp(mensaje, *, timeout, destinatario):
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=timeout) as smtp:
        smtp.starttls(context=ssl.create_default_context())
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.send_message(mensaje, to_addrs=[destinatario])


def enviar_correo(payload):
    remitente = FROM_EMAIL or SMTP_USER
    msg = EmailMessage()
    empresa = payload.get("empresa", "").strip()
    asunto = f"[{CONTACT_SITE}] " + " ".join(payload["nombre"].split())
    if empresa:
        asunto += " — " + " ".join(empresa.split())
    msg["Subject"] = asunto
    msg["From"] = remitente
    msg["To"] = TO_EMAIL
    msg["Reply-To"] = Address(addr_spec=payload["email"])
    msg.set_content(
        "Nombre: {}\nEmpresa: {}\nCorreo: {}\n\n{}".format(
            payload["nombre"], empresa or "-", payload["email"], payload["mensaje"]
        )
    )
    enviar_por_smtp(msg, timeout=20, destinatario=TO_EMAIL)


def agregar_html_confirmacion(msg):
    try:
        plantilla = CONFIRMACION_HTML.read_text(encoding="utf-8")
        monograma = CONFIRMACION_MONOGRAMA.read_bytes()
    except (OSError, UnicodeError) as exc:
        log({"evento": "confirmacion_solo_texto", "tipo": type(exc).__name__})
        return

    cid = make_msgid(domain=CONTACT_SITE)
    msg.add_alternative(plantilla.replace("{{MONOGRAMA_CID}}", cid[1:-1]), subtype="html")
    tarjeta = msg.get_payload()[-1]
    tarjeta.add_related(monograma, maintype="image", subtype="png", cid=cid)
    tarjeta.set_param("type", "text/html")


def enviar_confirmacion(email):
    if not reservar_confirmacion(email):
        return False
    try:
        destino = Address(addr_spec=email)
        remitente = Address(addr_spec=FROM_EMAIL or SMTP_USER)
        msg = EmailMessage()
        msg["Subject"] = CONFIRMACION_ASUNTO
        msg["From"] = Address("José Mercado", remitente.username, remitente.domain)
        msg["To"] = destino
        msg["Reply-To"] = TO_EMAIL
        msg["Date"] = formatdate(usegmt=True)
        msg["Message-ID"] = make_msgid(domain=CONTACT_SITE)
        msg["Auto-Submitted"] = "auto-replied"
        msg["X-Auto-Response-Suppress"] = "All"
        msg.set_content(CONFIRMACION_TEXTO)
        agregar_html_confirmacion(msg)
        enviar_por_smtp(msg, timeout=8, destinatario=destino.addr_spec)
    except (OSError, ValueError, HeaderParseError) as exc:
        log_error_smtp("error_confirmacion", exc)
        return False
    log({"evento": "confirmacion"})
    return True


def email_valido(email):
    if len(email) > 120 or not EMAIL_RE.fullmatch(email):
        return False
    try:
        return Address(addr_spec=email).addr_spec == email
    except (ValueError, HeaderParseError):
        return False


def validar(payload):
    nombre = str(payload.get("nombre", "")).strip()
    email = str(payload.get("email", "")).strip()
    mensaje = str(payload.get("mensaje", "")).strip()
    empresa = str(payload.get("empresa", "")).strip()
    if len(nombre) < 2 or len(nombre) > 80:
        return None, "nombre inválido"
    if not email_valido(email):
        return None, "correo inválido"
    if len(mensaje) < 10 or len(mensaje) > 2000:
        return None, "mensaje inválido"
    if len(empresa) > 80:
        return None, "empresa inválida"
    return {"nombre": nombre, "email": email, "mensaje": mensaje, "empresa": empresa}, ""


class Handler(BaseHTTPRequestHandler):
    server_version = "ContactAPI/1.0"

    def _origen_permitido(self):
        origen = self.headers.get("Origin", "")
        return origen if origen in ALLOWED_ORIGINS else ""

    def _responder(self, codigo, cuerpo, origen=""):
        datos = json.dumps(cuerpo).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
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
        if ruta != "/contacto":
            self._responder(404, {"ok": False, "error": "no encontrado"}, origen)
            return
        if not origen:
            self._responder(403, {"ok": False, "error": "origen no permitido"})
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
            self._responder(200, {"ok": True, "confirmacion_enviada": True}, origen)
            return
        datos, error = validar(payload)
        if error:
            self._responder(400, {"ok": False, "error": error}, origen)
            return
        if not correo_configurado():
            self._responder(503, {"ok": False, "error": "envío no disponible"}, origen)
            return
        if excede_limite(ip):
            log({"evento": "limite", "ip": ip})
            self._responder(429, {"ok": False, "error": "demasiados intentos"}, origen)
            return
        try:
            enviar_correo(datos)
        except Exception as exc:  # noqa: BLE001 - se reporta como fallo al cliente
            log_error_smtp("error_correo", exc)
            self._responder(502, {"ok": False, "error": "no se pudo enviar"}, origen)
            return
        guardar_mensaje(datos, ip)
        log({"evento": "mensaje", "ip": ip, "email": datos["email"]})
        confirmacion = enviar_confirmacion(datos["email"])
        self._responder(200, {"ok": True, "confirmacion_enviada": confirmacion}, origen)

    def log_message(self, format, *args):  # noqa: A002 - firma de stdlib
        pass


def main():
    if not SMTP_HOST:
        raise SystemExit("Falta SMTP_HOST (ver mmj-contact-api.env.ejemplo).")
    servidor = ThreadingHTTPServer((HOST, PORT), Handler)
    print("contact-api en {}:{}".format(HOST, PORT), flush=True)
    servidor.serve_forever()


if __name__ == "__main__":
    main()
