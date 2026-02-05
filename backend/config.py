# -*- coding: utf-8 -*-
"""
PDF Komuta Merkezi - Yapılandırma Dosyası
Profesyonel PDF Isleme ve Ceviri Sistemi
"""

import os
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

# Base Path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# API Keys - ENV'den al
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Gemini Ayarları - Varsayılan: KAPALI
ENABLE_GEMINI = os.environ.get("ENABLE_GEMINI", "false").lower() == "true"

# Hugging Face Token - Ücretsiz çeviri için
# Birden fazla ENV değişken adını destekle
HF_TOKEN = (
    os.environ.get("HF_TOKEN", "") or 
    os.environ.get("HUGGINGFACE_API_KEY", "") or
    os.environ.get("HUGGINGFACE_READ_API_KEY", "")
)

# LibreTranslate URL - Self-host için
LIBRETRANSLATE_URL = os.environ.get("LIBRETRANSLATE_URL", "")

# Çeviri Provider Seçimi: hf, libre, argos, gemini
TRANSLATOR_PROVIDER = os.environ.get("TRANSLATOR_PROVIDER", "hf")

# Font Yolları
FONT_DIR = os.path.join(BASE_DIR, "fonts")
FONTS = {
    "dejavu-sans": {
        "regular": os.path.join(FONT_DIR, "DejaVuSans.ttf"),
        "bold": os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf"),
        "italic": os.path.join(FONT_DIR, "DejaVuSans-Oblique.ttf"),
        "bold_italic": os.path.join(FONT_DIR, "DejaVuSans-BoldOblique.ttf")
    },
    "noto-sans": {
        "regular": os.path.join(FONT_DIR, "NotoSans-Regular.ttf"),
        "bold": os.path.join(FONT_DIR, "NotoSans-Bold.ttf")
    }
}

# Varsayılan Font
DEFAULT_FONT = "dejavu-sans"
DEFAULT_FONT_STYLE = "regular"

# Dil Kodları ve İsimleri
LANGUAGE_NAMES = {
    "auto": "Otomatik",
    "tr": "Turkce",
    "en": "Ingilizce",
    "de": "Almanca",
    "fr": "Fransizca",
    "es": "Ispanyolca",
    "it": "Italyanca",
    "da": "Danca",
    "sv": "Isvçrece",
    "no": "Norveçce",
    "fi": "Fince",
    "nl": "Felemenkçe",
    "pl": "Lehçe",
    "ru": "Rusça",
    "ar": "Arapça",
    "zh": "Çince",
    "ja": "Japonca",
    "ko": "Korece"
}

# PDF Ayarları
PDF_DPI = 300  # Yüksek kalite için
PDF_COMPRESSION = True
PDF_IMAGE_QUALITY = 95

# AI Ayarları
AI_MODEL = "gemini-2.0-flash-exp"
AI_MAX_RETRIES = 3
AI_TIMEOUT = 30  # saniye
AI_BATCH_SIZE = 5  # Her seferde kaç blok çevrilecek

# Upload Ayarları
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {"pdf"}

# Dönüşüm Formatları
OUTPUT_FORMATS = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "png": "image/png",
    "jpg": "image/jpeg"
}

# Geçici Dosya Ayarları
TEMP_DIR = os.path.join(BASE_DIR, "temp")
CLEANUP_TEMP_FILES = True

# Logging
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Performans
CHUNK_SIZE = 8192
MAX_PAGES_PREVIEW = 10
