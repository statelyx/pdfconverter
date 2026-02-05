# -*- coding: utf-8 -*-
"""
Hugging Face Translator v2 - Professional Translation Module
Uses HF Inference API with proper token priority

Token Priority: WRITE -> READ -> API_KEY
Models: Helsinki-NLP/opus-mt-* for fast translation
"""

import os
import time
import requests
from typing import Optional, List, Dict
from dataclasses import dataclass


@dataclass
class TranslationResult:
    """Translation result"""
    text: str
    source_lang: str
    target_lang: str
    success: bool
    error: Optional[str] = None
    provider: str = "huggingface"
    model: str = ""

    def __str__(self):
        return self.text if self.success else f"Error: {self.error}"


# OPUS model map - best performance
OPUS_MODELS = {
    ("en", "tr"): "Helsinki-NLP/opus-mt-en-tr",
    ("tr", "en"): "Helsinki-NLP/opus-mt-tr-en",
    ("en", "de"): "Helsinki-NLP/opus-mt-en-de",
    ("de", "en"): "Helsinki-NLP/opus-mt-de-en",
    ("en", "fr"): "Helsinki-NLP/opus-mt-en-fr",
    ("fr", "en"): "Helsinki-NLP/opus-mt-fr-en",
    ("en", "es"): "Helsinki-NLP/opus-mt-en-es",
    ("es", "en"): "Helsinki-NLP/opus-mt-es-en",
    ("de", "tr"): "Helsinki-NLP/opus-mt-de-tr",
    ("tr", "de"): "Helsinki-NLP/opus-mt-tr-de",
}

# NLLB language codes
NLLB_LANG_CODES = {
    "en": "eng_Latn",
    "tr": "tur_Latn",
    "de": "deu_Latn",
    "fr": "fra_Latn",
    "es": "spa_Latn",
}


def get_hf_token() -> str:
    """
    Get HF token with correct priority:
    WRITE -> READ -> API_KEY
    """
    token = (
        os.environ.get("HUGGINGFACE_WRITE_API_KEY", "") or
        os.environ.get("HUGGINGFACE_READ_API_KEY", "") or
        os.environ.get("HUGGINGFACE_API_KEY", "") or
        os.environ.get("HF_TOKEN", "")
    )
    return token


class HFTranslatorV2:
    """
    Hugging Face Translator v2
    
    Features:
    - Correct token priority (WRITE -> READ -> API_KEY)
    - OPUS models for fast translation
    - NLLB fallback for unsupported pairs
    - Retry mechanism with exponential backoff
    - Cache support
    """

    def __init__(self, token: str = None):
        """Initialize translator"""
        self.token = token or get_hf_token()
        self._cache = {}
        self._retry_count = 3
        self._retry_delay = 2
        
        # Custom model overrides from ENV
        self.model_en_tr = os.environ.get("HF_MODEL_EN_TR", "Helsinki-NLP/opus-mt-en-tr")
        self.model_tr_en = os.environ.get("HF_MODEL_TR_EN", "Helsinki-NLP/opus-mt-tr-en")
        
        if self.token:
            token_preview = f"***{self.token[-4:]}" if len(self.token) > 4 else "***"
            print(f"🤗 HF Translator v2 initialized (token: {token_preview})")
        else:
            print("⚠️ NO HF TOKEN FOUND - Translation will fail!")

    def _get_headers(self) -> Dict:
        """Get API headers"""
        if not self.token:
            return {"Content-Type": "application/json"}
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def _select_model(self, source_lang: str, target_lang: str) -> str:
        """Select best model for language pair"""
        src = "en" if source_lang == "auto" else source_lang
        
        # Check custom model overrides
        if src == "en" and target_lang == "tr":
            return self.model_en_tr
        if src == "tr" and target_lang == "en":
            return self.model_tr_en
            
        # Check OPUS models
        key = (src, target_lang)
        if key in OPUS_MODELS:
            return OPUS_MODELS[key]
        
        # Fallback to NLLB
        return "facebook/nllb-200-distilled-600M"

    def translate(self, text: str, target_lang: str = "tr", source_lang: str = "auto",
                 doc_type: str = None, preserve_format: bool = True) -> TranslationResult:
        """
        Translate text
        
        Args:
            text: Text to translate
            target_lang: Target language code
            source_lang: Source language code
            
        Returns:
            TranslationResult
        """
        # Empty text check
        if not text or not text.strip():
            return TranslationResult(
                text=text,
                source_lang=source_lang,
                target_lang=target_lang,
                success=True,
                model="passthrough"
            )

        # Token check
        if not self.token:
            print(f"❌ NO TOKEN - Cannot translate: {text[:50]}...")
            return TranslationResult(
                text=text,
                source_lang=source_lang,
                target_lang=target_lang,
                success=False,
                error="No HF token available",
                model="none"
            )

        # Cache check
        cache_key = f"{source_lang}:{target_lang}:{hash(text)}"
        if cache_key in self._cache:
            return TranslationResult(
                text=self._cache[cache_key],
                source_lang=source_lang,
                target_lang=target_lang,
                success=True,
                model="cached"
            )

        # Select model
        model = self._select_model(source_lang, target_lang)
        
        # Translate with retry
        for attempt in range(self._retry_count):
            try:
                result = self._call_hf_api(text, model, source_lang, target_lang)
                
                # Cache result
                self._cache[cache_key] = result
                
                print(f"✅ Translated ({model}): {text[:30]}... -> {result[:30]}...")
                
                return TranslationResult(
                    text=result,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    success=True,
                    model=model
                )
                
            except Exception as e:
                error_msg = str(e)
                print(f"⚠️ Attempt {attempt + 1}/{self._retry_count} failed: {error_msg}")
                
                # Check if model is loading
                if "loading" in error_msg.lower() or "503" in error_msg:
                    wait_time = self._retry_delay * (attempt + 1)
                    print(f"⏳ Model loading, waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                
                # Other errors
                if attempt == self._retry_count - 1:
                    return TranslationResult(
                        text=text,
                        source_lang=source_lang,
                        target_lang=target_lang,
                        success=False,
                        error=error_msg,
                        model=model
                    )
                
                time.sleep(self._retry_delay)

        return TranslationResult(
            text=text,
            source_lang=source_lang,
            target_lang=target_lang,
            success=False,
            error="Max retries exceeded",
            model=model
        )

    def _call_hf_api(self, text: str, model: str, source_lang: str, target_lang: str) -> str:
        """Call HF Inference API - Updated to use router.huggingface.co"""
        # YENİ ENDPOINT - api-inference artık desteklenmiyor
        api_url = f"https://router.huggingface.co/hf-inference/models/{model}"
        
        # NLLB requires different payload
        if "nllb" in model.lower():
            src_code = NLLB_LANG_CODES.get(source_lang if source_lang != "auto" else "en", "eng_Latn")
            tgt_code = NLLB_LANG_CODES.get(target_lang, "tur_Latn")
            payload = {
                "inputs": text,
                "parameters": {
                    "src_lang": src_code,
                    "tgt_lang": tgt_code
                }
            }
        else:
            payload = {"inputs": text}
        
        response = requests.post(
            api_url,
            headers=self._get_headers(),
            json=payload,
            timeout=120
        )
        
        if response.status_code == 503:
            # Model is loading
            data = response.json()
            raise Exception(f"Model loading: {data.get('error', 'Unknown')}")
        
        if response.status_code != 200:
            error_data = response.json() if response.text else {}
            raise Exception(f"API Error {response.status_code}: {error_data}")
        
        result = response.json()
        
        if isinstance(result, list) and len(result) > 0:
            return result[0].get("translation_text", text)
        elif isinstance(result, dict):
            if "error" in result:
                raise Exception(result["error"])
            return result.get("translation_text", text)
        
        return text

    def translate_batch(self, texts: List[str], target_lang: str = "tr",
                       source_lang: str = "auto") -> List[TranslationResult]:
        """Translate multiple texts"""
        results = []
        total = len(texts)
        
        for i, text in enumerate(texts):
            print(f"📝 Translating {i + 1}/{total}...")
            result = self.translate(text, target_lang, source_lang)
            results.append(result)
            
            # Rate limiting for free tier
            if i > 0 and i % 3 == 0:
                time.sleep(0.5)
        
        return results

    def clear_cache(self):
        """Clear translation cache"""
        self._cache.clear()


# Singleton instance
_translator_instance = None


def get_translator():
    """Get singleton translator instance"""
    global _translator_instance
    if _translator_instance is None:
        _translator_instance = HFTranslatorV2()
    return _translator_instance


def translate_text(text: str, target_lang: str = "tr", source_lang: str = "auto") -> str:
    """Simple translation function"""
    translator = get_translator()
    result = translator.translate(text, target_lang, source_lang)
    return result.text
