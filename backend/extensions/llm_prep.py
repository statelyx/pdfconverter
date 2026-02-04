# -*- coding: utf-8 -*-
"""
Extension: LLM Prep (PDF → LLM Ready)
Kaynak: https://github.com/pymupdf/pymupdf4llm
Mevcut sisteme DOKUNMADAN çalışır
PDF'i LLM input formatına hazırlar
"""

import io
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

import fitz  # PyMuPDF

try:
    # pymupdf4llm varsa kullan
    import pymupdf4llm
    PYMUPDF4LLM_AVAILABLE = True
except ImportError:
    PYMUPDF4LLM_AVAILABLE = False


@dataclass
class LLMChunk:
    """LLM için metin parçası"""
    text: str
    page: int
    bbox: List[float]  # [x0, y0, x1, y1]
    metadata: Dict[str, Any]


@dataclass
class LLMDocument:
    """LLM için doküman"""
    content: str
    chunks: List[LLMChunk]
    metadata: Dict[str, Any]
    images: List[Dict[str, Any]]
    tables: List[Dict[str, Any]]


class PDFToLLMPreparator:
    """
    PDF'i LLM için hazırlar
    pymupdf4llm wrapper'ı
    """

    __version__ = "1.0.0"

    def __init__(self, config: Optional[Dict] = None):
        """
        LLM preparator başlat

        Args:
            config: Yapılandırma
                - chunk_size: Parça boyutu (karakter)
                - overlap: Parçalar arası overlap
                - include_images: Görselleri dahil et
                - include_tables: Tabloları dahil et
                - output_format: Çıktı formatı (text, markdown, json)
        """
        self.config = config or {}
        self.chunk_size = self.config.get("chunk_size", 4000)
        self.overlap = self.config.get("overlap", 200)
        self.include_images = self.config.get("include_images", True)
        self.include_tables = self.config.get("include_tables", True)
        self.output_format = self.config.get("output_format", "text")

    def prepare(self, pdf_bytes: bytes) -> LLMDocument:
        """
        PDF'i LLM için hazırla

        Args:
            pdf_bytes: PDF bayt verisi

        Returns:
            LLMDocument: Hazırlanmış doküman
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        # Metadata
        metadata = {
            "title": doc.metadata.get("title", ""),
            "author": doc.metadata.get("author", ""),
            "subject": doc.metadata.get("subject", ""),
            "page_count": len(doc),
            "format": "pdf"
        }

        # İçeriği çıkar
        chunks = []
        all_text = []

        for page_num in range(len(doc)):
            page = doc[page_num]

            # Metin blokları
            blocks = page.get_text("dict")["blocks"]

            for block in blocks:
                if block["type"] == 0:  # Text
                    chunk = self._extract_text_block(block, page_num)
                    if chunk:
                        chunks.append(chunk)
                        all_text.append(chunk.text)

                elif block["type"] == 1 and self.include_images:  # Image
                    img_info = self._extract_image_block(block, page_num)
                    if img_info:
                        # Görsel için açıklama chunk oluştur
                        chunks.append(LLMChunk(
                            text=f"[Image: {img_info['name']}]",
                            page=page_num,
                            bbox=block["bbox"],
                            metadata={"type": "image", "image_info": img_info}
                        ))

        # Büyük chunk'ları böl
        final_chunks = self._split_large_chunks(chunks)

        # Görseller
        images = self._extract_images(doc) if self.include_images else []

        # Tablolar
        tables = self._extract_tables(doc) if self.include_tables else []

        doc.close()

        return LLMDocument(
            content="\n\n".join(all_text),
            chunks=final_chunks,
            metadata=metadata,
            images=images,
            tables=tables
        )

    def _extract_text_block(self, block: Dict, page_num: int) -> Optional[LLMChunk]:
        """Metin bloğunu çıkar"""
        text = ""
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text += span["text"]
            text += "\n"

        if text.strip():
            return LLMChunk(
                text=text.strip(),
                page=page_num,
                bbox=list(block["bbox"]),
                metadata={"type": "text"}
            )
        return None

    def _extract_image_block(self, block: Dict, page_num: int) -> Optional[Dict]:
        """Görsel bilgisini çıkar"""
        try:
            bbox = block["bbox"]
            return {
                "name": f"image_p{page_num}_{int(bbox[0])}_{int(bbox[1])}",
                "bbox": bbox,
                "page": page_num
            }
        except:
            return None

    def _split_large_chunks(self, chunks: List[LLMChunk]) -> List[LLMChunk]:
        """Büyük chunk'ları böl"""
        result = []

        for chunk in chunks:
            text = chunk.text

            if len(text) <= self.chunk_size:
                result.append(chunk)
            else:
                # Chunk'ları böl
                words = text.split()
                current_chunk = []

                for i, word in enumerate(words):
                    current_chunk.append(word)

                    # Chunk boyutu kontrolü
                    chunk_text = " ".join(current_chunk)
                    if len(chunk_text) >= self.chunk_size:
                        result.append(LLMChunk(
                            text=chunk_text,
                            page=chunk.page,
                            bbox=chunk.bbox,
                            metadata=chunk.metadata
                        ))
                        current_chunk = []

                        # Overlap için son kelimeleri koru
                        if self.overlap > 0:
                            overlap_words = words[max(0, i - self.overlap//5):i+1]
                            current_chunk = overlap_words
                        else:
                            current_chunk = []

                # Kalan metni ekle
                if current_chunk:
                    result.append(LLMChunk(
                        text=" ".join(current_chunk),
                        page=chunk.page,
                        bbox=chunk.bbox,
                        metadata=chunk.metadata
                    ))

        return result

    def _extract_images(self, doc) -> List[Dict]:
        """PDF'ten görselleri çıkar"""
        images = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            image_list = page.get_images()

            for img_index, img in enumerate(image_list):
                try:
                    xref = img[0]
                    base_image = doc.extract_image(xref)

                    if base_image:
                        images.append({
                            "page": page_num,
                            "index": img_index,
                            "format": base_image["ext"],
                            "size": len(base_image["image"]),
                            "width": base_image.get("width", 0),
                            "height": base_image.get("height", 0)
                        })
                except:
                    continue

        return images

    def _extract_tables(self, doc) -> List[Dict]:
        """PDF'ten tabloları çıkar (basit yaklaşım)"""
        tables = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            blocks = page.get_text("dict")["blocks"]

            # Tablo benzeri yapıları ara
            for block in blocks:
                if block["type"] == 0:  # Text
                    text = ""
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            text += span["text"] + " "
                        text += "\n"

                    # Tablo kontrolü (birden fazla "|" karakteri)
                    if text.count("|") >= 4:
                        tables.append({
                            "page": page_num,
                            "bbox": block["bbox"],
                            "content": text.strip(),
                            "rows": len(text.split("\n"))
                        })

        return tables

    def to_markdown(self, pdf_bytes: bytes) -> str:
        """
        PDF'i Markdown'a dönüştür (LLM için)

        Args:
            pdf_bytes: PDF bayt verisi

        Returns:
            str: Markdown içeriği
        """
        doc = self.prepare(pdf_bytes)
        md_content = []

        # Frontmatter
        md_content.append(f"""---
title: {doc.metadata.get('title', 'Untitled')}
page_count: {doc.metadata.get('page_count', 0)}
---
""")

        # İçerik
        for chunk in doc.chunks:
            if chunk.metadata.get("type") == "text":
                md_content.append(chunk.text)

        return "\n\n".join(md_content)

    def to_json(self, pdf_bytes: bytes) -> str:
        """
        PDF'i JSON'a dönüştür (LLM için)

        Args:
            pdf_bytes: PDF bayt verisi

        Returns:
            str: JSON içeriği
        """
        doc = self.prepare(pdf_bytes)

        # Serileştirilebilir format
        data = {
            "metadata": doc.metadata,
            "content": doc.content,
            "chunks": [
                {
                    "text": chunk.text,
                    "page": chunk.page,
                    "bbox": chunk.bbox,
                    "metadata": chunk.metadata
                }
                for chunk in doc.chunks
            ],
            "images": doc.images,
            "tables": doc.tables
        }

        return json.dumps(data, ensure_ascii=False, indent=2)

    def to_rag_format(self, pdf_bytes: bytes) -> List[Dict]:
        """
        PDF'i RAG (Retrieval Augmented Generation) formatına dönüştür

        Args:
            pdf_bytes: PDF bayt verisi

        Returns:
            List[Dict]: RAG için doküman parçaları
        """
        doc = self.prepare(pdf_bytes)
        rag_docs = []

        for i, chunk in enumerate(doc.chunks):
            rag_docs.append({
                "id": f"chunk_{i}",
                "text": chunk.text,
                "metadata": {
                    "page": chunk.page,
                    "bbox": chunk.bbox,
                    "source": doc.metadata.get("title", "unknown")
                }
            })

        return rag_docs


class LLMEmbeddingPreparator:
    """
    LLM embedding için hazırlık
    Vektör veritabanına uygun format
    """

    def __init__(self, config=None):
        self.config = config or {}
        self.preparator = PDFToLLMPreparator(config)

    def prepare_for_embedding(self, pdf_bytes: bytes) -> List[Dict]:
        """
        PDF'i embedding için hazırla

        Args:
            pdf_bytes: PDF bayt verisi

        Returns:
            List[Dict]: {id, text, metadata} formatında dokümanlar
        """
        doc = self.preparator.prepare(pdf_bytes)
        embeddings = []

        for i, chunk in enumerate(doc.chunks):
            embeddings.append({
                "id": f"{doc.metadata.get('title', 'doc')}_{i}",
                "text": chunk.text,
                "metadata": {
                    "page": chunk.page,
                    "bbox": chunk.bbox,
                    "source": doc.metadata.get("title", "unknown"),
                    "author": doc.metadata.get("author", ""),
                    "chunk_index": i
                }
            })

        return embeddings


# Kolay kullanım fonksiyonları
def prepare_pdf_for_llm(pdf_bytes: bytes, config: Dict = None) -> LLMDocument:
    """PDF'i LLM için hazırla (kolay fonksiyon)"""
    preparator = PDFToLLMPreparator(config)
    return preparator.prepare(pdf_bytes)


def pdf_to_llm_markdown(pdf_bytes: bytes, config: Dict = None) -> str:
    """PDF'i LLM Markdown'ına çevir (kolay fonksiyon)"""
    preparator = PDFToLLMPreparator(config)
    return preparator.to_markdown(pdf_bytes)


def pdf_to_llm_json(pdf_bytes: bytes, config: Dict = None) -> str:
    """PDF'i LLM JSON'ına çevir (kolay fonksiyon)"""
    preparator = PDFToLLMPreparator(config)
    return preparator.to_json(pdf_bytes)


def pdf_to_rag_format(pdf_bytes: bytes, config: Dict = None) -> List[Dict]:
    """PDF'i RAG formatına çevir (kolay fonksiyon)"""
    preparator = PDFToLLMPreparator(config)
    return preparator.to_rag_format(pdf_bytes)
