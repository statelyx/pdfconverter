# -*- coding: utf-8 -*-
"""
Fallback Translator - Basit Çeviri Modülü
Gemini olmadan çalışan basit çeviri sistemi

Bu modül Gemini kullanılamadığında veya devre dışı bırakıldığında kullanılır.
Hugging Face, LibreTranslate veya Argos entegrasyonu için temel oluşturur.
"""

import os
import time
import requests
from typing import Optional, List, Dict
from dataclasses import dataclass

# Config'den dil isimlerini al
try:
    from config import LANGUAGE_NAMES
except ImportError:
    LANGUAGE_NAMES = {
        "auto": "Otomatik",
        "tr": "Türkçe",
        "en": "İngilizce",
        "de": "Almanca",
        "fr": "Fransızca",
        "es": "İspanyolca"
    }


@dataclass
class TranslationResult:
    """Çeviri sonucu"""
    text: str
    source_lang: str
    target_lang: str
    success: bool
    error: Optional[str] = None
    provider: str = "fallback"

    def __str__(self):
        return self.text if self.success else f"Hata: {self.error}"


class FallbackTranslator:
    """
    Fallback çeviri sistemi
    
    Öncelik sırası:
    1. Hugging Face Inference API (HF_TOKEN varsa)
    2. LibreTranslate (LIBRETRANSLATE_URL varsa)
    3. Passthrough (çeviri yapmadan döndür)
    """

    def __init__(self):
        """Translator başlat"""
        self.hf_token = os.environ.get("HF_TOKEN", "")
        self.libre_url = os.environ.get("LIBRETRANSLATE_URL", "")
        self.provider = os.environ.get("TRANSLATOR_PROVIDER", "hf")
        self._cache = {}
        self._hf_translator = None
        
        # Hangi provider aktif?
        self.active_provider = self._detect_provider()
        print(f"🌐 Çeviri Motoru: {self.active_provider}")

    def _detect_provider(self) -> str:
        """Aktif provider'ı tespit et"""
        # Manuel seçim varsa kullan
        if self.provider == "libre" and self.libre_url:
            return "libretranslate"
        elif self.provider == "hf" and self.hf_token:
            return "huggingface"
        
        # Otomatik tespit
        if self.hf_token:
            return "huggingface"
        elif self.libre_url:
            return "libretranslate"
        else:
            return "passthrough"

    def _get_hf_translator(self):
        """Lazy HF translator al"""
        if self._hf_translator is None:
            from translators.hf_translator import HuggingFaceTranslator
            self._hf_translator = HuggingFaceTranslator(self.hf_token)
        return self._hf_translator

    def translate(self, text: str, target_lang: str = "tr", source_lang: str = "auto",
                 doc_type: str = None, preserve_format: bool = True) -> TranslationResult:
        """
        Metni çevir

        Args:
            text: Çevrilecek metin
            target_lang: Hedef dil kodu
            source_lang: Kaynak dil kodu
            doc_type: Belge türü (kullanılmıyor, uyumluluk için)
            preserve_format: Format koruma (kullanılmıyor, uyumluluk için)

        Returns:
            TranslationResult: Çeviri sonucu
        """
        if not text or not text.strip():
            return TranslationResult(
                text=text,
                source_lang=source_lang,
                target_lang=target_lang,
                success=True,
                provider=self.active_provider
            )

        # Cache kontrolü
        cache_key = f"{source_lang}:{target_lang}:{text[:100]}"
        if cache_key in self._cache:
            return TranslationResult(
                text=self._cache[cache_key],
                source_lang=source_lang,
                target_lang=target_lang,
                success=True,
                provider=self.active_provider
            )

        # Provider'a göre çeviri yap
        try:
            if self.active_provider == "huggingface":
                result = self._translate_hf(text, target_lang, source_lang)
            elif self.active_provider == "libretranslate":
                result = self._translate_libre(text, target_lang, source_lang)
            else:
                # Passthrough - çeviri yapmadan döndür
                result = text
                
            # Cache'e ekle
            self._cache[cache_key] = result

            return TranslationResult(
                text=result,
                source_lang=source_lang,
                target_lang=target_lang,
                success=True,
                provider=self.active_provider
            )

        except Exception as e:
            print(f"⚠️ Çeviri hatası ({self.active_provider}): {e}")
            # Hata durumunda orijinal metni döndür
            return TranslationResult(
                text=text,
                source_lang=source_lang,
                target_lang=target_lang,
                success=False,
                error=str(e),
                provider=self.active_provider
            )

    def _translate_hf(self, text: str, target_lang: str, source_lang: str) -> str:
        """Hugging Face ile çeviri - Profesyonel HF Translator kullan"""
        hf_translator = self._get_hf_translator()
        result = hf_translator.translate(text, target_lang, source_lang)
        
        if result.success:
            return result.text
        else:
            raise Exception(result.error or "HF çeviri hatası")

    def _translate_libre(self, text: str, target_lang: str, source_lang: str) -> str:
        """LibreTranslate ile çeviri"""
        payload = {
            "q": text,
            "source": source_lang if source_lang != "auto" else "auto",
            "target": target_lang,
            "format": "text"
        }
        
        response = requests.post(
            f"{self.libre_url}/translate",
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        
        result = response.json()
        return result.get("translatedText", text)

    def translate_batch(self, texts: List[str], target_lang: str = "tr",
                       source_lang: str = "auto") -> List[TranslationResult]:
        """
        Birden çok metni çevir (batch)
        """
        results = []
        for i, text in enumerate(texts):
            if i % 5 == 0:
                print(f"📝 Çeviri: {i}/{len(texts)}")
            result = self.translate(text, target_lang, source_lang)
            results.append(result)
            # Rate limiting
            if i > 0 and i % 5 == 0:
                time.sleep(0.3)
        return results

    def translate_blocks(self, blocks: List[Dict], target_lang: str = "tr",
                        source_lang: str = "auto") -> List[str]:
        """Metin bloklarını çevir"""
        texts = [block.get("text", "") for block in blocks]
        results = self.translate_batch(texts, target_lang, source_lang)
        return [r.text if r.success else texts[i] for i, r in enumerate(results)]

    def clear_cache(self):
        """Çeviri cache'ini temizle"""
        self._cache.clear()

    def get_supported_languages(self) -> Dict[str, str]:
        """Desteklenen dilleri döndür"""
        return LANGUAGE_NAMES.copy()


# Singleton instance
_fallback_instance = None


def get_fallback_translator() -> FallbackTranslator:
    """Singleton fallback translator örneği al"""
    global _fallback_instance
    if _fallback_instance is None:
        _fallback_instance = FallbackTranslator()
    return _fallback_instance
