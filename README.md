# MMJ Systems

Sitio público de MMJ Systems.

**Web:** https://mmjsystems.cl/

Este repositorio contiene el sitio estático (actualmente publicado mediante
GitHub Pages) y una imagen Nginx para desplegarlo también en Coolify.
Sin dependencias remotas, sin analítica, sin cookies.

## Vista local

```bash
python3 -m http.server --bind 127.0.0.1 8123
```

Abrir `http://127.0.0.1:8123/`, `http://127.0.0.1:8123/estudios-juridicos/` o
`http://127.0.0.1:8123/guias/automatizar-correos-y-planillas/`.
En local y en dominios de vista previa el formulario simula el envío;
solo envía mensajes en los dominios de producción.

## Estructura

- `index.html` — contenido y estructura semántica.
- `estudios-juridicos/index.html` — automatización de un flujo de correo jurídico.
- `guias/automatizar-correos-y-planillas/index.html` — guía para elegir, probar y medir un flujo.
- `styles.css` — sistema visual y responsive.
- `main.js` — menú móvil en páginas secundarias, origen de las consultas y envío del formulario.
- `story.js` — sincroniza el fotograma y los tres pasos del ejemplo con el
  desplazamiento de la página. Actualiza también el parallax del fondo, los
  carriles, el encuadre y la imagen de diagnóstico.
- `assets/` — logo Convergencia III (variante web de tres entradas), retratos,
  imágenes WebP e imagen para compartir. `logo-mmj.png` se deriva del SVG de
  Convergencia III para los datos estructurados. Se conserva el SVG original.
- `assets/fonts/` — Manrope e IBM Plex Sans en WOFF2, con sus licencias OFL.
- `assets/recorrido/` — toma ilustrativa generada con Higgsfield Seedance 2.5,
  en H.264 sin audio. Primero se muestra el póster; al acercarse a los pasos
  mediante scroll se carga solo el clip correspondiente al ancho de la pantalla.
- `assets/profundidad/` — fondo y fotografías editoriales WebP en versiones
  de escritorio y móvil.
- `contact-api/` — endpoint del formulario para el servidor Hetzner
  (ver `contact-api/README.md`). Solo biblioteca estándar de Python.
- `CNAME`, `robots.txt`, `sitemap.xml`, `404.html` — publicación en
  GitHub Pages con dominio propio.

«Vista estática» permite leer el recorrido sin movimiento. También se muestra
así sin JavaScript, con movimiento reducido, con ahorro de datos indicado por
el navegador, en pantallas de poca altura o si falla el video. El contacto
por correo directo y los tres pasos siguen accesibles.

## Origen de las consultas

El formulario incluye la página de origen en la notificación. Opcionalmente
acepta `utm_source` (`linkedin`, `email`, `referido`, `google`, `meta`,
`whatsapp`) y `utm_content` (`ahorro-tiempo`, `pendientes-sin-responsable`).
Los enlaces marcados entre Inicio, Estudios jurídicos y la guía conservan solo
esos valores permitidos. No se usan cookies, rastreadores ni almacenamiento
del navegador.

Para validar el nicho jurídico, comparte la página desde un solo canal y usa
los dos mensajes por separado. Por ejemplo, en LinkedIn, usa
`/estudios-juridicos/?utm_source=linkedin&utm_content=ahorro-tiempo` y sustituye
`ahorro-tiempo` por `pendientes-sin-responsable` para el segundo mensaje.
Con el origen de la notificación, lleva una cuenta semanal por mensaje de
consultas recibidas, conversaciones realizadas sobre un proceso concreto y
diagnósticos contratados. No hace falta añadir rastreadores ni un CRM.

## SEO y validación tras publicar

- Las tres páginas tienen títulos, descripciones y canónicas propios, y se
  incluyen en `sitemap.xml`. El contenido está disponible sin JavaScript.
- La portada declara `Organization` y `WebSite`; la página jurídica, `Service`;
  la guía, `Article`. No se declaran precios ni datos de contacto no verificados.
- En Nginx, `www.mmjsystems.cl` redirige al dominio canónico y los demás hosts de
  vista previa reciben `X-Robots-Tag: noindex, nofollow`. El proxy debe preservar
  el encabezado `Host`; no bloquees el rastreo del HTML en `robots.txt`, para que
  un buscador pueda leer el `noindex`.
- Después de una publicación autorizada, verificar `https://mmjsystems.cl/sitemap.xml`,
  enviarlo en Search Console e inspeccionar las tres URLs. Revisar indexación,
  impresiones, clics y consultas por página, filtrando Chile. No requiere
  instalar píxeles ni cookies.

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
