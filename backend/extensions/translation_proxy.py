# -*- coding: utf-8 -*-
"""
Extension: Translation Proxy (LibreTranslate)
Kaynak: https://github.com/LibreTranslate/LibreTranslate
Mevcut sisteme DOKUNMADAN çalışır
Ücretsiz, offline çeviri alternatifi
"""

import io
import os
from typing import Dict, List, Optional
from dataclasses import dataclass

import requests


@dataclass
class TranslationResult:
    """Çeviri sonucu"""
    text: str
    source_lang: str
    target_lang: str
    confidence: float
    service: str


class LibreTranslateProxy:
    """
    LibreTranslate proxy'si
    Self-hosted ücretsiz çeviri servisi
    """

    __version__ = "1.0.0"

    def __init__(self, config: Optional[Dict] = None):
        """
        LibreTranslate proxy başlat

        Args:
            config: Yapılandırma
                - url: LibreTranslate servisi URL'si
                - api_key: API anahtarı (opsiyonel)
                - timeout: İstek zaman aşımı
        """
        self.config = config or {}
        self.url = self.config.get(
            "url",
            os.environ.get("LIBRETRANSLATE_URL", "http://localhost:5001")
        )
        self.api_key = self.config.get("api_key", "")
        self.timeout = self.config.get("timeout", 30)
        self.available = self.check_available()

        # Dil kodları
        self.lang_map = {
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
            "zh": "zh",
            "ja": "ja",
        }

    def check_available(self) -> bool:
        """LibreTranslate servisi reachable mi"""
        try:
            response = requests.get(f"{self.url}/spec", timeout=5)
            return response.status_code == 200
        except:
            return False

    def translate(self, text: str, target_lang: str = "tr",
                 source_lang: str = "auto") -> TranslationResult:
        """
        Metin çevirisi yap

        Args:
            text: Çevrilecek metin
            target_lang: Hedef dil
            source_lang: Kaynak dil (auto = otomatik tespit)

        Returns:
            TranslationResult: Çeviri sonucu
        """
        if not text or not text.strip():
            return TranslationResult(
                text=text,
                source_lang=source_lang,
                target_lang=target_lang,
                confidence=0,
                service="libretranslate"
            )

        # Dil kodlarını normalize et
        target = self.lang_map.get(target_lang.lower(), target_lang)
        source = self.lang_map.get(source_lang.lower(), source_lang)

        try:
            payload = {
                "q": text,
                "target": target,
                "format": "text"
            }

            if source != "auto":
                payload["source"] = source

            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            response = requests.post(
                f"{self.url}/translate",
                json=payload,
                headers=headers,
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                return TranslationResult(
                    text=data.get("translatedText", text),
                    source_lang=data.get("detectedLanguage", {}).get("language", source),
                    target_lang=target,
                    confidence=data.get("detectedLanguage", {}).get("confidence", 1.0),
                    service="libretranslate"
                )
            else:
                # Hata durumunda orijinal metni döndür
                return TranslationResult(
                    text=text,
                    source_lang=source,
                    target_lang=target,
                    confidence=0,
                    service="libretranslate"
                )

        except Exception as e:
            print(f"LibreTranslate hatası: {e}")
            return TranslationResult(
                text=text,
                source_lang=source,
                target_lang=target,
                confidence=0,
                service="libretranslate"
            )

    def translate_batch(self, texts: List[str], target_lang: str = "tr",
                       source_lang: str = "auto") -> List[TranslationResult]:
        """
        Toplu metin çevirisi

        Args:
            texts: Metin listesi
            target_lang: Hedef dil
            source_lang: Kaynak dil

        Returns:
            List[TranslationResult]: Çeviri sonuçları
        """
        results = []

        for text in texts:
            result = self.translate(text, target_lang, source_lang)
            results.append(result)

        return results

    def get_supported_languages(self) -> List[Dict]:
        """Desteklenen dilleri al"""
        try:
            response = requests.get(f"{self.url}/languages", timeout=5)
            if response.status_code == 200:
                return response.json()
        except:
            pass

        # Varsayılan dil listesi
        return [
            {"code": "en", "name": "English"},
            {"code": "tr", "name": "Turkish"},
            {"code": "de", "name": "German"},
            {"code": "fr", "name": "French"},
            {"code": "es", "name": "Spanish"},
            {"code": "it", "name": "Italian"},
            {"code": "ru", "name": "Russian"},
            {"code": "ar", "name": "Arabic"},
            {"code": "zh", "name": "Chinese"},
            {"code": "ja", "name": "Japanese"}
        ]

    def detect_language(self, text: str) -> Dict:
        """
        Dil tespiti yap

        Args:
            text: Metin

        Returns:
            Dict: {language: str, confidence: float}
        """
        try:
            payload = {"q": text}
            response = requests.post(
                f"{self.url}/detect",
                json=payload,
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    return data[0]

        except Exception as e:
            print(f"Dil tespit hatası: {e}")

        return {"language": "unknown", "confidence": 0}


class HybridTranslator:
    """
    Hibrit çeviri servisi
    LibreTranslate + Fallback mekanizması
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.primary = LibreTranslateProxy(config)
        self.fallback = None  # GoogleTranslateScraper (eklenebilir)

    def translate(self, text: str, target_lang: str = "tr",
                 source_lang: str = "auto") -> TranslationResult:
        """
        Hibrit çeviri
        Önce LibreTranslate dener, başarısız olursa fallback kullanır
        """
        # Önce birincil servis
        result = self.primary.translate(text, target_lang, source_lang)

        # Başarısız olursa fallback
        if result.confidence == 0 and self.fallback:
            result = self.fallback.translate(text, target_lang, source_lang)

        return result


# Kolay kullanım fonksiyonları
def translate_text(text: str, target_lang: str = "tr",
                  source_lang: str = "auto", config: Dict = None) -> str:
    """
    Metin çevirisi (kolay fonksiyon)

    Args:
        text: Çevrilecek metin
        target_lang: Hedef dil
        source_lang: Kaynak dil
        config: Yapılandırma

    Returns:
        str: Çevrilmiş metin
    """
    proxy = LibreTranslateProxy(config)
    result = proxy.translate(text, target_lang, source_lang)
    return result.text


def detect_language(text: str, config: Dict = None) -> Dict:
    """
    Dil tespiti (kolay fonksiyon)

    Args:
        text: Metin
        config: Yapılandırma

    Returns:
        Dict: {language: str, confidence: float}
    """
    proxy = LibreTranslateProxy(config)
    return proxy.detect_language(text)
