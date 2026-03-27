import os


host = os.getenv("ZERO_DB_HOST", "127.0.0.1")
port = os.getenv("ZERO_DB_PORT", "8050")

wsgi_app = "main:server"
bind = os.getenv("ZERO_DB_GUNICORN_BIND", f"{host}:{port}")
workers = int(os.getenv("ZERO_DB_GUNICORN_WORKERS", "2"))
threads = int(os.getenv("ZERO_DB_GUNICORN_THREADS", "1"))
timeout = int(os.getenv("ZERO_DB_GUNICORN_TIMEOUT", "300"))
accesslog = os.getenv("ZERO_DB_GUNICORN_ACCESSLOG", "-")
errorlog = os.getenv("ZERO_DB_GUNICORN_ERRORLOG", "-")
loglevel = os.getenv("ZERO_DB_GUNICORN_LOGLEVEL", "info")
capture_output = True

