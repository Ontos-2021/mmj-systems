# contact-api — imagen mínima (app.py usa solo la biblioteca estándar de Python)
FROM python:3.12-slim

RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY app.py .

ENV HOST=0.0.0.0 \
    PORT=8471 \
    STORE_FILE=/data/mensajes.jsonl \
    LOG_FILE=/data/api.log

RUN mkdir -p /data && chown app:app /data
USER app
VOLUME ["/data"]
EXPOSE 8471

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8471/salud', timeout=2).status == 200 else 1)"

CMD ["python", "app.py"]
