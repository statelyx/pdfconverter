# -*- coding: utf-8 -*-
"""
PDF to Image Converter
PDF sayfalarını yüksek kaliteli görsellere dönüştürme
"""

import io
import os
import tempfile
from typing import List, Optional

import fitz  # PyMuPDF
from PIL import Image
from tqdm import tqdm

from core.pdf_reader import PDFReader
from config import PDF_DPI


class PDFToImageConverter:
    """
    PDF'ten gösele dönüştürücü
    Yüksek kaliteli PNG/JPG çıktı
    """

    def __init__(self, dpi: int = PDF_DPI):
        """
        Converter başlat

        Args:
            dpi: Çıktı DPI değeri
        """
        self.dpi = dpi

    def convert(self, pdf_bytes: bytes, format: str = "png",
               quality: int = 95, progress_callback = None) -> bytes:
        """
        PDF'i gösele dönüştür (tek sayfa için)

        Args:
            pdf_bytes: PDF bayt verisi
            format: Çıktı formatı (png, jpg)
            quality: JPG kalitesi (1-100)
            progress_callback: İlerleme callback'i

        Returns:
            bytes: Görsel bayt verisi (ilk sayfa)
        """
        with PDFReader(pdf_bytes=pdf_bytes) as reader:
            if len(reader) == 0:
                raise ValueError("PDF boş")

            # İlk sayfayı al
            pixmap = reader.get_page_pixmap(0, dpi=self.dpi)

            # Format belirle
            fmt = format.lower()
            if fmt not in ["png", "jpg", "jpeg"]:
                fmt = "png"

            # Bayt olarak al
            img_bytes = pixmap.tobytes(fmt)

            return img_bytes

    def convert_all_pages(self, pdf_bytes: bytes, format: str = "png",
                         quality: int = 95, progress_callback = None) -> List[bytes]:
        """
        Tüm sayfaları gösele dönüştür

        Args:
            pdf_bytes: PDF bayt verisi
            format: Çıktı formatı (png, jpg)
            quality: JPG kalitesi
            progress_callback: İlerleme callback'i

        Returns:
            List[bytes]: Görsel bayt verileri listesi
        """
        with PDFReader(pdf_bytes=pdf_bytes) as reader:
            total_pages = len(reader)
            images = []

            for page_num in range(total_pages):
                if progress_callback:
                    progress_callback(page_num + 1, total_pages)

                # Sayfa görselini al
                pixmap = reader.get_page_pixmap(page_num, dpi=self.dpi)

                # Format belirle
                fmt = format.lower()
                if fmt not in ["png", "jpg", "jpeg"]:
                    fmt = "png"

                # Bayt olarak al
                img_bytes = pixmap.tobytes(fmt)
                images.append(img_bytes)

            return images

    def convert_to_zip(self, pdf_bytes: bytes, format: str = "png",
                      quality: int = 95) -> bytes:
        """
        Tüm sayfaları ZIP olarak döndür

        Args:
            pdf_bytes: PDF bayt verisi
            format: Çıktı formatı
            quality: JPG kalitesi

        Returns:
            bytes: ZIP bayt verisi
        """
        import zipfile

        images = self.convert_all_pages(pdf_bytes, format, quality)

        # ZIP oluştur
        output = io.BytesIO()

        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for i, img_bytes in enumerate(images):
                ext = format.lower()
                if ext == "jpg":
                    ext = "jpeg"
                filename = f"page_{i+1}.{ext}"
                zip_file.writestr(filename, img_bytes)

        return output.getvalue()


class ImageConverter:
    """
    Görsel işleme ve optimizasyon
    """

    @staticmethod
    def optimize_image(img_bytes: bytes, max_size: tuple = None,
                      quality: int = 85, format: str = "png") -> bytes:
        """
        Görseli optimize et

        Args:
            img_bytes: Görsel bayt verisi
            max_size: Maksimum boyut (width, height)
            quality: JPG kalitesi
            format: Çıktı formatı

        Returns:
            bytes: Optimize edilmiş görsel
        """
        img = Image.open(io.BytesIO(img_bytes))

        # Boyutlandır
        if max_size:
            img.thumbnail(max_size, Image.Resampling.LANCZOS)

        # Çıktı
        output = io.BytesIO()

        if format.lower() in ["jpg", "jpeg"]:
            img.save(output, format="JPEG", quality=quality, optimize=True)
        else:
            img.save(output, format="PNG", optimize=True)

        return output.getvalue()

    @staticmethod
    def create_thumbnail(img_bytes: bytes, size: tuple = (150, 200)) -> bytes:
        """
        Küçük resim oluştur

        Args:
            img_bytes: Görsel bayt verisi
            size: Thumbnail boyutu

        Returns:
            bytes: Thumbnail bayt verisi
        """
        img = Image.open(io.BytesIO(img_bytes))
        img.thumbnail(size, Image.Resampling.LANCZOS)

        output = io.BytesIO()
        img.save(output, format="PNG")
        return output.getvalue()

    @staticmethod
    def convert_format(img_bytes: bytes, target_format: str) -> bytes:
        """
        Görsel formatını değiştir

        Args:
            img_bytes: Görsel bayt verisi
            target_format: Hedef format (png, jpg, webp)

        Returns:
            bytes: Dönüştrülmüş görsel
        """
        img = Image.open(io.BytesIO(img_bytes))

        output = io.BytesIO()

        if target_format.lower() in ["jpg", "jpeg"]:
            # PNG'den JPG'ye çevirirken RGBA'yı RGB'ye çevir
            if img.mode == "RGBA":
                img = img.convert("RGB")
            img.save(output, format="JPEG", quality=95)
        elif target_format.lower() == "webp":
            img.save(output, format="WebP", quality=95)
        else:
            img.save(output, format="PNG")

        return output.getvalue()


class PDFPreviewGenerator:
    """
    PDF önizleme görselleri oluşturucu
    Küçük boyutlu, hızlı yükleme için
    """

    def __init__(self, preview_dpi: int = 72):
        """
        Preview generator başlat

        Args:
            preview_dpi: Önizleme DPI değeri
        """
        self.preview_dpi = preview_dpi

    def generate_previews(self, pdf_bytes: bytes, max_pages: int = 10) -> List[bytes]:
        """
        PDF önizlemeleri oluştur

        Args:
            pdf_bytes: PDF bayt verisi
            max_pages: Maksimum önizleme sayfası

        Returns:
            List[bytes]: Önizleme görselleri
        """
        converter = PDFToImageConverter(dpi=self.preview_dpi)

        with PDFReader(pdf_bytes=pdf_bytes) as reader:
            total = min(len(reader), max_pages)
            previews = []

            for i in range(total):
                pixmap = reader.get_page_pixmap(i, dpi=self.preview_dpi)
                img_bytes = pixmap.tobytes("png")

                # Thumbnail boyutuna getir
                thumb = ImageConverter.create_thumbnail(img_bytes, size=(200, 300))
                previews.append(thumb)

            return previews

    def generate_preview_grid(self, pdf_bytes: bytes,
                             cols: int = 5, max_pages: int = 10) -> bytes:
        """
        Önizleme grid'i oluştur

        Args:
            pdf_bytes: PDF bayt verisi
            cols: Sütun sayısı
            max_pages: Maksimum sayfa

        Returns:
            bytes: Grid görseli
        """
        previews = self.generate_previews(pdf_bytes, max_pages)

        if not previews:
            return b""

        # Grid oluştur
        from PIL import Image

        images = [Image.open(io.BytesIO(p)) for p in previews]

        # Grid boyutları
        thumb_width, thumb_height = images[0].size
        rows = (len(images) + cols - 1) // cols

        grid_width = thumb_width * cols
        grid_height = thumb_height * rows

        # Yeni görsel oluştur
        grid = Image.new("RGB", (grid_width, grid_height), color="white")

        # Görselleri yerleştir
        for i, img in enumerate(images):
            row = i // cols
            col = i % cols
            x = col * thumb_width
            y = row * thumb_height
            grid.paste(img, (x, y))

        # Çıktı
        output = io.BytesIO()
        grid.save(output, format="PNG")
        return output.getvalue()


def convert_pdf_to_image(pdf_bytes: bytes, page_num: int = 0,
                        format: str = "png", dpi: int = 300) -> bytes:
    """
    PDF'ten gösele dönüşüm (kolay fonksiyon)

    Args:
        pdf_bytes: PDF bayt verisi
        page_num: Sayfa numarası
        format: Çıktı formatı
        dpi: DPI değeri

    Returns:
        bytes: Görsel bayt verisi
    """
    converter = PDFToImageConverter(dpi=dpi)

    with PDFReader(pdf_bytes=pdf_bytes) as reader:
        if page_num >= len(reader):
            page_num = 0

        pixmap = reader.get_page_pixmap(page_num, dpi=dpi)
        return pixmap.tobytes(format.lower())
