# -*- coding: utf-8 -*-
"""
Extension: PDF → Markdown Converter
Kaynak: https://github.com/jzillmann/pdf-to-markdown
Mevcut sisteme DOKUNMADAN çalışır
"""

import io
import re
from typing import Dict, List, Optional
from dataclasses import dataclass

import fitz  # PyMuPDF


@dataclass
class MarkdownElement:
    """Markdown elementi"""
    type: str  # heading, paragraph, list, table, code, image
    content: str
    level: int = 0  # heading level, list indent
    metadata: Dict = None


class PDFToMarkdownConverter:
    """
    PDF'ten Markdown'a dönüştürücü
    pdf-to-markdown reposundan esinlenilmiştir
    """

    __version__ = "1.0.0"

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.preserve_images = self.config.get("preserve_images", True)
        self.preserve_tables = self.config.get("preserve_tables", True)
        self.output_format = self.config.get("output_format", "github")  # github, standard

    def convert(self, pdf_bytes: bytes) -> str:
        """
        PDF'i Markdown'a dönüştür

        Args:
            pdf_bytes: PDF bayt verisi

        Returns:
            str: Markdown içeriği
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        markdown_content = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            page_markdown = self._convert_page(page, page_num)
            markdown_content.append(page_markdown)

        doc.close()

        return "\n\n---\n\n".join(markdown_content)

    def _convert_page(self, page, page_num: int) -> str:
        """Sayfayı Markdown'a dönüştür"""
        blocks = page.get_text("dict")["blocks"]
        elements = []
        images = []

        # Blokları analiz et
        for block in blocks:
            if block["type"] == 0:  # Text
                element = self._parse_text_block(block)
                if element:
                    elements.append(element)
            elif block["type"] == 1:  # Image
                if self.preserve_images:
                    img_info = self._parse_image_block(block, page_num)
                    if img_info:
                        images.append(img_info)

        # Elementleri Markdown'a çevir
        markdown_parts = []

        # Başlıklar ve metin
        for element in elements:
            md_text = self._element_to_markdown(element)
            if md_text:
                markdown_parts.append(md_text)

        # Görseller
        for img in images:
            md_text = f"![Image]({img['name']})"
            markdown_parts.append(md_text)

        return "\n\n".join(markdown_parts)

    def _parse_text_block(self, block: Dict) -> Optional[MarkdownElement]:
        """Metin bloğunu analiz et"""
        lines = []
        font_sizes = []

        for line in block.get("lines", []):
            line_text = ""
            for span in line.get("spans", []):
                line_text += span["text"]
                font_sizes.append(span.get("size", 12))

            if line_text.strip():
                lines.append(line_text.strip())

        if not lines:
            return None

        # Ortalama font boyutu
        avg_font = sum(font_sizes) / len(font_sizes) if font_sizes else 12

        # Element tipi belirle
        text = "\n".join(lines)

        # Başlık kontrolü
        if avg_font > 16 and len(lines) == 1:
            level = 1 if avg_font > 24 else (2 if avg_font > 20 else 3)
            return MarkdownElement("heading", text, level)

        # Liste kontrolü
        if text.startswith(("- ", "• ", "* ", "1. ", "2. ", "3. ")):
            return MarkdownElement("list", text, 0)

        # Tablo kontrolü (basit)
        if "|" in text and text.count("|") >= 2:
            lines_list = text.split("\n")
            if all("|" in line for line in lines_list):
                return MarkdownElement("table", text, 0)

        # Kod bloğu kontrolü
        if text.startswith("```") or text.startswith("    "):
            return MarkdownElement("code", text, 0)

        # Varsayılan: paragraf
        return MarkdownElement("paragraph", text, 0)

    def _parse_image_block(self, block: Dict, page_num: int) -> Optional[Dict]:
        """Görsel bloğunu analiz et"""
        try:
            bbox = block["bbox"]
            return {
                "name": f"image_p{page_num}_{int(bbox[0])}_{int(bbox[1])}.png",
                "bbox": bbox,
                "page": page_num
            }
        except:
            return None

    def _element_to_markdown(self, element: MarkdownElement) -> str:
        """Elementi Markdown formatına çevir"""
        if element.type == "heading":
            prefix = "#" * element.level
            return f"{prefix} {element.content}"

        elif element.type == "paragraph":
            return element.content

        elif element.type == "list":
            return element.content

        elif element.type == "code":
            if not element.content.startswith("```"):
                return f"```\n{element.content}\n```"
            return element.content

        elif element.type == "table":
            lines = element.content.split("\n")
            if len(lines) >= 2:
                # Header separator ekle
                header_cols = lines[0].split("|")
                separator = "|" + "---|" * (len(header_cols) - 1)
                return lines[0] + "\n" + separator + "\n" + "\n".join(lines[1:])
            return element.content

        return element.content

    def _extract_images(self, pdf_bytes: bytes) -> List[Dict]:
        """PDF'ten görselleri çıkar"""
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        images = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            image_list = page.get_images()

            for img_index, img in enumerate(image_list):
                xref = img[0]
                base_image = doc.extract_image(xref)

                if base_image:
                    image_bytes = base_image["image"]
                    ext = base_image["ext"]

                    images.append({
                        "page": page_num,
                        "index": img_index,
                        "bytes": image_bytes,
                        "ext": ext,
                        "filename": f"image_p{page_num}_{img_index}.{ext}"
                    })

        doc.close()
        return images


class AdvancedMarkdownConverter:
    """
    Gelişmiş Markdown converter
    Daha fazla formatting koruma
    """

    def __init__(self, config=None):
        self.config = config or {}
        self.converter = PDFToMarkdownConverter(config)

    def convert_with_frontmatter(self, pdf_bytes: bytes) -> str:
        """PDF'i Markdown'a (frontmatter ile) dönüştür"""
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        # Metadata
        metadata = doc.metadata
        frontmatter = f"""---
title: {metadata.get('title', 'Untitled')}
author: {metadata.get('author', 'Unknown')}
subject: {metadata.get('subject', '')}
keywords: {metadata.get('keywords', '')}
page_count: {len(doc)}
---
"""

        doc.close()

        # Markdown içeriği
        markdown_content = self.converter.convert(pdf_bytes)

        return frontmatter + "\n\n" + markdown_content

    def convert_to_slides(self, pdf_bytes: bytes) -> str:
        """PDF'i slayt Markdown'ına dönüştür (Marp format)"""
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        slides = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")

            # Slayt ayırıcı
            slides.append(f"<!-- Slide {page_num + 1} -->\n\n{text}")

        doc.close()

        return "\n\n---\n\n".join(slides)


# Kolay kullanım fonksiyonları
def pdf_to_markdown(pdf_bytes: bytes, config: Dict = None) -> str:
    """
    PDF'i Markdown'a dönüştür (kolay fonksiyon)

    Args:
        pdf_bytes: PDF bayt verisi
        config: Yapılandırma

    Returns:
        str: Markdown içeriği
    """
    converter = PDFToMarkdownConverter(config)
    return converter.convert(pdf_bytes)


def pdf_to_markdown_with_images(pdf_bytes: bytes, output_dir: str = None) -> tuple:
    """
    PDF'i Markdown'a dönüştür (görselleriyle birlikte)

    Args:
        pdf_bytes: PDF bayt verisi
        output_dir: Görselleri kaydetmek için dizin

    Returns:
        tuple: (markdown_content, images_list)
    """
    converter = PDFToMarkdownConverter({"preserve_images": True})
    markdown = converter.convert(pdf_bytes)
    images = converter._extract_images(pdf_bytes)

    return markdown, images
