# MMJ Systems

Sitio público de MMJ Systems.

**Web:** https://mmjsystems.cl/

Este repositorio contiene el sitio estático (actualmente publicado mediante
GitHub Pages) y una imagen Nginx para desplegarlo también en Coolify.
Sin dependencias remotas, sin analítica, sin cookies.

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

- GitHub Pages sigue sirviendo `mmjsystems.cl` desde `main` hasta cambiar DNS.
- Coolify: crear aplicación desde repositorio público `Ontos-2021/mmj-systems`,
  rama `main`, build pack **Dockerfile** en la raíz (`/Dockerfile`), contexto
  raíz y puerto interno **80**. No requiere variables ni volumen. Asignar un
  subdominio de prueba HTTPS, comprobar que funciona y recién entonces decidir
  la migración del dominio principal. `Dockerfile` incluye solo el frontend;
  `contact-api/` es un recurso separado y el formulario seguirá usando
  `https://api.mmjsystems.cl/contacto` (con fallback por correo si no responde).
- Para la publicación anterior en Pages: el push a `main` publica en Pages;
  `CNAME` y la configuración del dominio apuntan a `mmjsystems.cl`.
