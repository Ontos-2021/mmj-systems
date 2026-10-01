# MMJ Systems

Sitio público de MMJ Systems.

**Web:** https://mmjsystems.cl/

Este repositorio contiene únicamente los archivos estáticos publicados
mediante GitHub Pages. Sin dependencias remotas, sin analítica, sin cookies.

## Vista local

```bash
python3 -m http.server 8123
```

Abrir `http://127.0.0.1:8123/`.

## Estructura

- `index.html` — contenido y estructura semántica.
- `styles.css` — sistema visual y responsive.
- `main.js` — menú móvil, botón copiar-email y envío del formulario.
- `assets/` — marca, favicon SVG e imagen OG (`og-cover.png`).
- `contact-api/` — endpoint del formulario para el servidor Hetzner
  (ver `contact-api/README.md`). Solo biblioteca estándar de Python.
- `CNAME`, `robots.txt`, `sitemap.xml`, `404.html` — publicación en
  GitHub Pages con dominio propio.

## Publicar

1. Merge de `dev` a `main` (el push a `main` publica en Pages).
2. DNS según `contact-api/README.md` (apex → GitHub Pages,
   `api` → Hetzner) y dominio personalizado `mmjsystems.cl` en
   Settings → Pages con HTTPS forzado.
3. Desplegar `contact-api/` en Hetzner para activar el formulario.
   Sin ese paso, el formulario muestra la vía directa por correo.
