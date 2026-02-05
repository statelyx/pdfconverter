# -*- coding: utf-8 -*-
"""
PDF to PDF Converter - Hibrit Çeviri Sistemi
Orijinal görseli koruyup metni Türkçe font ile çevirir
"""

import io
import os
import tempfile
from typing import Optional, Callable

import fitz  # PyMuPDF
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas
from PIL import Image

from core.pdf_reader import PDFReader, TextBlock
from core.pdf_writer import HybridPDFWriter
from core.font_manager import FontManager
from translators.multi_translator import get_translator, TranslationResult
from config import PDF_DPI


class PDFToPDFConverter:
    """
    PDF'ten PDF'e çeviri
    Orijinal görseli koruyup metni çevirir
    Türkçe font ile profesyonel çıktı
    """

    def __init__(self):
        self.translator = get_translator()

    def convert(self, pdf_bytes: bytes, source_lang: str = "auto",
               target_lang: str = "tr", progress_callback: Callable = None) -> bytes:
        """
        PDF'i çevrilmiş PDF'e dönüştür

        Args:
            pdf_bytes: PDF bayt verisi
            source_lang: Kaynak dil kodu
            target_lang: Hedef dil kodu
            progress_callback: İlerleme callback'i (sayfa_num, toplam_sayfa)

        Returns:
            bytes: Çevrilmiş PDF bayt verisi
        """
        # PDF'i oku
        with PDFReader(pdf_bytes=pdf_bytes) as reader:
            total_pages = len(reader)
            print(f"📄 PDF okunuyor: {total_pages} sayfa")

            # Çeviri sözlüğü
            translated_texts = {}

            # Her sayfa için
            for page_num in range(total_pages):
                if progress_callback:
                    progress_callback(page_num + 1, total_pages)

                # Sayfa layout'unu al
                layout = reader.analyze_page_layout(page_num)
                translated_texts[page_num] = {}

                # Her metin bloğunu çevir
                for block_idx, block in enumerate(layout.text_blocks):
                    if not block.text.strip():
                        continue

                    try:
                        result = self.translator.translate(
                            block.text,
                            target_lang=target_lang,
                            source_lang=source_lang
                        )

                        if result.success:
                            translated_texts[page_num][block_idx] = result.text
                        else:
                            translated_texts[page_num][block_idx] = block.text

                        print(f"✅ Sayfa {page_num + 1}/{total_pages} - Blok {block_idx + 1}: Çevrildi")

                    except Exception as e:
                        print(f"⚠️ Çeviri hatası: {e}")
                        translated_texts[page_num][block_idx] = block.text

            # Yeni PDF oluştur
            print("📝 Yeni PDF oluşturuluyor...")
            hybrid_writer = HybridPDFWriter()

            for page_num in range(total_pages):
                # Arka plan görseli
                pixmap = reader.get_page_pixmap(page_num, dpi=PDF_DPI)

                # Çevrili metin blokları ile sayfa verisi hazırla
                layout = reader.analyze_page_layout(page_num)

                text_blocks = []
                for block_idx, block in enumerate(layout.text_blocks):
                    # Çevrilmiş metin
                    translated = translated_texts.get(page_num, {}).get(block_idx, block.text)

                    # Font stili belirle
                    style = "regular"
                    if block.is_bold and block.is_italic:
                        style = "bold_italic"
                    elif block.is_bold:
                        style = "bold"
                    elif block.is_italic:
                        style = "italic"

                    font_name = FontManager.get_font_name(style=style)

                    text_blocks.append({
                        "text": translated,
                        "bbox": block.bbox,
                        "font_size": max(8, min(24, block.font_size)),
                        "font_name": font_name,
                        "alignment": block.alignment
                    })

                # Sayfa ekle
                page_data = {
                    "background": pixmap.tobytes("png"),
                    "width": pixmap.width,
                    "height": pixmap.height,
                    "text_blocks": text_blocks
                }
                hybrid_writer.writer.pages_data.append(page_data)

            # PDF oluştur
            result = hybrid_writer.writer.generate()
            print("✅ PDF oluşturuldu!")

            return result

    def convert_with_watermark(self, pdf_bytes: bytes, source_lang: str = "auto",
                              target_lang: str = "tr", watermark: str = None) -> bytes:
        """
        PDF'i çevir ve filigran ekle

        Args:
            pdf_bytes: PDF bayt verisi
            source_lang: Kaynak dil
            target_lang: Hedef dil
            watermark: Filigran metni

        Returns:
            bytes: Çevrilmiş PDF
        """
        result = self.convert(pdf_bytes, source_lang, target_lang)

        if watermark:
            # Filigran ekle
            result = self._add_watermark(result, watermark)

        return result

    def _add_watermark(self, pdf_bytes: bytes, watermark: str) -> bytes:
        """PDF'e filigran ekle"""
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        for page in doc:
            # Filigran ortala
            rect = page.rect
            x = rect.width / 2
            y = rect.height / 2

            # Dönüş -45 derece
            point = fitz.Point(x, y)

            page.insert_text(
                point,
                watermark,
                fontsize=24,
                fontname="helv",
                color=(0.7, 0.7, 0.7),
                rotate=45
            )

        return doc.tobytes()


class SimplePDFTranslator:
    """
    Basit PDF çevirici
    Sadece metni çevirir, görsel arka plan eklemez
    """

    def __init__(self):
        self.translator = get_translator()

    def translate(self, pdf_bytes: bytes, source_lang: str = "auto",
                 target_lang: str = "tr") -> bytes:
        """
        PDF metnini çevir

        Args:
            pdf_bytes: PDF bayt verisi
            source_lang: Kaynak dil
            target_lang: Hedef dil

        Returns:
            bytes: Çevrilmiş PDF
        """
        # PDF'i oku
        with PDFReader(pdf_bytes=pdf_bytes) as reader:
            output_doc = fitz.open()

            for page_num in range(len(reader)):
                src_page = reader.get_page(page_num)

                # Yeni sayfa oluştur
                new_page = output_doc.new_page(
                    width=src_page.rect.width,
                    height=src_page.rect.height
                )

                # Metin bloklarını çevir
                blocks = reader.extract_text_blocks(page_num)

                for block in blocks:
                    # Çeviri yap
                    result = self.translator.translate(
                        block.text,
                        target_lang=target_lang,
                        source_lang=source_lang
                    )

                    translated = result.text if result.success else block.text

                    # Beyaz arka plan
                    new_page.draw_rect(
                        fitz.Rect(block.bbox),
                        color=(1, 1, 1),
                        fill=(1, 1, 1)
                    )

                    # Font stilini belirle
                    font_flags = 0
                    if block.is_bold:
                        font_flags |= 1
                    if block.is_italic:
                        font_flags |= 2

                    # Metni ekle
                    # Türkçe karakterleri korumak için rect yerine textpoint kullan
                    try:
                        new_page.insert_text(
                            fitz.Point(block.bbox[0], block.bbox[3] - block.font_size),
                            translated,
                            fontsize=block.font_size,
                            fontname="helv",
                            color=(0, 0, 0)
                        )
                    except Exception as e:
                        # Hata olursa basit metin ekle
                        new_page.insert_textbox(
                            fitz.Rect(block.bbox),
                            translated,
                            fontsize=block.font_size,
                            fontname="helv",
                            align=fitz.TEXT_ALIGN_LEFT
                        )

            return output_doc.tobytes()


# Converter factory
def create_converter(converter_type: str = "span"):
    """
    Converter oluştur

    Args:
        converter_type: 
            - "span" (VARSAYILAN): Span-based translator - BOMBA layout koruması
            - "layout": Layout-koruyucu çevirici
            - "hybrid": Hibrit çevirici - Görsel arka plan + metin katmanı
            - "simple": Basit çevirici - Sadece metin

    Returns:
        Converter instance
    """
    if converter_type == "span":
        # SPAN-BASED - En iyi layout koruması
        from converters.span_translator import SpanBasedTranslator
        return SpanBasedTranslator()
    elif converter_type == "layout":
        from converters.layout_translator import LayoutPreservingTranslator
        return LayoutPreservingTranslator()
    elif converter_type == "simple":
        return SimplePDFTranslator()
    elif converter_type == "hybrid":
        return PDFToPDFConverter()
    else:
        # Varsayılan: Span-based
        from converters.span_translator import SpanBasedTranslator
        return SpanBasedTranslator()


# Test için
if __name__ == "__main__":
    # Test kodu
    pass


