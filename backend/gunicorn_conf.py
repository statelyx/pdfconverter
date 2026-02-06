# -*- coding: utf-8 -*-
"""
Gunicorn Config - PDFConverter Backend
Railway deploy için optimize edilmiş konfigürasyon
"""

import os

# Worker timeout - PDF çeviri işlemleri için yeterli süre
timeout = 600  # 10 dakika (çok büyük PDF'ler için)

# Worker type - async işlem için gevent
worker_class = "sync"

# Worker sayısı - RAM kısıtı nedeniyle 1-2 arası
workers = int(os.environ.get("GUNICORN_WORKERS", 1))

# Thread sayısı
threads = int(os.environ.get("GUNICORN_THREADS", 2))

# Bind address
bind = "0.0.0.0:5000"

# Log level
loglevel = os.environ.get("LOG_LEVEL", "info")

# Access log
accesslog = "-"

# Error log
errorlog = "-"

# Graceful timeout
graceful_timeout = 30

# Keepalive
keepalive = 5

# Max requests - bellek sızıntısını önlemek için
max_requests = 100
max_requests_jitter = 10

# Preload app (daha hızlı başlatma)
preload_app = True

def when_ready(server):
    """Server hazır olduğunda"""
    print("\n" + "="*60)
    print("  Gunicorn Server Hazır")
    print(f"  Workers: {workers}")
    print(f"  Timeout: {timeout}s")
    print("="*60 + "\n")

def worker_int(worker):
    """Worker başladığında"""
    print(f"Worker {worker.pid} başlatılıyor...")

def on_exit(server):
    """Server kapanırken"""
    print("Server kapatılıyor...")
