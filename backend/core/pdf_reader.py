# -*- coding: utf-8 -*-
"""
PDF Reader - PyMuPDF Wrapper
PDF okuma ve analiz işlemleri
"""

import io
import fitz  # PyMuPDF
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass


@dataclass
class TextBlock:
    """Metin bloğu veri yapısı"""
    bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1)
    text: str
    font_size: float
    font_name: str
    is_bold: bool = False
    is_italic: bool = False
    alignment: str = "left"
    lines: List[str] = None

    def __post_init__(self):
        if self.lines is None:
            self.lines = []

    @property
    def width(self) -> float:
        return self.bbox[2] - self.bbox[0]

    @property
    def height(self) -> float:
        return self.bbox[3] - self.bbox[1]

    @property
    def center_x(self) -> float:
        return (self.bbox[0] + self.bbox[2]) / 2

    @property
    def center_y(self) -> float:
        return (self.bbox[1] + self.bbox[3]) / 2


@dataclass
class ImageBlock:
    """Görsel bloğu veri yapısı"""
    bbox: Tuple[float, float, float, float]
    image_data: bytes
    width: int
    height: int
    transform: Optional[Any] = None


@dataclass
class PageLayout:
    """Sayfa layout bilgisi"""
    width: float
    height: float
    text_blocks: List[TextBlock]
    images: List[ImageBlock]
    columns: int = 1
    has_tables: bool = False


class PDFReader:
    """PDF okuma ve analiz sınıfı"""

    def __init__(self, pdf_bytes: bytes = None, pdf_path: str = None):
        """
        PDF Reader başlat

        Args:
            pdf_bytes: PDF bayt verisi
            pdf_path: PDF dosya yolu
        """
        if pdf_bytes:
            self.doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        elif pdf_path:
            self.doc = fitz.open(pdf_path)
        else:
            raise ValueError("PDF verisi veya dosya yolu gereklidir")

        self.page_count = len(self.doc)

    def __len__(self) -> int:
        return self.page_count

    def __getitem__(self, index: int) -> fitz.Page:
        return self.doc[index]

    def close(self):
        """PDF文档yi kapat"""
        if hasattr(self, 'doc'):
            self.doc.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def get_page(self, page_num: int) -> fitz.Page:
        """Sayfa al"""
        if 0 <= page_num < self.page_count:
            return self.doc[page_num]
        raise IndexError(f"Sayfa numarası geçersiz: {page_num}")

    def get_page_pixmap(self, page_num: int, dpi: int = 150, matrix: fitz.Matrix = None) -> fitz.Pixmap:
        """
        Sayfanın yüksek kaliteli görselini al

        Args:
            page_num: Sayfa numarası
            dpi: DPI değeri
            matrix: Dönüşüm matrisi

        Returns:
            fitz.Pixmap: Sayfa görseli
        """
        page = self.get_page(page_num)

        if matrix is None:
            # DPI'dan matris oluştur
            scale = dpi / 72  # 72 PDF varsayılan DPI
            matrix = fitz.Matrix(scale, scale)

        return page.get_pixmap(matrix=matrix)

    def extract_text_blocks(self, page_num: int) -> List[TextBlock]:
        """
        Sayfadaki metin bloklarını çıkar

        Args:
            page_num: Sayfa numarası

        Returns:
            List[TextBlock]: Metin blokları listesi
        """
        page = self.get_page(page_num)
        blocks = page.get_text("dict")["blocks"]
        text_blocks = []

        for block in blocks:
            if block["type"] == 0:  # Metin bloğu
                bbox = block["bbox"]
                lines = []

                # Font bilgilerini topla
                font_sizes = []
                font_names = []
                is_bold = False
                is_italic = False

                for line in block.get("lines", []):
                    line_text = ""
                    for span in line.get("spans", []):
                        line_text += span["text"]
                        font_sizes.append(span.get("size", 10))
                        font_flags = span.get("flags", 0)

                        # Font flag'leri: 1=bold, 2=italic
                        if font_flags & 1:
                            is_bold = True
                        if font_flags & 2:
                            is_italic = True

                    if line_text.strip():
                        lines.append(line_text.strip())

                if lines:
                    # Ortalama font boyutu
                    avg_font_size = sum(font_sizes) / len(font_sizes) if font_sizes else 10

                    # Hizalama tahmini (basit)
                    alignment = self._detect_alignment(block, page)

                    text_blocks.append(TextBlock(
                        bbox=bbox,
                        text="\n".join(lines),
                        font_size=avg_font_size,
                        font_name="helv",  # Varsayılan, sonra düzeltilecek
                        is_bold=is_bold,
                        is_italic=is_italic,
                        alignment=alignment,
                        lines=lines
                    ))

        return text_blocks

    def extract_images(self, page_num: int) -> List[ImageBlock]:
        """
        Sayfadaki görselleri çıkar

        Args:
            page_num: Sayfa numarası

        Returns:
            List[ImageBlock]: Görsel blokları listesi
        """
        page = self.get_page(page_num)
        blocks = page.get_text("dict")["blocks"]
        images = []

        for block in blocks:
            if block["type"] == 1:  # Görsel bloğu
                bbox = block["bbox"]

                try:
                    # Görsel verisini çıkar
                    img = page.get_image(block["image"])
                    image_data = img["image"]

                    images.append(ImageBlock(
                        bbox=bbox,
                        image_data=image_data,
                        width=img.get("width", 0),
                        height=img.get("height", 0),
                        transform=block.get("transform")
                    ))
                except Exception as e:
                    print(f"⚠️ Görsel çıkarılamadı: {e}")
                    continue

        return images

    def analyze_page_layout(self, page_num: int) -> PageLayout:
        """
        Sayfa layout analiz et

        Args:
            page_num: Sayfa numarası

        Returns:
            PageLayout: Sayfa layout bilgisi
        """
        page = self.get_page(page_num)
        rect = page.rect

        text_blocks = self.extract_text_blocks(page_num)
        images = self.extract_images(page_num)

        # Sütun tespiti
        columns = self._detect_columns(page)

        # Tablo tespiti (basit)
        has_tables = self._detect_tables(text_blocks)

        return PageLayout(
            width=rect.width,
            height=rect.height,
            text_blocks=text_blocks,
            images=images,
            columns=columns,
            has_tables=has_tables
        )

    def get_full_text(self, page_num: int = None) -> str:
        """
        Sayfa veya tüm doküman metnini al

        Args:
            page_num: Sayfa numarası (None = tüm doküman)

        Returns:
            str: Metin içeriği
        """
        if page_num is not None:
            page = self.get_page(page_num)
            return page.get_text("text")
        else:
            return self.doc.get_text("text")

    def _detect_alignment(self, block: Dict, page: fitz.Page) -> str:
        """Metin hizalaması tespit et"""
        bbox = block["bbox"]
        page_width = page.rect.width

        # Bloğun sayfadaki konumuna göre hizalama tahmini
        left_margin = bbox[0]
        right_margin = page_width - bbox[2]
        center = bbox[0] + (bbox[2] - bbox[0]) / 2

        # Sayfanın ortasına yakınsa = center
        if abs(center - page_width / 2) < 50:
            return "center"
        # Sağ marjı soldan küçüksse = right
        elif right_margin < left_margin and right_margin < 20:
            return "right"
        else:
            return "left"

    def _detect_columns(self, page: fitz.Page) -> int:
        """Sütun sayısı tespit et"""
        blocks = page.get_text("dict")["blocks"]
        if not blocks:
            return 1

        # Blokların x pozisyonlarını cluster'la
        x_positions = []
        for block in blocks:
            if block["type"] == 0:
                x_positions.append(block["bbox"][0])

        if not x_positions:
            return 1

        x_positions.sort()

        # Benzer x pozisyonlarını grupla (20px tolerans)
        clusters = []
        for x in x_positions:
            if not clusters or abs(x - clusters[-1][0]) > 20:
                clusters.append([x])
            else:
                clusters[-1].append(x)

        return len(clusters)

    def _detect_tables(self, text_blocks: List[TextBlock]) -> bool:
        """Tablo tespit et (basit)"""
        # Çok sayıda düzenli blok varsa tablo olabilir
        if len(text_blocks) < 3:
            return False

        # Blokların benzer boyutta ve düzenli hizalanmış olup olmadığını kontrol et
        heights = [b.height for b in text_blocks]
        avg_height = sum(heights) / len(heights)

        # Benzer yükseklikte blok sayısı
        similar_count = sum(1 for h in heights if abs(h - avg_height) < 5)

        return similar_count >= len(text_blocks) * 0.7

    def to_bytes(self) -> bytes:
        """PDF'i bayt olarak döndür"""
        return self.doc.tobytes()

    def get_metadata(self) -> Dict[str, Any]:
        """PDF metadata'sını al"""
        metadata = self.doc.metadata
        return {
            "title": metadata.get("title", ""),
            "author": metadata.get("author", ""),
            "subject": metadata.get("subject", ""),
            "keywords": metadata.get("keywords", ""),
            "creator": metadata.get("creator", ""),
            "producer": metadata.get("producer", ""),
            "page_count": self.page_count
        }
