# -*- coding: utf-8 -*-
"""
Multi-Provider Translator v3 - Profesyonel Çoklu Çeviri Sistemi
Sıfır maliyet, maksimum güvenilirlik

PROVIDER ÖNCELİK SIRASI:
1. Hugging Face Router API (YENİ ENDPOINT)
2. Argos Translate (Offline, ücretsiz)
3. LibreTranslate (Self-hosted)
4. MyMemory API (Ücretsiz, günlük limit)
5. Lingva Translate (Ücretsiz proxy)

Token Priority: WRITE -> READ -> API_KEY
"""

import os
import time
import requests
from typing import Optional, List, Dict, Callable
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib3

# SSL warnings'ı gizle (Railway SSL certificate issues için)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


@dataclass
class TranslationResult:
    """Çeviri sonucu"""
    text: str
    source_lang: str
    target_lang: str
    success: bool
    error: Optional[str] = None
    provider: str = "unknown"
    model: str = ""
    confidence: float = 1.0

    def __str__(self):
        return self.text if self.success else f"Hata: {self.error}"


# ============================================================================
# DİL KODLARI VE MODEL HARİTALARI
# ============================================================================

# Helsinki-NLP OPUS modelleri - En hızlı ve güvenilir
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
    ("de", "tr"): "Helsinki-NLP/opus-mt-de-tr",
    ("tr", "de"): "Helsinki-NLP/opus-mt-tr-de",
    ("fr", "tr"): "Helsinki-NLP/opus-mt-fr-tr",
    ("tr", "fr"): "Helsinki-NLP/opus-mt-tr-fr",
}

# NLLB dil kodları (Facebook modeli için)
NLLB_LANG_CODES = {
    "en": "eng_Latn", "tr": "tur_Latn", "de": "deu_Latn",
    "fr": "fra_Latn", "es": "spa_Latn", "it": "ita_Latn",
    "ru": "rus_Cyrl", "ar": "arb_Arab", "zh": "zho_Hans",
    "ja": "jpn_Jpan", "ko": "kor_Hang", "nl": "nld_Latn",
    "pl": "pol_Latn", "pt": "por_Latn", "sv": "swe_Latn",
}

# Argos Translate dil kodları
ARGOS_LANG_CODES = {
    "en": "en", "tr": "tr", "de": "de", "fr": "fr",
    "es": "es", "it": "it", "ru": "ru", "ar": "ar",
    "zh": "zh", "ja": "ja", "ko": "ko", "nl": "nl",
    "pl": "pl", "pt": "pt",
}


def get_hf_token() -> str:
    """HF token al - WRITE -> READ -> API_KEY önceliği"""
    return (
        os.environ.get("HUGGINGFACE_WRITE_API_KEY", "") or
        os.environ.get("HUGGINGFACE_READ_API_KEY", "") or
        os.environ.get("HUGGINGFACE_API_KEY", "") or
        os.environ.get("HF_TOKEN", "")
    )


# ============================================================================
# PROVIDER SINIFLAR
# ============================================================================

class HuggingFaceProvider:
    """
    Hugging Face Router API Provider
    YENİ ENDPOINT: router.huggingface.co
    """
    
    name = "huggingface"
    
    def __init__(self, token: str = None):
        self.token = token or get_hf_token()
        self.base_url = "https://router.huggingface.co/hf-inference/models"
        self.timeout = 120
        self.available = bool(self.token)
        
    def _get_headers(self) -> Dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        } if self.token else {"Content-Type": "application/json"}
    
    def _select_model(self, source_lang: str, target_lang: str) -> str:
        src = "en" if source_lang == "auto" else source_lang
        key = (src, target_lang)
        return OPUS_MODELS.get(key, "facebook/nllb-200-distilled-600M")
    
    def translate(self, text: str, target_lang: str, source_lang: str = "auto") -> TranslationResult:
        if not self.available:
            return TranslationResult(text=text, source_lang=source_lang, target_lang=target_lang,
                                    success=False, error="No HF token", provider=self.name)
        
        model = self._select_model(source_lang, target_lang)
        api_url = f"{self.base_url}/{model}"
        
        # NLLB için özel payload
        if "nllb" in model.lower():
            src_code = NLLB_LANG_CODES.get(source_lang if source_lang != "auto" else "en", "eng_Latn")
            tgt_code = NLLB_LANG_CODES.get(target_lang, "tur_Latn")
            payload = {"inputs": text, "parameters": {"src_lang": src_code, "tgt_lang": tgt_code}}
        else:
            payload = {"inputs": text}
        
        try:
            response = requests.post(api_url, headers=self._get_headers(), json=payload, timeout=self.timeout)
            
            # Boş yanıt kontrolü
            if not response.text or len(response.text.strip()) == 0:
                raise Exception("Boş API yanıtı")
            
            # HTML yanıt kontrolü (hata sayfası)
            if response.text.strip().startswith("<!") or response.text.strip().startswith("<html"):
                raise Exception("API HTML hata sayfası döndürdü")
            
            if response.status_code == 503:
                try:
                    data = response.json()
                    raise Exception(f"Model yükleniyor: {data.get('error', 'Bekleyin')}")
                except:
                    raise Exception("Model yükleniyor, lütfen bekleyin...")
            
            if response.status_code != 200:
                try:
                    error_data = response.json()
                except:
                    error_data = {"raw": response.text[:200]}
                raise Exception(f"API Hatası {response.status_code}: {error_data}")
            
            result = response.json()
            
            if isinstance(result, list) and len(result) > 0:
                translated = result[0].get("translation_text", text)
            elif isinstance(result, dict):
                if "error" in result:
                    raise Exception(result["error"])
                translated = result.get("translation_text", text)
            else:
                translated = text
            
            return TranslationResult(
                text=translated, source_lang=source_lang, target_lang=target_lang,
                success=True, provider=self.name, model=model
            )
            
        except requests.exceptions.JSONDecodeError as e:
            return TranslationResult(
                text=text, source_lang=source_lang, target_lang=target_lang,
                success=False, error=f"JSON parse hatası: {response.text[:100] if response else 'N/A'}", 
                provider=self.name, model=model
            )
        except Exception as e:
            return TranslationResult(
                text=text, source_lang=source_lang, target_lang=target_lang,
                success=False, error=str(e), provider=self.name, model=model
            )


class MyMemoryProvider:
    """
    MyMemory Translation API - Ücretsiz
    Günlük 5000 kelime limiti (anonim)
    API key ile 30000 kelime/gün
    SSL ve retry optimizasyonlu
    """

    name = "mymemory"

    def __init__(self, email: str = None):
        self.email = email or os.environ.get("MYMEMORY_EMAIL", "")
        self.base_url = "https://api.mymemory.translated.net/get"
        self.timeout = 30
        self.max_retries = 3
        self.available = True

        # Session oluştur - SSL sorunları için
        self.session = requests.Session()
        # SSL verify'i kapat (Railway'de SSL certificate sorunları için)
        self.session.verify = False
        # Warning'leri gizle
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def translate(self, text: str, target_lang: str, source_lang: str = "auto") -> TranslationResult:
        src = "en" if source_lang == "auto" else source_lang
        langpair = f"{src}|{target_lang}"

        params = {"q": text, "langpair": langpair}
        if self.email:
            params["de"] = self.email

        # Retry mekanizması
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(self.base_url, params=params, timeout=self.timeout)

                if response.status_code != 200:
                    raise Exception(f"HTTP {response.status_code}")

                data = response.json()

                if data.get("responseStatus") != 200:
                    raise Exception(data.get("responseDetails", "Bilinmeyen hata"))

                translated = data.get("responseData", {}).get("translatedText", text)
                match_quality = data.get("responseData", {}).get("match", 0)

                return TranslationResult(
                    text=translated, source_lang=src, target_lang=target_lang,
                    success=True, provider=self.name, confidence=match_quality
                )

            except (requests.exceptions.SSLError,
                    requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout) as e:
                last_error = str(e)
                if attempt < self.max_retries - 1:
                    time.sleep(0.5 * (attempt + 1))  # Exponential backoff
                    continue
            except Exception as e:
                last_error = str(e)
                break

        return TranslationResult(
            text=text, source_lang=source_lang, target_lang=target_lang,
            success=False, error=f"MyMemory hatası (retry: {self.max_retries}): {last_error}",
            provider=self.name
        )


class LingvaProvider:
    """
    Lingva Translate - Ücretsiz Google Translate Proxy
    https://lingva.ml alternatif instance'lar kullanılabilir
    """
    
    name = "lingva"
    
    def __init__(self, instance_url: str = None):
        # Birden fazla instance dene
        self.instances = [
            instance_url or os.environ.get("LINGVA_URL", ""),
            "https://lingva.ml",
            "https://translate.plausibility.cloud",
            "https://lingva.garuber.eu",
        ]
        self.timeout = 10  # 30'dan 10'a düşürüldü
        self.available = True
        
    def translate(self, text: str, target_lang: str, source_lang: str = "auto") -> TranslationResult:
        src = "en" if source_lang == "auto" else source_lang
        
        for instance in self.instances:
            if not instance:
                continue
                
            try:
                # URL encode text
                import urllib.parse
                encoded_text = urllib.parse.quote(text)
                url = f"{instance}/api/v1/{src}/{target_lang}/{encoded_text}"
                
                response = requests.get(url, timeout=self.timeout)
                
                if response.status_code == 200:
                    data = response.json()
                    translated = data.get("translation", text)
                    
                    return TranslationResult(
                        text=translated, source_lang=src, target_lang=target_lang,
                        success=True, provider=f"{self.name}:{instance}"
                    )
                    
            except Exception as e:
                continue  # Sonraki instance'ı dene
        
        return TranslationResult(
            text=text, source_lang=source_lang, target_lang=target_lang,
            success=False, error="Tüm Lingva instance'ları başarısız", provider=self.name
        )


class LibreTranslateProvider:
    """
    LibreTranslate - Self-hosted ücretsiz çeviri
    """
    
    name = "libretranslate"
    
    def __init__(self, url: str = None, api_key: str = None):
        self.url = url or os.environ.get("LIBRETRANSLATE_URL", "")
        self.api_key = api_key or os.environ.get("LIBRETRANSLATE_API_KEY", "")
        self.timeout = 30
        self.available = bool(self.url)
        
    def translate(self, text: str, target_lang: str, source_lang: str = "auto") -> TranslationResult:
        if not self.available:
            return TranslationResult(text=text, source_lang=source_lang, target_lang=target_lang,
                                    success=False, error="LibreTranslate URL yok", provider=self.name)
        
        payload = {
            "q": text,
            "source": source_lang if source_lang != "auto" else "auto",
            "target": target_lang,
            "format": "text"
        }
        
        if self.api_key:
            payload["api_key"] = self.api_key
        
        try:
            response = requests.post(f"{self.url}/translate", json=payload, timeout=self.timeout)
            
            if response.status_code != 200:
                raise Exception(f"HTTP {response.status_code}")
            
            data = response.json()
            translated = data.get("translatedText", text)
            
            return TranslationResult(
                text=translated, source_lang=source_lang, target_lang=target_lang,
                success=True, provider=self.name
            )
            
        except Exception as e:
            return TranslationResult(
                text=text, source_lang=source_lang, target_lang=target_lang,
                success=False, error=str(e), provider=self.name
            )



# ============================================================================
# ANA TRANSLATOR SINIFI
# ============================================================================

class MultiProviderTranslator:
    """
    Çoklu Provider Çeviri Sistemi
    
    Özellikler:
    - Otomatik failover (bir provider başarısız olursa diğerine geç)
    - Paralel çeviri desteği
    - Akıllı cache
    - Rate limiting
    """
    
    def __init__(self, config: Dict = None):
        """
        Translator başlat
        
        Args:
            config: Yapılandırma
                - providers: Provider listesi ["huggingface", "mymemory", "lingva", "libretranslate"]
                - parallel: Paralel çeviri aktif mi
                - cache_enabled: Cache aktif mi
        """
        self.config = config or {}
        self._cache = {}
        self._cache_enabled = self.config.get("cache_enabled", True)
        
        # Provider'ları başlat
        self.providers = self._init_providers()
        
        # Aktif provider'ları logla
        active = [p.name for p in self.providers if p.available]
        print(f"🌐 MultiProviderTranslator başlatıldı")
        print(f"   Aktif provider'lar: {active}")
    
    def _init_providers(self) -> List:
        """Provider'ları öncelik sırasına göre başlat"""
        # MyMemory şu an çalışıyor, onu birincil yapalım
        provider_order = self.config.get("providers", [
            "mymemory", "huggingface", "lingva", "libretranslate"
        ])
        
        provider_map = {
            "huggingface": HuggingFaceProvider,
            "mymemory": MyMemoryProvider,
            "lingva": LingvaProvider,
            "libretranslate": LibreTranslateProvider,
        }
        
        providers = []
        for name in provider_order:
            if name in provider_map:
                try:
                    provider = provider_map[name]()
                    providers.append(provider)
                except Exception as e:
                    print(f"⚠️ {name} provider başlatılamadı: {e}")
        
        return providers
    
    def translate(self, text: str, target_lang: str = "tr", source_lang: str = "auto",
                 doc_type: str = None, preserve_format: bool = True) -> TranslationResult:
        """
        Metni çevir - Failover destekli
        
        Args:
            text: Çevrilecek metin
            target_lang: Hedef dil
            source_lang: Kaynak dil
            
        Returns:
            TranslationResult
        """
        # Boş metin kontrolü
        if not text or not text.strip():
            return TranslationResult(
                text=text, source_lang=source_lang, target_lang=target_lang,
                success=True, provider="passthrough"
            )
        
        # Cache kontrolü
        if self._cache_enabled:
            cache_key = f"{source_lang}:{target_lang}:{hash(text)}"
            if cache_key in self._cache:
                cached = self._cache[cache_key]
                return TranslationResult(
                    text=cached, source_lang=source_lang, target_lang=target_lang,
                    success=True, provider="cache"
                )
        
        # Provider'ları sırayla dene
        last_error = None
        for provider in self.providers:
            if not provider.available:
                continue
            
            try:
                result = provider.translate(text, target_lang, source_lang)
                
                if result.success:
                    # Cache'e ekle
                    if self._cache_enabled:
                        self._cache[cache_key] = result.text
                    
                    print(f"✅ Çeviri ({result.provider}): {text[:30]}... → {result.text[:30]}...")
                    return result
                else:
                    last_error = result.error
                    print(f"⚠️ {provider.name} başarısız: {result.error}")
                    
            except Exception as e:
                last_error = str(e)
                print(f"⚠️ {provider.name} hata: {e}")
                continue
        
        # Tüm provider'lar başarısız
        print(f"❌ Tüm provider'lar başarısız oldu: {text[:50]}...")
        return TranslationResult(
            text=text, source_lang=source_lang, target_lang=target_lang,
            success=False, error=f"Tüm provider'lar başarısız: {last_error}",
            provider="none"
        )
    
    def translate_batch(self, texts: List[str], target_lang: str = "tr",
                       source_lang: str = "auto", parallel: bool = False) -> List[TranslationResult]:
        """
        Toplu çeviri
        
        Args:
            texts: Metin listesi
            target_lang: Hedef dil
            source_lang: Kaynak dil
            parallel: Paralel çeviri
            
        Returns:
            List[TranslationResult]
        """
        if parallel and len(texts) > 1:
            return self._translate_parallel(texts, target_lang, source_lang)
        
        results = []
        total = len(texts)
        
        for i, text in enumerate(texts):
            if i % 10 == 0:
                print(f"📝 Çeviri: {i}/{total}")
            
            result = self.translate(text, target_lang, source_lang)
            results.append(result)
            
            # Rate limiting
            if i > 0 and i % 5 == 0:
                time.sleep(0.3)
        
        return results
    
    def _translate_parallel(self, texts: List[str], target_lang: str,
                           source_lang: str, max_workers: int = 3) -> List[TranslationResult]:
        """Paralel çeviri"""
        results = [None] * len(texts)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {
                executor.submit(self.translate, text, target_lang, source_lang): i
                for i, text in enumerate(texts)
            }
            
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    results[idx] = TranslationResult(
                        text=texts[idx], source_lang=source_lang, target_lang=target_lang,
                        success=False, error=str(e), provider="parallel_error"
                    )
        
        return results
    
    def clear_cache(self):
        """Cache temizle"""
        self._cache.clear()
        print("🗑️ Çeviri cache temizlendi")
    
    def get_provider_status(self) -> Dict:
        """Provider durumlarını al"""
        return {
            p.name: {
                "available": p.available,
                "type": type(p).__name__
            }
            for p in self.providers
        }


# ============================================================================
# SINGLETON VE YARDIMCI FONKSİYONLAR
# ============================================================================

_translator_instance = None


def get_translator() -> MultiProviderTranslator:
    """Singleton translator örneği al"""
    global _translator_instance
    if _translator_instance is None:
        _translator_instance = MultiProviderTranslator()
    return _translator_instance


def translate_text(text: str, target_lang: str = "tr", source_lang: str = "auto") -> str:
    """Basit çeviri fonksiyonu"""
    translator = get_translator()
    result = translator.translate(text, target_lang, source_lang)
    return result.text


def translate_batch(texts: List[str], target_lang: str = "tr", source_lang: str = "auto") -> List[str]:
    """Toplu çeviri fonksiyonu"""
    translator = get_translator()
    results = translator.translate_batch(texts, target_lang, source_lang)
    return [r.text for r in results]


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  Multi-Provider Translator Test")
    print("="*60 + "\n")
    
    translator = get_translator()
    
    # Provider durumları
    print("Provider Durumları:")
    for name, status in translator.get_provider_status().items():
        emoji = "✅" if status["available"] else "❌"
        print(f"  {emoji} {name}: {status['available']}")
    
    # Test çevirisi
    test_texts = [
        "Hello, how are you?",
        "This is a test document.",
        "The weather is nice today."
    ]
    
    print("\nTest Çevirileri (EN → TR):")
    for text in test_texts:
        result = translator.translate(text, "tr", "en")
        status = "✅" if result.success else "❌"
        print(f"  {status} [{result.provider}] {text} → {result.text}")
    
    print("\n" + "="*60)
