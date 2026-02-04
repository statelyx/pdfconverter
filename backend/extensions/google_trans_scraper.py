# -*- coding: utf-8 -*-
"""
Extension: Google Translate Scraper
Kaynak: https://github.com/aurawindsurfing/google-translate
Mevcut sisteme DOKUNMADAN çalışır
Ücretsiz Google Translate erişimi (scraper)
"""

import json
import random
import time
from typing import Dict, List, Optional
from urllib.parse import quote
from dataclasses import dataclass

try:
    import requests
    from bs4 import BeautifulSoup
    _SCRAPER_AVAILABLE = True
except ImportError:
    _SCRAPER_AVAILABLE = False


@dataclass
class ScrapedTranslation:
    """Scraped çeviri sonucu"""
    text: str
    source_lang: str
    target_lang: str
    service: str = "google_translate_scraper"


class GoogleTranslateScraper:
    """
    Google Translate scraper'ı
    API anahtarı gerektirmez, ücretsiz
    Rate limiting riski vardır
    """

    __version__ = "1.0.0"

    # Google Translate URL'leri
    BASE_URL = "https://translate.google.com/translate_a/single"
    FALLBACK_URL = "https://translate.googleapis.com/translate_a/single"

    # Dil kodları
    LANG_CODES = {
        "auto": "auto",
        "tr": "tr",
        "turkish": "tr",
        "en": "en",
        "english": "en",
        "de": "de",
        "german": "de",
        "fr": "fr",
        "french": "fr",
        "es": "es",
        "spanish": "es",
        "it": "it",
        "italian": "it",
        "ru": "ru",
        "ar": "ar",
        "zh": "zh-CN",
        "ja": "ja",
        "ko": "ko",
        "pt": "pt",
        "nl": "nl",
        "pl": "pl",
    }

    # User-Agent listesi (döngüsel kullanım için)
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    ]

    def __init__(self, config: Optional[Dict] = None):
        """
        Google Translate scraper başlat

        Args:
            config: Yapılandırma
                - timeout: Zaman aşımı
                - delay: İstekler arası gecikme (rate limiting önlemi)
        """
        if not _SCRAPER_AVAILABLE:
            raise ImportError("Scraper kütüphaneleri kurulu değil. pip install requests beautifulsoup4")

        self.config = config or {}
        self.timeout = self.config.get("timeout", 10)
        self.delay = self.config.get("delay", 1.0)
        self.session = requests.Session()

    def _get_headers(self) -> Dict:
        """Rastgele User-Agent ile headers oluştur"""
        return {
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "*/*",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

    def translate(self, text: str, target_lang: str = "tr",
                 source_lang: str = "auto") -> ScrapedTranslation:
        """
        Metin çevirisi yap (Google Translate scraper)

        Args:
            text: Çevrilecek metin
            target_lang: Hedef dil
            source_lang: Kaynak dil

        Returns:
            ScrapedTranslation: Çeviri sonucu
        """
        if not text or not text.strip():
            return ScrapedTranslation(
                text=text,
                source_lang=source_lang,
                target_lang=target_lang
            )

        # Dil kodlarını normalize et
        target = self.LANG_CODES.get(target_lang.lower(), target_lang)
        source = self.LANG_CODES.get(source_lang.lower(), source_lang)

        try:
            # Rate limiting önlemi
            time.sleep(self.delay)

            # Parametreler
            params = {
                "client": "gtx",
                "sl": source,
                "tl": target,
                "dt": "t",
                "q": text
            }

            # İstek gönder
            response = self.get(
                self.BASE_URL,
                params=params,
                headers=self._get_headers(),
                timeout=self.timeout
            )

            if response.status_code == 200:
                # JSON yanıtı parse et
                data = response.json()

                # Çevrilen metni çıkar
                if data and len(data) > 0:
                    translated = ""
                    for item in data[0]:
                        if item and len(item) > 0:
                            translated += item[0]

                    # Kaynak dil tespiti
                    detected = data[2] if len(data) > 2 else source_lang

                    return ScrapedTranslation(
                        text=translated,
                        source_lang=detected,
                        target_lang=target
                    )

        except Exception as e:
            print(f"Google Translate scraper hatası: {e}")

        # Hata durumunda orijinal metni döndür
        return ScrapedTranslation(
            text=text,
            source_lang=source,
            target_lang=target
        )

    def get(self, url: str, params: Dict = None,
            headers: Dict = None, timeout: int = 10):
        """
        GET isteği (rate limiting ile)
        """
        return self.session.get(url, params=params, headers=headers, timeout=timeout)

    def translate_with_alternative(self, text: str, target_lang: str = "tr",
                                  source_lang: str = "auto") -> ScrapedTranslation:
        """
        Alternatif URL ile çeviri (fallback)

        Args:
            text: Çevrilecek metin
            target_lang: Hedef dil
            source_lang: Kaynak dil

        Returns:
            ScrapedTranslation: Çeviri sonucu
        """
        if not text or not text.strip():
            return ScrapedTranslation(
                text=text,
                source_lang=source_lang,
                target_lang=target_lang
            )

        target = self.LANG_CODES.get(target_lang.lower(), target_lang)
        source = self.LANG_CODES.get(source_lang.lower(), source_lang)

        try:
            time.sleep(self.delay)

            params = {
                "client": "gtx",
                "sl": source,
                "tl": target,
                "dt": "t",
                "q": text
            }

            response = self.get(
                self.FALLBACK_URL,
                params=params,
                headers=self._get_headers(),
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()

                if data and len(data) > 0:
                    translated = ""
                    for item in data[0]:
                        if item and len(item) > 0:
                            translated += item[0]

                    return ScrapedTranslation(
                        text=translated,
                        source_lang=data[2] if len(data) > 2 else source_lang,
                        target_lang=target
                    )

        except Exception as e:
            print(f"Alternatif scraper hatası: {e}")

        return ScrapedTranslation(
            text=text,
            source_lang=source,
            target_lang=target
        )

    def translate_batch(self, texts: List[str], target_lang: str = "tr",
                       source_lang: str = "auto") -> List[ScrapedTranslation]:
        """
        Toplu metin çevirisi (rate limiting ile)

        Args:
            texts: Metin listesi
            target_lang: Hedef dil
            source_lang: Kaynak dil

        Returns:
            List[ScrapedTranslation]: Çeviri sonuçları
        """
        results = []

        for text in texts:
            result = self.translate(text, target_lang, source_lang)
            results.append(result)

            # Rate limiting için artan gecikme
            time.sleep(self.delay * 0.5)

        return results

    def detect_language(self, text: str) -> Dict:
        """
        Dil tespiti yap

        Args:
            text: Metin

        Returns:
            Dict: {language: str, confidence: float}
        """
        try:
            params = {
                "client": "gtx",
                "sl": "auto",
                "tl": "tr",
                "dt": "t",
                "q": text[:100]  # İlk 100 karakter
            }

            response = self.get(
                self.BASE_URL,
                params=params,
                headers=self._get_headers(),
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                if len(data) > 2:
                    return {
                        "language": data[2],
                        "confidence": 1.0  # Google confidence vermez
                    }

        except Exception as e:
            print(f"Dil tespit hatası: {e}")

        return {"language": "unknown", "confidence": 0}


class SafeGoogleTranslator(GoogleTranslateScraper):
    """
    Güvenli Google Translate scraper
    Rate limiting koruması ile
    """

    def __init__(self, config: Optional[Dict] = None):
        super().__init__(config)
        self.request_count = 0
        self.max_requests = 100  # Maksimum istek sayısı
        self.reset_time = time.time() + 3600  # 1 saat sonra sıfırla

    def translate(self, text: str, target_lang: str = "tr",
                 source_lang: str = "auto") -> ScrapedTranslation:
        """
        Rate limiting kontrolü ile çeviri
        """
        # Zaman aşımı kontrolü
        if time.time() > self.reset_time:
            self.request_count = 0
            self.reset_time = time.time() + 3600

        # Maksimum istek kontrolü
        if self.request_count >= self.max_requests:
            print("⚠️ Maksimum istek sınırına ulaşildi, bir saat bekleyin")
            return ScrapedTranslation(
                text=text,
                source_lang=source_lang,
                target_lang=target_lang
            )

        self.request_count += 1

        # Rate limiting için artan gecikme
        dynamic_delay = self.delay + (self.request_count / 100)
        time.sleep(dynamic_delay)

        return super().translate(text, target_lang, source_lang)


# Kolay kullanım fonksiyonları
def google_translate(text: str, target_lang: str = "tr",
                    source_lang: str = "auto", config: Dict = None) -> str:
    """
    Google Translate ile çeviri (kolay fonksiyon)

    Args:
        text: Çevrilecek metin
        target_lang: Hedef dil
        source_lang: Kaynak dil
        config: Yapılandırma

    Returns:
        str: Çevrilmiş metin
    """
    scraper = SafeGoogleTranslator(config)
    result = scraper.translate(text, target_lang, source_lang)
    return result.text


def detect_language_google(text: str, config: Dict = None) -> Dict:
    """
    Dil tespiti (kolay fonksiyon)

    Args:
        text: Metin
        config: Yapılandırma

    Returns:
        Dict: {language: str, confidence: float}
    """
    scraper = GoogleTranslateScraper(config)
    return scraper.detect_language(text)
