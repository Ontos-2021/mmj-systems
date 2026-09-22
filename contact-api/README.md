# contact-api — endpoint del formulario (Hetzner)

Servicio mínimo, solo biblioteca estándar de Python, sin dependencias.
Recibe `POST /contacto` desde `https://mmjsystems.cl/` y lo reenvía por
correo. Pensado para correr detrás de Caddy o nginx con HTTPS.

## Archivos

- `app.py` — el servicio.
- `mmj-contact-api.service` — unidad systemd.
- `mmj-contact-api.env.ejemplo` — plantilla de configuración (sin secretos).
- `proxy.Caddyfile` — fragmento de reverse proxy.

## 1. DNS (registrador del dominio, ej. NIC Chile)

| Host | Tipo | Valor |
|---|---|---|
| `@` | A | `185.199.108.153` |
| `@` | A | `185.199.109.153` |
| `@` | A | `185.199.110.153` |
| `@` | A | `185.199.111.153` |
| `www` | CNAME | `ontos-2021.github.io.` |
| `api` | A | IP pública del servidor Hetzner |

Las 4 A del apex son las de GitHub Pages. Después, en el repo:
Settings → Pages → Custom domain → `mmjsystems.cl`, y activar
“Enforce HTTPS”. El archivo `CNAME` de la raíz ya dice `mmjsystems.cl`.

## 2. Servidor Hetzner (una vez)

```bash
sudo mkdir -p /opt/mmj-contact-api
sudo cp app.py /opt/mmj-contact-api/app.py
sudo cp mmj-contact-api.service /etc/systemd/system/mmj-contact-api.service
sudo cp mmj-contact-api.env.ejemplo /etc/mmj-contact-api.env
sudo chmod 600 /etc/mmj-contact-api.env
# editar /etc/mmj-contact-api.env con la app password real de Gmail
sudo systemctl daemon-reload
sudo systemctl enable --now mmj-contact-api
```

App password de Gmail: cuenta `contacto.mmjsystems@gmail.com` →
Seguridad → Verificación en 2 pasos → Contraseñas de aplicaciones →
generar una para “Correo” y pegarla en `SMTP_PASS`.

Proxy HTTPS (Caddy, recomendado):

```bash
# agregar el bloque de proxy.Caddyfile al Caddyfile y recargar
sudo systemctl reload caddy
```

## 3. Probar

```bash
curl -i https://api.mmjsystems.cl/salud
curl -i -X POST https://api.mmjsystems.cl/contacto \
  -H 'Content-Type: application/json' \
  -H 'Origin: https://mmjsystems.cl' \
  -d '{"nombre":"Prueba","email":"prueba@example.com","mensaje":"Mensaje de prueba del formulario."}'
```

Lo esperado: `{"ok": true}` y el correo en la bandeja de
`contacto.mmjsystems@gmail.com` con Reply-To al remitente.

Límites incluidos: validación de campos, honeypot `sitio`, tope de
5 mensajes por hora por IP, CORS solo para `mmjsystems.cl`.
Copia local de cada mensaje en `mensajes.jsonl` (respaldo).

## 4. Operación

```bash
sudo systemctl status mmj-contact-api
sudo journalctl -u mmj-contact-api -n 50
sudo tail -n 20 /var/lib/mmj-contact-api/api.log
```

Actualizar: copiar el nuevo `app.py` a `/opt/mmj-contact-api/` y
`sudo systemctl restart mmj-contact-api`.
