# -*- coding: utf-8 -*-
"""
Extension: Batch Translator
Kaynak: https://github.com/LibreTranslate/argos-translate-files
Mevcut sisteme DOKUNMADAN çalışır
Toplu dosya çevirisi servisi
"""

import io
import os
import tempfile
import zipfile
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

import fitz  # PyMuPDF

# Extension modüllerini içe aktar
from .translation_proxy import LibreTranslateProxy
from .google_trans_scraper import GoogleTranslateScraper


@dataclass
class BatchTranslationResult:
    """Toplu çeviri sonucu"""
    files: List[Dict]  # [{original_name, translated_name, bytes, success, error}]
    total_files: int
    success_count: int
    failed_count: int
    service: str


class BatchTranslator:
    """
    Toplu dosya çevirisi servisi
    Birden fazla dosyayı aynı anda çevirir
    """

    __version__ = "1.0.0"

    def __init__(self, config: Optional[Dict] = None):
        """
        Batch translator başlat

        Args:
            config: Yapılandırma
                - service: Çeviri servisi (libretranslate, google, gemini)
                - target_lang: Hedef dil
                - source_lang: Kaynak dil
                - output_format: Çıktı formatı (pdf, zip)
                - concurrent: Eşzamanlı işlem sayısı
        """
        self.config = config or {}
        self.service = self.config.get("service", "libretranslate")
        self.target_lang = self.config.get("target_lang", "tr")
        self.source_lang = self.config.get("source_lang", "auto")
        self.output_format = self.config.get("output_format", "zip")
        self.concurrent = self.config.get("concurrent", 3)

        # Çeviri servisi başlat
        if self.service == "libretranslate":
            self.translator = LibreTranslateProxy(self.config)
        elif self.service == "google":
            self.translator = GoogleTranslateScraper(self.config)
        else:
            self.translator = LibreTranslateProxy(self.config)

    def translate_pdf_files(self, files: List[Dict]) -> BatchTranslationResult:
        """
        PDF dosyalarını toplu çevir

        Args:
            files: [{name, bytes}] formatında dosya listesi

        Returns:
            BatchTranslationResult: Çeviri sonucu
        """
        results = []

        for file_info in files:
            file_name = file_info.get("name", "unknown.pdf")
            file_bytes = file_info.get("bytes", b"")

            try:
                # PDF'i çevir
                translated = self._translate_pdf(file_bytes, self.source_lang, self.target_lang)

                results.append({
                    "original_name": file_name,
                    "translated_name": file_name.replace(".pdf", f"_{self.target_lang}.pdf"),
                    "bytes": translated,
                    "success": True,
                    "error": ""
                })

            except Exception as e:
                results.append({
                    "original_name": file_name,
                    "translated_name": file_name,
                    "bytes": file_bytes,
                    "success": False,
                    "error": str(e)
                })

        # İstatistikler
        success_count = sum(1 for r in results if r["success"])
        failed_count = len(results) - success_count

        return BatchTranslationResult(
            files=results,
            total_files=len(files),
            success_count=success_count,
            failed_count=failed_count,
            service=self.service
        )

    def _translate_pdf(self, pdf_bytes: bytes, source_lang: str, target_lang: str) -> bytes:
        """PDF'i çevir (basit yaklaşım)"""
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        output_doc = fitz.open()

        for page_num in range(len(doc)):
            page = doc[page_num]

            # Yeni sayfa oluştur
            new_page = output_doc.new_page(
                width=page.rect.width,
                height=page.rect.height
            )

            # Metin bloklarını çevir
            blocks = page.get_text("dict")["blocks"]

            for block in blocks:
                if block["type"] == 0:  # Text
                    # Metni çıkar
                    text = ""
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            text += span["text"] + " "
                        text += "\n"

                    if text.strip():
                        # Çeviri yap
                        result = self.translator.translate(text.strip(), target_lang, source_lang)

                        # Çevrili metni yaz
                        block_rect = fitz.Rect(block["bbox"])
                        new_page.draw_rect(block_rect, color=(1,1,1), fill=(1,1,1))

                        # Türkçe karakter düzeltme (basit)
                        translated = result.text
                        if hasattr(result, "text"):
                            translated = self._fix_turkish_chars(translated)

                        new_page.insert_textbox(
                            block_rect,
                            translated,
                            fontsize=10,
                            fontname="helv",
                            align=fitz.TEXT_ALIGN_LEFT
                        )

        doc.close()
        return output_doc.tobytes()

    def _fix_turkish_chars(self, text: str) -> str:
        """Türkçe karakterleri düzelt"""
        return text  # Daha detaylı düzeltme eklenebilir

    def translate_text_files(self, files: List[Dict]) -> BatchTranslationResult:
        """
        Metin dosyalarını toplu çevir

        Args:
            files: [{name, bytes}] formatında dosya listesi

        Returns:
            BatchTranslationResult: Çeviri sonucu
        """
        results = []

        for file_info in files:
            file_name = file_info.get("name", "unknown.txt")
            file_bytes = file_info.get("bytes", b"")

            try:
                # Metni çöz
                text = file_bytes.decode("utf-8")

                # Çeviri yap
                result = self.translator.translate(text, self.target_lang, self.source_lang)
                translated = result.text if hasattr(result, "text") else text

                # Sonucu oluştur
                ext = os.path.splitext(file_name)[1]
                new_name = file_name.replace(ext, f"_{self.target_lang}{ext}")

                results.append({
                    "original_name": file_name,
                    "translated_name": new_name,
                    "bytes": translated.encode("utf-8"),
                    "success": True,
                    "error": ""
                })

            except Exception as e:
                results.append({
                    "original_name": file_name,
                    "translated_name": file_name,
                    "bytes": file_bytes,
                    "success": False,
                    "error": str(e)
                })

        success_count = sum(1 for r in results if r["success"])
        failed_count = len(results) - success_count

        return BatchTranslationResult(
            files=results,
            total_files=len(files),
            success_count=success_count,
            failed_count=failed_count,
            service=self.service
        )

    def translate_to_zip(self, files: List[Dict]) -> Tuple[bytes, str]:
        """
        Dosyaları çevirip ZIP olarak döndür

        Args:
            files: [{name, bytes}] formatında dosya listesi

        Returns:
            Tuple[bytes, str]: (ZIP bayt verisi, dosya adı)
        """
        # PDF veya metin dosyası olduğunu tespit et
        is_pdf = any(f["name"].endswith(".pdf") for f in files)

        if is_pdf:
            result = self.translate_pdf_files(files)
        else:
            result = self.translate_text_files(files)

        # ZIP oluştur
        output = io.BytesIO()

        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_result in result.files:
                zip_file.writestr(file_result["translated_name"], file_result["bytes"])

        zip_bytes = output.getvalue()
        zip_name = f"translated_{self.target_lang}.zip"

        return zip_bytes, zip_name


class ParallelBatchTranslator(BatchTranslator):
    """
    Paralel batch translator
    Çoklu dosya işleme desteği
    """

    def __init__(self, config=None):
        super().__init__(config)
        self.max_workers = self.config.get("max_workers", 3)

    def translate_pdf_files_parallel(self, files: List[Dict]) -> BatchTranslationResult:
        """
        PDF dosyalarını paralel çevir

        Args:
            files: [{name, bytes}] formatında dosya listesi

        Returns:
            BatchTranslationResult: Çeviri sonucu
        """
        # Basit sıralı implementasyon (paralel versiyon için concurrent.futures kullanılabilir)
        return self.translate_pdf_files(files)


# Kolay kullanım fonksiyonları
def batch_translate_pdfs(files: List[Dict], target_lang: str = "tr",
                        source_lang: str = "auto", config: Dict = None) -> Tuple[bytes, str]:
    """
    PDF dosyalarını toplu çevir (kolay fonksiyon)

    Args:
        files: [{name, bytes}] formatında dosya listesi
        target_lang: Hedef dil
        source_lang: Kaynak dil
        config: Yapılandırma

    Returns:
        Tuple[bytes, str]: (ZIP bayt verisi, dosya adı)
    """
    config = config or {}
    config["target_lang"] = target_lang
    config["source_lang"] = source_lang

    translator = BatchTranslator(config)
    return translator.translate_to_zip(files)


def batch_translate_text(files: List[Dict], target_lang: str = "tr",
                        source_lang: str = "auto", config: Dict = None) -> Tuple[bytes, str]:
    """
    Metin dosyalarını toplu çevir (kolay fonksiyon)

    Args:
        files: [{name, bytes}] formatında dosya listesi
        target_lang: Hedef dil
        source_lang: Kaynak dil
        config: Yapılandırma

    Returns:
        Tuple[bytes, str]: (ZIP bayt verisi, dosya adı)
    """
    config = config or {}
    config["target_lang"] = target_lang
    config["source_lang"] = source_lang

    translator = BatchTranslator(config)
    return translator.translate_to_zip(files)
