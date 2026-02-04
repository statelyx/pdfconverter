# -*- coding: utf-8 -*-
"""
Gemini Translator - AI Çeviri Modülü
Google Gemini API ile profesyonel çeviri
"""

import time
import google.generativeai as genai
from typing import Optional, List, Dict
from dataclasses import dataclass

from config import (
    GEMINI_API_KEY,
    AI_MODEL,
    AI_MAX_RETRIES,
    AI_TIMEOUT,
    AI_BATCH_SIZE,
    LANGUAGE_NAMES
)


@dataclass
class TranslationResult:
    """Çeviri sonucu"""
    text: str
    source_lang: str
    target_lang: str
    success: bool
    error: Optional[str] = None

    def __str__(self):
        return self.text if self.success else f"Hata: {self.error}"


class ContextManager:
    """
    Çeviri bağlam yöneticisi
    Belge türüne göre bağlam koruyan çeviri prompt'ları oluşturur
    """

    DOCUMENT_TYPES = {
        "legal": {
            "name": "Hukuki Belge",
            "context": "Bu bir hukuki belgedir. Terimlerin resmi ve hukuki karşılıklarını kullan.",
            "tone": "resmi, hukuki"
        },
        "medical": {
            "name": "Tıbbi Belge",
            "context": "Bu bir tıbbi belgedir. Medikal terimlerin doğru karşılıklarını kullan.",
            "tone": "profesyonel, tıbbi"
        },
        "business": {
            "name": "İş Belgesi",
            "context": "Bu bir iş belgesidir. Profesyonel iş dilini kullan.",
            "tone": "profesyonel, kurumsal"
        },
        "academic": {
            "name": "Akademik Belge",
            "context": "Bu bir akademik belgedir. Bilimsel terminolojiyi koru.",
            "tone": "akademik, bilimsel"
        },
        "general": {
            "name": "Genel Belge",
            "context": "Bu genel amaçlı bir belgedir.",
            "tone": "doğal, akıcı"
        }
    }

    @staticmethod
    def detect_document_type(text: str) -> str:
        """
        Metinden belge türü tespit et

        Args:
            text: Metin içeriği

        Returns:
            str: Belge türü
        """
        keywords = {
            "legal": ["mahkeme", "dava", "hukuk", "yasa", "kanun", "madde", "fıkra",
                     "court", "law", "legal", "article", "contract", "agreement"],
            "medical": ["hasta", "tedavi", "tanı", "ilaç", "rapor", "sağlık",
                       "patient", "treatment", "diagnosis", "medical", "health"],
            "business": ["fatura", "sözleşme", "şirket", "müşteri", "sipariş",
                        "invoice", "company", "customer", "order", "business"],
            "academic": ["araştırma", "çalışma", "makale", "tezi", "üniversite",
                        "research", "study", "paper", "thesis", "university"]
        }

        text_lower = text.lower()
        scores = {}

        for doc_type, words in keywords.items():
            scores[doc_type] = sum(1 for word in words if word in text_lower)

        # En yüksek puanlı türü seç
        if scores:
            max_type = max(scores, key=scores.get)
            if scores[max_type] > 0:
                return max_type

        return "general"

    @staticmethod
    def build_prompt(text: str, target_lang: str, source_lang: str = "auto",
                    doc_type: str = None, preserve_format: bool = True) -> str:
        """
        AI için çeviri prompt'u oluştur

        Args:
            text: Çevrilecek metin
            target_lang: Hedef dil
            source_lang: Kaynak dil
            doc_type: Belge türü
            preserve_format: Format koruma

        Returns:
            str: Prompt
        """
        if doc_type is None:
            doc_type = ContextManager.detect_document_type(text)

        doc_info = ContextManager.DOCUMENT_TYPES.get(doc_type,
                     ContextManager.DOCUMENT_TYPES["general"])

        target_name = LANGUAGE_NAMES.get(target_lang, target_lang)

        prompt = f"""Sen profesyonel bir çevirmensin. Aşağıdaki metni {target_name}'ye çevir.

Belge Türü: {doc_info['name']}
Bağlam: {doc_info['context']}
Ton: {doc_info['tone']}

Kurallar:
1. Sadece çevrilmiş metni döndür, açıklama yapma
2. Satır sonlarını ve paragraf yapısını koru
3. Özel isimleri, tarihleri, sayıları koru
4. Türkçe karakterleri (ç, ğ, ı, ö, ş, ü) koru
5. Profesyonel ve doğal bir dil kullan

Çevrilecek Metin:
{text}"""

        return prompt


class GeminiTranslator:
    """
    Google Gemini API ile profesyonel çeviri
    Bağlam koruyan, format-duyarlı çeviri
    """

    def __init__(self, api_key: str = None, model: str = None):
        """
        Gemini Translator başlat

        Args:
            api_key: Gemini API anahtarı
            model: Model adı
        """
        self.api_key = api_key or GEMINI_API_KEY
        self.model_name = model or AI_MODEL
        self._init_model()
        self._cache = {}

    def _init_model(self):
        """Modeli başlat"""
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(self.model_name)

    def translate(self, text: str, target_lang: str = "tr", source_lang: str = "auto",
                 doc_type: str = None, preserve_format: bool = True) -> TranslationResult:
        """
        Metni çevir

        Args:
            text: Çevrilecek metin
            target_lang: Hedef dil kodu
            source_lang: Kaynak dil kodu
            doc_type: Belge türü
            preserve_format: Format koruma

        Returns:
            TranslationResult: Çeviri sonucu
        """
        if not text or not text.strip():
            return TranslationResult(
                text=text,
                source_lang=source_lang,
                target_lang=target_lang,
                success=True
            )

        # Cache kontrolü
        cache_key = f"{source_lang}:{target_lang}:{text[:100]}"
        if cache_key in self._cache:
            return TranslationResult(
                text=self._cache[cache_key],
                source_lang=source_lang,
                target_lang=target_lang,
                success=True
            )

        # Prompt oluştur
        prompt = ContextManager.build_prompt(
            text, target_lang, source_lang, doc_type, preserve_format
        )

        # Çeviriyi dene
        for attempt in range(AI_MAX_RETRIES):
            try:
                response = self.model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.3,
                        max_output_tokens=4096,
                    )
                )

                result = response.text.strip()

                # Cache'e ekle
                self._cache[cache_key] = result

                return TranslationResult(
                    text=result,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    success=True
                )

            except Exception as e:
                if attempt < AI_MAX_RETRIES - 1:
                    time.sleep(1)  # Retry önce bekle
                    continue
                else:
                    return TranslationResult(
                        text=text,
                        source_lang=source_lang,
                        target_lang=target_lang,
                        success=False,
                        error=str(e)
                    )

    def translate_batch(self, texts: List[str], target_lang: str = "tr",
                       source_lang: str = "auto") -> List[TranslationResult]:
        """
        Birden çok metni çevir (batch)

        Args:
            texts: Metin listesi
            target_lang: Hedef dil
            source_lang: Kaynak dil

        Returns:
            List[TranslationResult]: Çeviri sonuçları
        """
        results = []

        for i, text in enumerate(texts):
            # Progress
            if i % AI_BATCH_SIZE == 0:
                print(f"📝 Çeviri: {i}/{len(texts)}")

            result = self.translate(text, target_lang, source_lang)
            results.append(result)

            # Rate limiting için kısa bekleme
            if i > 0 and i % AI_BATCH_SIZE == 0:
                time.sleep(0.5)

        return results

    def translate_blocks(self, blocks: List[Dict], target_lang: str = "tr",
                        source_lang: str = "auto") -> List[str]:
        """
        Metin bloklarını çevir

        Args:
            blocks: {"text": str, "bbox": tuple, ...} formatında blok listesi
            target_lang: Hedef dil
            source_lang: Kaynak dil

        Returns:
            List[str]: Çevrili metinler
        """
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
_translator_instance = None


def get_translator() -> GeminiTranslator:
    """Singleton translator örneği al"""
    global _translator_instance
    if _translator_instance is None:
        _translator_instance = GeminiTranslator()
    return _translator_instance


def translate_text(text: str, target_lang: str = "tr", source_lang: str = "auto") -> str:
    """
    Kolay çeviri fonksiyonu

    Args:
        text: Çevrilecek metin
        target_lang: Hedef dil
        source_lang: Kaynak dil

    Returns:
        str: Çevrili metin
    """
    translator = get_translator()
    result = translator.translate(text, target_lang, source_lang)
    return result.text if result.success else text
