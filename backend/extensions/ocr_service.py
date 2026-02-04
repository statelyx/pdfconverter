# -*- coding: utf-8 -*-
"""
Extension: OCR Service
Kaynak: https://github.com/tesseract-ocr/tesseract
Mevcut sisteme DOKUNMADAN çalışır
Türkçe karakter desteği ile
"""

import io
import os
import tempfile
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

try:
    import pytesseract
    from PIL import Image
    import fitz  # PyMuPDF
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


@dataclass
class OCRResult:
    """OCR sonucu"""
    text: str
    confidence: float
    language: str
    pages: int
    blocks: List[Dict]


class OCRService:
    """
    Tesseract OCR servis wrapper'ı
    Türkçe dil desteği ile
    """

    __version__ = "1.0.0"

    # Dil kodları
    LANGUAGES = {
        "tr": "tur",
        "tur": "tur",
        "turkish": "tur",
        "en": "eng",
        "eng": "eng",
        "english": "eng",
        "de": "deu",
        "fr": "fra",
        "es": "spa",
        "ru": "rus",
        "ar": "ara",
        "zh": "chi_sim",
        "ja": "jpn",
    }

    def __init__(self, config: Optional[Dict] = None):
        """
        OCR servisi başlat

        Args:
            config: Yapılandırma
                - tesseract_path: Tesseract executable yolu
                - tessdata_dir: tessdata dizini
                - language: Varsayılan dil (tr)
        """
        if not OCR_AVAILABLE:
            raise ImportError("OCR kütüphaneleri kurulu değil. pip install pytesseract Pillow")

        self.config = config or {}

        # Tesseract yolunu ayarla
        tesseract_path = self.config.get("tesseract_path")
        if tesseract_path and os.path.exists(tesseract_path):
            pytesseract.pytesseract.tesseract_cmd = tesseract_path

        # Tessdata dizinini ayarla
        tessdata_dir = self.config.get("tessdata_dir")
        if tessdata_dir:
            os.environ["TESSDATA_PREFIX"] = tessdata_dir

        # Varsayılan dil
        self.default_lang = self.config.get("language", "tr")

        # Kullanılabilirlik kontrolü
        self.available = self.check_available()

    def check_available(self) -> bool:
        """Tesseract kurulu mu kontrol et"""
        try:
            version = pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def ocr_pdf(self, pdf_bytes: bytes, lang: str = "tr",
               dpi: int = 300) -> OCRResult:
        """
        PDF üzerinde OCR yap

        Args:
            pdf_bytes: PDF bayt verisi
            lang: Dil kodu (tr, en, de, vb.)
            dpi: DPI değeri

        Returns:
            OCRResult: OCR sonucu
        """
        # Dil kodunu çevir
        tesseract_lang = self.LANGUAGES.get(lang.lower(), lang)

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        all_text = []
        total_confidence = 0
        block_count = 0

        for page_num in range(len(doc)):
            page = doc[page_num]

            # Sayfayı yüksek DPI'da pixmap olarak al
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat)

            # PIL Image'a çevir
            img = Image.open(io.BytesIO(pix.tobytes("png")))

            # OCR yap
            text = pytesseract.image_to_string(
                img,
                lang=tesseract_lang,
                config='--psm 6'  # Tek sütunlu varsayılan
            )

            # Detaylı OCR (confidence ile)
            data = pytesseract.image_to_data(
                img,
                lang=tesseract_lang,
                output_type=pytesseract.Output.DICT
            )

            # Ortalama confidence hesapla
            confidences = [int(conf) for conf in data["conf"] if str(conf).isdigit()]
            avg_conf = sum(confidences) / len(confidences) if confidences else 0

            all_text.append(text)
            total_confidence += avg_conf
            block_count += 1

        doc.close()

        return OCRResult(
            text="\n\n".join(all_text),
            confidence=total_confidence / block_count if block_count > 0 else 0,
            language=tesseract_lang,
            pages=len(doc),
            blocks=[]
        )

    def ocr_image(self, image_bytes: bytes, lang: str = "tr") -> OCRResult:
        """
        Görsel üzerinde OCR yap

        Args:
            image_bytes: Görsel bayt verisi
            lang: Dil kodu

        Returns:
            OCRResult: OCR sonucu
        """
        tesseract_lang = self.LANGUAGES.get(lang.lower(), lang)

        img = Image.open(io.BytesIO(image_bytes))

        # OCR yap
        text = pytesseract.image_to_string(
            img,
            lang=tesseract_lang,
            config='--psm 6'
        )

        # Detaylı data
        data = pytesseract.image_to_data(
            img,
            lang=tesseract_lang,
            output_type=pytesseract.Output.DICT
        )

        # Confidence hesapla
        confidences = [int(conf) for conf in data["conf"] if str(conf).isdigit()]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0

        return OCRResult(
            text=text,
            confidence=avg_conf,
            language=tesseract_lang,
            pages=1,
            blocks=[]
        )

    def ocr_with_boxes(self, pdf_bytes: bytes, lang: str = "tr",
                      dpi: int = 300) -> List[Dict]:
        """
        PDF üzerinde OCR yap (metin kutuları ile)

        Args:
            pdf_bytes: PDF bayt verisi
            lang: Dil kodu
            dpi: DPI değeri

        Returns:
            List[Dict]: Metin kutuları (bbox, text, confidence)
        """
        tesseract_lang = self.LANGUAGES.get(lang.lower(), lang)

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        all_boxes = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat)
            img = Image.open(io.BytesIO(pix.tobytes("png")))

            # Detaylı OCR
            data = pytesseract.image_to_data(
                img,
                lang=tesseract_lang,
                output_type=pytesseract.Output.DICT
            )

            # Metin kutularını çıkar
            n_boxes = len(data["text"])
            for i in range(n_boxes):
                text = data["text"][i].strip()
                conf = int(data["conf"][i]) if str(data["conf"][i]).isdigit() else 0

                if text and conf > 30:  # Min confidence
                    all_boxes.append({
                        "page": page_num,
                        "text": text,
                        "confidence": conf,
                        "bbox": (
                            data["left"][i],
                            data["top"][i],
                            data["left"][i] + data["width"][i],
                            data["top"][i] + data["height"][i]
                        )
                    })

        doc.close()
        return all_boxes


class TurkishOCRService(OCRService):
    """
    Türkçe OCR servisi
    Türkçe karakter optimizasyonu ile
    """

    def __init__(self, config=None):
        super().__init__(config)
        self.turkish_chars = {
            "Ý": "İ",
            "ð": "ğ",
            "þ": "ş",
            "ý": "ı",
            "Ð": "Ğ",
            "Þ": "Ş"
        }

    def fix_turkish_chars(self, text: str) -> str:
        """Türkçe karakterleri düzelt"""
        for wrong, correct in self.turkish_chars.items():
            text = text.replace(wrong, correct)
        return text

    def ocr_pdf(self, pdf_bytes: bytes, lang: str = "tr",
               dpi: int = 300) -> OCRResult:
        """PDF üzerinde OCR yap (Türkçe karakter düzeltmesi ile)"""
        result = super().ocr_pdf(pdf_bytes, lang, dpi)
        result.text = self.fix_turkish_chars(result.text)
        return result

    def ocr_image(self, image_bytes: bytes, lang: str = "tr") -> OCRResult:
        """Görsel üzerinde OCR yap (Türkçe karakter düzeltmesi ile)"""
        result = super().ocr_image(image_bytes, lang)
        result.text = self.fix_turkish_chars(result.text)
        return result


# Kolay kullanım fonksiyonları
def ocr_pdf(pdf_bytes: bytes, lang: str = "tr", config: Dict = None) -> str:
    """
    PDF üzerinde OCR yap (kolay fonksiyon)

    Args:
        pdf_bytes: PDF bayt verisi
        lang: Dil kodu
        config: Yapılandırma

    Returns:
        str: OCR sonucu metin
    """
    service = TurkishOCRService(config)
    result = service.ocr_pdf(pdf_bytes, lang)
    return result.text


def ocr_image(image_bytes: bytes, lang: str = "tr", config: Dict = None) -> str:
    """
    Görsel üzerinde OCR yap (kolay fonksiyon)

    Args:
        image_bytes: Görsel bayt verisi
        lang: Dil kodu
        config: Yapılandırma

    Returns:
        str: OCR sonucu metin
    """
    service = TurkishOCRService(config)
    result = service.ocr_image(image_bytes, lang)
    return result.text
