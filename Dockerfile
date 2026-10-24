FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html 404.html robots.txt sitemap.xml styles.css main.js /usr/share/nginx/html/
COPY assets/ /usr/share/nginx/html/assets/
COPY health/web.sh /usr/local/bin/mmj-web-health
RUN chmod 755 /usr/local/bin/mmj-web-health

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 CMD ["/usr/local/bin/mmj-web-health"]
