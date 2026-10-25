"""
GV Powers ERP - Gunicorn Configuration
Production-grade Gunicorn settings.
"""

import os
import multiprocessing

bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")
workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
threads = int(os.getenv("GUNICORN_THREADS", "2"))
worker_class = "gthread"
timeout = 120
keepalive = 5
max_requests = 1000
max_requests_jitter = 50

accesslog = os.path.join(os.path.dirname(__file__), "logs", "access.log")
errorlog = os.path.join(os.path.dirname(__file__), "logs", "error.log")
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")

proc_name = "gvpowers_erp"

preload_app = True
daemon = False
