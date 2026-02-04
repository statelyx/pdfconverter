# -*- coding: utf-8 -*-
"""
PDF Writer - ReportLab ile Türkçe Fontlu PDF Oluşturma
Görsel bütünlüğü koruyarak PDF oluşturma
"""

import io
from typing import List, Tuple, Optional
from reportlab.lib.pagesizes import letter, A4, legal
from reportlab.lib.units import inch
from reportlab.lib.colors import Color, white
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from PIL import Image
import fitz  # PyMuPDF

from core.font_manager import FontManager, TextStyles
from core.pdf_reader import TextBlock, ImageBlock, PageLayout
from config import PDF_DPI, PDF_COMPRESSION


class PDFWriter:
    """
    ReportLab ile Türkçe fontlu PDF oluşturma
    Görseli arka plan olarak kullanıp metni katman olarak ekler
    """

    # Sayfa boyutları
    PAGE_SIZES = {
        "letter": letter,
        "a4": A4,
        "legal": legal
    }

    def __init__(self, page_size: str = "a4"):
        """
        PDF Writer başlat

        Args:
            page_size: Sayfa boyutu (letter, a4, legal)
        """
        self.page_size = self.PAGE_SIZES.get(page_size.lower(), A4)
        self.pages_data = []

    def add_page_from_pixmap(self, pixmap: fitz.Pixmap):
        """
        PyMuPDF pixmap'tan sayfa ekle

        Args:
            pixmap: PyMuPDF pixmap nesnesi
        """
        # Pixmap'ı PNG formatına çevir
        img_bytes = pixmap.tobytes("png")

        self.pages_data.append({
            "background": img_bytes,
            "width": pixmap.width,
            "height": pixmap.height,
            "text_blocks": [],
            "images": []
        })

    def add_page_with_text(self, pixmap: fitz.Pixmap, text_blocks: List[TextBlock],
                          images: List[ImageBlock] = None):
        """
        Görsel arka plan ve metin blokları ile sayfa ekle

        Args:
            pixmap: Arka plan görseli
            text_blocks: Metin blokları
            images: Görsel blokları (opsiyonel)
        """
        img_bytes = pixmap.tobytes("png")

        self.pages_data.append({
            "background": img_bytes,
            "width": pixmap.width,
            "height": pixmap.height,
            "text_blocks": text_blocks or [],
            "images": images or []
        })

    def add_text_block(self, text: str, bbox: Tuple[float, float, float, float],
                      font_size: float = 10, font_name: str = None,
                      alignment: str = "left", page_index: int = -1):
        """
        Metin bloğu ekle

        Args:
            text: Metin içeriği
            bbox: (x0, y0, x1, y1) koordinatları
            font_size: Font boyutu
            font_name: Font adı
            alignment: Hizalama (left, center, right)
            page_index: Sayfa indeksi (-1 = son sayfa)
        """
        if page_index == -1:
            page_index = len(self.pages_data) - 1

        if 0 <= page_index < len(self.pages_data):
            self.pages_data[page_index]["text_blocks"].append({
                "text": text,
                "bbox": bbox,
                "font_size": font_size,
                "font_name": font_name or FontManager.get_font_name(),
                "alignment": alignment
            })

    def generate(self, output_path: str = None) -> bytes:
        """
        PDF'i oluştur

        Args:
            output_path: Çıktı dosya yolu (None = bayt döndür)

        Returns:
            bytes: PDF bayt verisi
        """
        output_buffer = io.BytesIO()

        # Her sayfa için boyut hesapla
        if self.pages_data:
            # İlk sayfanın boyutunu kullan
            first_page = self.pages_data[0]
            page_width = first_page["width"]
            page_height = first_page["height"]

            # Point'e çevir (1 point = 1/72 inch, DPI'dan hesapla)
            width_pt = (page_width / PDF_DPI) * 72
            height_pt = (page_height / PDF_DPI) * 72

            page_size = (width_pt, height_pt)
        else:
            page_size = A4

        # Canvas oluştur
        c = canvas.Canvas(output_buffer, pagesize=page_size)

        # Her sayfa için
        for page_data in self.pages_data:
            # Arka plan görselini ekle
            if "background" in page_data:
                self._draw_background_image(c, page_data, page_size)

            # Metin bloklarını ekle
            for block in page_data.get("text_blocks", []):
                self._draw_text_block(c, block, page_size)

            # Yeni sayfa
            c.showPage()

        # PDF'i kaydet
        c.save()

        return output_buffer.getvalue()

    def _draw_background_image(self, c: canvas.Canvas, page_data: dict, page_size: Tuple[float, float]):
        """Arka plan görselini çiz"""
        try:
            img_bytes = page_data["background"]
            img = Image.open(io.BytesIO(img_bytes))

            # Resim boyutları
            img_width, img_height = img.size

            # PDF boyutları (point)
            pdf_width, pdf_height = page_size

            # Resmi PDF'e sığdır
            c.drawInlineImage(
                img,
                0, 0,
                width=pdf_width,
                height=pdf_height,
                preserveAspectRatio=True,
                anchor="c"
            )
        except Exception as e:
            print(f"⚠️ Arka plan görseli çizilemedi: {e}")

    def _draw_text_block(self, c: canvas.Canvas, block: dict, page_size: Tuple[float, float]):
        """Metin bloğunu çiz"""
        text = block.get("text", "")
        bbox = block.get("bbox")
        font_size = block.get("font_size", 10)
        font_name = block.get("font_name")
        alignment = block.get("alignment", "left")

        if not text or not bbox:
            return

        # Koordinat dönüşümü (PDF sol alt köşeden başlar)
        # bbox: (x0, y0, x1, y1) - sol üstten
        x0, y0, x1, y1 = bbox
        pdf_width, pdf_height = page_size

        # Y koordinatını çevir (sol üst -> sol alt)
        # PyMuPDF top-left origin, ReportLab bottom-left origin
        y_bottom = pdf_height - (y1 / PDF_DPI) * 72
        y_top = pdf_height - (y0 / PDF_DPI) * 72
        x_left = (x0 / PDF_DPI) * 72

        # Font ayarla
        c.setFont(font_name, font_size)

        # Hizalama
        align = TextStyles.get_alignment(alignment)

        # Metni çiz (çok satırlı destek)
        lines = text.split("\n")
        line_height = font_size * 1.2
        current_y = y_top

        for line in lines:
            if line.strip():
                c.drawString(x_left, current_y, line)
            current_y -= line_height

    def clear(self):
        """Sayfa verilerini temizle"""
        self.pages_data.clear()


class HybridPDFWriter:
    """
    Hibrit PDF yazıcı
    Orijinal görseli koruyup metni Türkçe font ile üzerine yazar
    """

    def __init__(self):
        self.writer = PDFWriter()

    def create_from_pdf_reader(self, pdf_reader, translated_texts: dict = None,
                             target_lang: str = "tr") -> bytes:
        """
        PDF reader'dan yeni PDF oluştur

        Args:
            pdf_reader: PDFReader nesnesi
            translated_texts: {page_num: {block_idx: translated_text}} formatında
            target_lang: Hedef dil

        Returns:
            bytes: Yeni PDF bayt verisi
        """
        translated_texts = translated_texts or {}

        for page_num in range(len(pdf_reader)):
            # Sayfa görselini al
            pixmap = pdf_reader.get_page_pixmap(page_num, dpi=PDF_DPI)

            # Sayfa layout'unu al
            layout = pdf_reader.analyze_page_layout(page_num)

            # Çevrili metin bloklarını hazırla
            text_blocks = []
            for idx, block in enumerate(layout.text_blocks):
                # Çeviri varsa kullan, yoksa orijinal
                if page_num in translated_texts and idx in translated_texts[page_num]:
                    translated = translated_texts[page_num][idx]
                else:
                    translated = block.text

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
                    "font_size": max(8, min(24, block.font_size)),  # Font boyutu sınırlandır
                    "font_name": font_name,
                    "alignment": block.alignment
                })

            # Sayfa ekle
            page_data = {
                "background": pixmap.tobytes("png"),
                "width": pixmap.width,
                "height": pixmap.height,
                "text_blocks": text_blocks,
                "images": []  # Görseller zaten arka planda
            }

            self.writer.pages_data.append(page_data)

        # PDF oluştur
        return self.writer.generate()

    def create_with_overlay_translation(self, pdf_reader, translate_func,
                                      source_lang: str, target_lang: str) -> bytes:
        """
        Dinamik çeviri ile PDF oluştur

        Args:
            pdf_reader: PDFReader nesnesi
            translate_func: Çeviri fonksiyonu
            source_lang: Kaynak dil
            target_lang: Hedef dil

        Returns:
            bytes: Yeni PDF bayt verisi
        """
        translated_texts = {}

        # Her sayfayı çevir
        for page_num in range(len(pdf_reader)):
            layout = pdf_reader.analyze_page_layout(page_num)
            translated_texts[page_num] = {}

            for idx, block in enumerate(layout.text_blocks):
                try:
                    translated = translate_func(block.text, source_lang, target_lang)
                    translated_texts[page_num][idx] = translated
                except Exception as e:
                    print(f"⚠️ Çeviri hatası (Sayfa {page_num + 1}, Blok {idx}): {e}")
                    translated_texts[page_num][idx] = block.text

        return self.create_from_pdf_reader(pdf_reader, translated_texts, target_lang)


def create_simple_pdf(text: str, output_path: str = None,
                     title: str = "PDF Komuta Merkezi") -> bytes:
    """
    Basit metin PDF'i oluştur (test amaçlı)

    Args:
        text: Metin içeriği
        output_path: Çıktı dosya yolu
        title: PDF başlığı

    Returns:
        bytes: PDF bayt verisi
    """
    output_buffer = io.BytesIO()
    c = canvas.Canvas(output_buffer, pagesize=A4)

    # Başlık
    font_name = FontManager.get_font_name(style="bold")
    c.setFont(font_name, 18)
    c.drawString(72, 750, title)

    # Metin
    font_name = FontManager.get_font_name()
    c.setFont(font_name, 12)

    y = 700
    for line in text.split("\n"):
        c.drawString(72, y, line)
        y -= 18

        # Sayfa sonuna yakınsa yeni sayfa
        if y < 72:
            c.showPage()
            c.setFont(font_name, 12)
            y = 750

    c.save()

    if output_path:
        with open(output_path, "wb") as f:
            f.write(output_buffer.getvalue())

    return output_buffer.getvalue()
