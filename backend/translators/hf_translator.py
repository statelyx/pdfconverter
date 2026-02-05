# -*- coding: utf-8 -*-
"""
Hugging Face Translator - Ücretsiz AI Çeviri Modülü
Hugging Face Inference API ile profesyonel çeviri

Desteklenen modeller:
- Helsinki-NLP/opus-mt-* (hızlı, dil çiftleri için)
- facebook/nllb-200-distilled-600M (çoklu dil)
- facebook/mbart-large-50-many-to-many-mmt (alternatif)
"""

import os
import time
import requests
from typing import Optional, List, Dict
from dataclasses import dataclass

# Config'den dil isimlerini al
try:
    from config import LANGUAGE_NAMES, HF_TOKEN as CONFIG_HF_TOKEN
except ImportError:
    LANGUAGE_NAMES = {
        "auto": "Otomatik",
        "tr": "Türkçe",
        "en": "İngilizce",
        "de": "Almanca",
        "fr": "Fransızca",
        "es": "İspanyolca"
    }
    CONFIG_HF_TOKEN = ""


@dataclass
class TranslationResult:
    """Çeviri sonucu"""
    text: str
    source_lang: str
    target_lang: str
    success: bool
    error: Optional[str] = None
    provider: str = "huggingface"
    model: str = ""

    def __str__(self):
        return self.text if self.success else f"Hata: {self.error}"


# OPUS model haritası - en iyi performans için
OPUS_MODELS = {
    ("en", "tr"): "Helsinki-NLP/opus-mt-en-tr",
    ("tr", "en"): "Helsinki-NLP/opus-mt-tr-en",
    ("en", "de"): "Helsinki-NLP/opus-mt-en-de",
    ("de", "en"): "Helsinki-NLP/opus-mt-de-en",
    ("en", "fr"): "Helsinki-NLP/opus-mt-en-fr",
    ("fr", "en"): "Helsinki-NLP/opus-mt-fr-en",
    ("en", "es"): "Helsinki-NLP/opus-mt-en-es",
    ("es", "en"): "Helsinki-NLP/opus-mt-es-en",
    ("en", "it"): "Helsinki-NLP/opus-mt-en-it",
    ("it", "en"): "Helsinki-NLP/opus-mt-it-en",
    ("en", "ru"): "Helsinki-NLP/opus-mt-en-ru",
    ("ru", "en"): "Helsinki-NLP/opus-mt-ru-en",
    ("en", "ar"): "Helsinki-NLP/opus-mt-en-ar",
    ("ar", "en"): "Helsinki-NLP/opus-mt-ar-en",
    ("en", "zh"): "Helsinki-NLP/opus-mt-en-zh",
    ("zh", "en"): "Helsinki-NLP/opus-mt-zh-en",
}

# NLLB dil kodları (farklı format kullanıyor)
NLLB_LANG_CODES = {
    "en": "eng_Latn",
    "tr": "tur_Latn",
    "de": "deu_Latn",
    "fr": "fra_Latn",
    "es": "spa_Latn",
    "it": "ita_Latn",
    "ru": "rus_Cyrl",
    "ar": "arb_Arab",
    "zh": "zho_Hans",
    "ja": "jpn_Jpan",
    "ko": "kor_Hang",
}


class HuggingFaceTranslator:
    """
    Hugging Face Inference API ile çeviri
    
    Özellikler:
    - OPUS modelleri ile hızlı çeviri (dil çiftleri için)
    - NLLB ile çoklu dil desteği (fallback)
    - Otomatik model seçimi
    - Retry mekanizması
    - Cache desteği
    """

    def __init__(self, token: str = None):
        """
        HF Translator başlat
        
        Args:
            token: Hugging Face API token (opsiyonel, ENV'den de alınabilir)
        """
        self.token = token or os.environ.get("HF_TOKEN", "") or CONFIG_HF_TOKEN
        self._cache = {}
        self._model_status = {}  # Model kullanılabilirlik durumu
        
        if self.token:
            print(f"🤗 Hugging Face Translator başlatıldı (token: ***{self.token[-4:]})")
        else:
            print("⚠️ HF_TOKEN bulunamadı - çeviri passthrough modunda çalışacak")

    def _get_headers(self) -> Dict:
        """API headers"""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _select_model(self, source_lang: str, target_lang: str) -> tuple:
        """
        En uygun modeli seç
        
        Returns:
            (model_name, model_type) tuple
        """
        # Auto ise varsayılan olarak en kullan
        src = "en" if source_lang == "auto" else source_lang
        tgt = target_lang
        
        # Önce OPUS modeli dene (daha hızlı)
        opus_key = (src, tgt)
        if opus_key in OPUS_MODELS:
            return OPUS_MODELS[opus_key], "opus"
        
        # Sonra ters yönü dene
        reverse_key = (tgt, src)
        if reverse_key in OPUS_MODELS:
            # Ters model var ama biz ters çeviri yapamayız
            pass
        
        # NLLB kullan (çoklu dil)
        return "facebook/nllb-200-distilled-600M", "nllb"

    def translate(self, text: str, target_lang: str = "tr", source_lang: str = "auto",
                 doc_type: str = None, preserve_format: bool = True) -> TranslationResult:
        """
        Metni çevir

        Args:
            text: Çevrilecek metin
            target_lang: Hedef dil kodu
            source_lang: Kaynak dil kodu
            doc_type: Belge türü (uyumluluk için)
            preserve_format: Format koruma (uyumluluk için)

        Returns:
            TranslationResult: Çeviri sonucu
        """
        # Boş metin kontrolü
        if not text or not text.strip():
            return TranslationResult(
                text=text,
                source_lang=source_lang,
                target_lang=target_lang,
                success=True,
                model="passthrough"
            )

        # Token yoksa passthrough
        if not self.token:
            return TranslationResult(
                text=text,
                source_lang=source_lang,
                target_lang=target_lang,
                success=True,
                error="Token yok, çeviri yapılmadı",
                model="passthrough"
            )

        # Cache kontrolü
        cache_key = f"{source_lang}:{target_lang}:{text[:100]}"
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            return TranslationResult(
                text=cached["text"],
                source_lang=source_lang,
                target_lang=target_lang,
                success=True,
                model=cached["model"] + " (cached)"
            )

        # Model seç
        model_name, model_type = self._select_model(source_lang, target_lang)
        
        # Çeviri yap
        try:
            if model_type == "opus":
                result = self._translate_opus(text, model_name)
            else:
                result = self._translate_nllb(text, source_lang, target_lang, model_name)
            
            # Cache'e ekle
            self._cache[cache_key] = {"text": result, "model": model_name}
            
            return TranslationResult(
                text=result,
                source_lang=source_lang,
                target_lang=target_lang,
                success=True,
                model=model_name
            )

        except Exception as e:
            error_msg = str(e)
            print(f"⚠️ HF Çeviri hatası ({model_name}): {error_msg}")
            
            # Model yükleniyorsa bekle ve tekrar dene
            if "loading" in error_msg.lower():
                print("⏳ Model yükleniyor, 20 saniye bekleniyor...")
                time.sleep(20)
                return self.translate(text, target_lang, source_lang, doc_type, preserve_format)
            
            return TranslationResult(
                text=text,
                source_lang=source_lang,
                target_lang=target_lang,
                success=False,
                error=error_msg,
                model=model_name
            )

    def _translate_opus(self, text: str, model_name: str) -> str:
        """OPUS modeli ile çeviri"""
        api_url = f"https://api-inference.huggingface.co/models/{model_name}"
        
        response = requests.post(
            api_url,
            headers=self._get_headers(),
            json={"inputs": text},
            timeout=60
        )
        
        if response.status_code != 200:
            error_data = response.json() if response.text else {}
            raise Exception(f"API Error {response.status_code}: {error_data}")
        
        result = response.json()
        
        if isinstance(result, list) and len(result) > 0:
            return result[0].get("translation_text", text)
        elif isinstance(result, dict) and "error" in result:
            raise Exception(result["error"])
        
        return text

    def _translate_nllb(self, text: str, source_lang: str, target_lang: str, model_name: str) -> str:
        """NLLB modeli ile çeviri"""
        api_url = f"https://api-inference.huggingface.co/models/{model_name}"
        
        # NLLB dil kodlarını al
        src_code = NLLB_LANG_CODES.get(source_lang if source_lang != "auto" else "en", "eng_Latn")
        tgt_code = NLLB_LANG_CODES.get(target_lang, "tur_Latn")
        
        payload = {
            "inputs": text,
            "parameters": {
                "src_lang": src_code,
                "tgt_lang": tgt_code
            }
        }
        
        response = requests.post(
            api_url,
            headers=self._get_headers(),
            json=payload,
            timeout=60
        )
        
        if response.status_code != 200:
            error_data = response.json() if response.text else {}
            raise Exception(f"API Error {response.status_code}: {error_data}")
        
        result = response.json()
        
        if isinstance(result, list) and len(result) > 0:
            return result[0].get("translation_text", text)
        elif isinstance(result, dict) and "error" in result:
            raise Exception(result["error"])
        
        return text

    def translate_batch(self, texts: List[str], target_lang: str = "tr",
                       source_lang: str = "auto") -> List[TranslationResult]:
        """
        Birden çok metni çevir (batch)
        """
        results = []
        total = len(texts)
        
        for i, text in enumerate(texts):
            if i % 5 == 0:
                print(f"📝 Çeviri: {i}/{total}")
            
            result = self.translate(text, target_lang, source_lang)
            results.append(result)
            
            # Rate limiting - HF free tier için
            if i > 0 and i % 5 == 0:
                time.sleep(1)
        
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
_hf_translator_instance = None


def get_hf_translator() -> HuggingFaceTranslator:
    """Singleton HF translator örneği al"""
    global _hf_translator_instance
    if _hf_translator_instance is None:
        _hf_translator_instance = HuggingFaceTranslator()
    return _hf_translator_instance
