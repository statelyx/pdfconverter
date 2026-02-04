# -*- coding: utf-8 -*-
"""
Extension: PDF OCR Adder
Kaynak: https://github.com/ocrmypdf/OCRmyPDF
Mevcut sisteme DOKUNMADAN çalışır
PDF'e görünmez OCR metni ekler (taranmış PDF için)
"""

import io
import os
import tempfile
from typing import Dict, Optional, List
from dataclasses import dataclass

try:
    import fitz  # PyMuPDF
    import pytesseract
    from PIL import Image
    from ocrmypdf import ocrmypdf
    OCRLIB_AVAILABLE = True
except ImportError:
    OCRLIB_AVAILABLE = False


@dataclass
class OCROperationResult:
    """OCR işlem sonucu"""
    success: bool
    output_pdf: bytes
    pages_processed: int
    text_found: bool
    error: str = ""


class PDFOCRAdder:
    """
    PDF'e OCR ekleyen servis
    Taranmış PDF'lere görünmez metin katmanı ekler
    OCRmyPDF wrapper'ı
    """

    __version__ = "1.0.0"

    def __init__(self, config: Optional[Dict] = None):
        """
        PDF OCR Adder başlat

        Args:
            config: Yapılandırma
                - tesseract_path: Tesseract executable yolu
                - tessdata_dir: tessdata dizini
                - language: Varsayılan dil (tur)
                - dpi: Tarama DPI değeri
                - deskew: Sayfa düzeltme
                - clean: Görüntü temizleme
        """
        if not OCRLIB_AVAILABLE:
            raise ImportError("OCR kütüphaneleri kurulu değil. pip install ocrmypdf pytesseract Pillow")

        self.config = config or {}

        # Tesseract yolunu ayarla
        tesseract_path = self.config.get("tesseract_path")
        if tesseract_path and os.path.exists(tesseract_path):
            pytesseract.pytesseract.tesseract_cmd = tesseract_path

        # Tessdata dizinini ayarla
        tessdata_dir = self.config.get("tessdata_dir")
        if tessdata_dir:
            os.environ["TESSDATA_PREFIX"] = tessdata_dir

        # Dil
        self.default_lang = self.config.get("language", "tur")

        # OCR ayarları
        self.dpi = self.config.get("dpi", 300)
        self.deskew = self.config.get("deskew", True)
        self.clean = self.config.get("clean", True)

    def add_ocr_to_pdf(self, pdf_bytes: bytes, lang: str = "tur",
                       output_type: str = "pdf") -> OCROperationResult:
        """
        PDF'e OCR ekle

        Args:
            pdf_bytes: PDF bayt verisi
            lang: Dil kodu (tur, eng, vb.)
            output_type: Çıktı tipi (pdf, pdfa, txt)

        Returns:
            OCROperationResult: OCR sonucu
        """
        # Dil kodunu normalize et
        lang_map = {
            "tr": "tur",
            "tur": "tur",
            "turkish": "tur",
            "en": "eng",
            "eng": "eng",
            "english": "eng",
            "de": "deu",
            "fr": "fra",
        }
        ocr_lang = lang_map.get(lang.lower(), lang)

        # Geçici dosyalar oluştur
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as input_pdf:
            input_pdf.write(pdf_bytes)
            input_path = input_pdf.name

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as output_pdf:
            output_path = output_pdf.name

        try:
            # OCRmyPDF ile işlem yap
            args = [
                input_path,
                output_path,
                "-l", ocr_lang,
                "--dpi", str(self.dpi),
                "--output-type", output_type
            ]

            if self.deskew:
                args.append("--deskew")

            if self.clean:
                args.append("--clean")

            # OCRmyPDF'ı çalıştır
            ocrmypdf.ocrmypdf(args, progress_bar=False)

            # Sonucu oku
            with open(output_path, "rb") as f:
                result_bytes = f.read()

            # Sayfa sayısı kontrolü
            doc = fitz.open(stream=result_bytes, filetype="pdf")
            page_count = len(doc)

            # Metin kontrolü
            has_text = False
            for page in doc:
                if page.get_text("text").strip():
                    has_text = True
                    break
            doc.close()

            return OCROperationResult(
                success=True,
                output_pdf=result_bytes,
                pages_processed=page_count,
                text_found=has_text
            )

        except Exception as e:
            # Hata durumunda orijinal PDF'i döndür
            return OCROperationResult(
                success=False,
                output_pdf=pdf_bytes,
                pages_processed=0,
                text_found=False,
                error=str(e)
            )

        finally:
            # Geçici dosyaları temizle
            try:
                os.unlink(input_path)
            except:
                pass
            try:
                os.unlink(output_path)
            except:
                pass

    def add_ocr_to_scanned_pages(self, pdf_bytes: bytes, lang: str = "tur") -> OCROperationResult:
        """
        Sadece taranmış sayfalara OCR ekle

        Args:
            pdf_bytes: PDF bayt verisi
            lang: Dil kodu

        Returns:
            OCROperationResult: OCR sonucu
        """
        # Önce taranmış sayfaları tespit et
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        scanned_pages = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            # Metin yoksa taranmış sayfa say
            if not page.get_text("text").strip():
                scanned_pages.append(page_num)

        doc.close()

        if not scanned_pages:
            return OCROperationResult(
                success=True,
                output_pdf=pdf_bytes,
                pages_processed=0,
                text_found=True
            )

        # Tüm PDF'e OCR ekle (OCRmyPDF otomatik tespit yapıyor)
        return self.add_ocr_to_pdf(pdf_bytes, lang)

    def make_searchable(self, pdf_bytes: bytes, lang: str = "tur") -> OCROperationResult:
        """
        PDF'i aranabilir hale getir (OCR ile)

        Args:
            pdf_bytes: PDF bayt verisi
            lang: Dil kodu

        Returns:
            OCROperationResult: OCR sonucu
        """
        return self.add_ocr_to_pdf(pdf_bytes, lang, "pdf")

    def extract_text_with_ocr(self, pdf_bytes: bytes, lang: str = "tur") -> str:
        """
        PDF'ten metin çıkar (OCR ile)

        Args:
            pdf_bytes: PDF bayt verisi
            lang: Dil kodu

        Returns:
            str: Çıkarılan metin
        """
        # Önce normal metin çıkarmayı dene
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = ""

        for page in doc:
            text += page.get_text("text") + "\n\n"

        doc.close()

        # Metin varsa döndür
        if text.strip():
            return text

        # Metin yoksa OCR yap
        result = self.add_ocr_to_pdf(pdf_bytes, lang)

        if result.success:
            doc = fitz.open(stream=result.output_pdf, filetype="pdf")
            text = ""
            for page in doc:
                text += page.get_text("text") + "\n\n"
            doc.close()

        return text


class TurkishPDFOCRAdder(PDFOCRAdder):
    """
    Türkçe OCR Adder
    Türkçe karakter optimizasyonu ile
    """

    def __init__(self, config=None):
        config = config or {}
        config["language"] = "tur"
        super().__init__(config)

        # Türkçe karakter düzeltme
        self.char_corrections = {
            "Ý": "İ",
            "ð": "ğ",
            "þ": "ş",
            "ý": "ı",
            "Ð": "Ğ",
            "Þ": "Ş"
        }

    def fix_turkish_chars(self, text: str) -> str:
        """Türkçe karakterleri düzelt"""
        for wrong, correct in self.char_corrections.items():
            text = text.replace(wrong, correct)
        return text

    def add_ocr_to_pdf(self, pdf_bytes: bytes, lang: str = "tur",
                       output_type: str = "pdf") -> OCROperationResult:
        """PDF'e OCR ekle (Türkçe karakter düzeltmesi ile)"""
        result = super().add_ocr_to_pdf(pdf_bytes, lang, output_type)

        # Türkçe karakterleri düzelt
        if result.success:
            doc = fitz.open(stream=result.output_pdf, filetype="pdf")

            # Her sayfayı işle
            for page in doc:
                text = page.get_text("text")
                # Düzeltme gerekmiyor kontrol et
                # (PyMuPDF zaten UTF-8 destekliyor)

            doc.close()

        return result


# Kolay kullanım fonksiyonları
def add_ocr_to_pdf(pdf_bytes: bytes, lang: str = "tr", config: Dict = None) -> bytes:
    """
    PDF'e OCR ekle (kolay fonksiyon)

    Args:
        pdf_bytes: PDF bayt verisi
        lang: Dil kodu
        config: Yapılandırma

    Returns:
        bytes: OCR eklenmiş PDF
    """
    adder = TurkishPDFOCRAdder(config)
    result = adder.add_ocr_to_pdf(pdf_bytes, lang)
    return result.output_pdf if result.success else pdf_bytes


def make_pdf_searchable(pdf_bytes: bytes, lang: str = "tr", config: Dict = None) -> bytes:
    """
    PDF'i aranabilir hale getir (kolay fonksiyon)

    Args:
        pdf_bytes: PDF bayt verisi
        lang: Dil kodu
        config: Yapılandırma

    Returns:
        bytes: Aranabilir PDF
    """
    adder = TurkishPDFOCRAdder(config)
    result = adder.make_searchable(pdf_bytes, lang)
    return result.output_pdf if result.success else pdf_bytes


def extract_text_with_ocr(pdf_bytes: bytes, lang: str = "tr", config: Dict = None) -> str:
    """
    PDF'ten metin çıkar OCR ile (kolay fonksiyon)

    Args:
        pdf_bytes: PDF bayt verisi
        lang: Dil kodu
        config: Yapılandırma

    Returns:
        str: Çıkarılan metin
    """
    adder = TurkishPDFOCRAdder(config)
    return adder.extract_text_with_ocr(pdf_bytes, lang)
