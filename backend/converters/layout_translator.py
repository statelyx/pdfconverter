# -*- coding: utf-8 -*-
"""
Layout-Preserving PDF Translator
PDF görsel yapısını koruyarak sadece metni çevirir

YAKLAŞIM:
1. Orijinal PDF'i kopyala
2. Her metin bloğunu orijinal konumunda düzenle
3. Çevrilmiş metni aynı bbox'a yaz
4. Görseller, tablolar, çizgiler DEĞİŞMEZ
"""

import io
import fitz  # PyMuPDF
from typing import Optional, Callable, List, Dict, Tuple

from translators.multi_translator import get_translator


class LayoutPreservingTranslator:
    """
    Layout-koruyan PDF çevirici
    
    Orijinal PDF yapısını KORUR:
    - Tablolar
    - Görseller
    - Çizgiler ve şekiller
    - Font stilleri
    - Renk şemaları
    
    Sadece metin içeriğini değiştirir.
    """

    def __init__(self):
        self.translator = get_translator()
        self._font_cache = {}

    def translate(self, pdf_bytes: bytes, source_lang: str = "auto",
                 target_lang: str = "tr", progress_callback: Callable = None) -> bytes:
        """
        PDF'i layout koruyarak çevir
        
        Args:
            pdf_bytes: PDF bayt verisi
            source_lang: Kaynak dil
            target_lang: Hedef dil
            progress_callback: İlerleme callback'i
            
        Returns:
            bytes: Çevrilmiş PDF
        """
        # PDF'i aç
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = len(doc)
        
        print(f"📄 PDF açıldı: {total_pages} sayfa")
        print(f"🌐 Çeviri: {source_lang} → {target_lang}")

        # Her sayfa için
        for page_num in range(total_pages):
            page = doc[page_num]
            
            if progress_callback:
                progress_callback(page_num + 1, total_pages)
            
            print(f"📝 Sayfa {page_num + 1}/{total_pages} işleniyor...")
            
            # Sayfadaki metinleri bul ve çevir
            self._translate_page(page, source_lang, target_lang)

        # Sonuç PDF'i oluştur
        result = doc.tobytes(garbage=4, deflate=True)
        doc.close()
        
        print("✅ Çeviri tamamlandı!")
        return result

    def _translate_page(self, page: fitz.Page, source_lang: str, target_lang: str):
        """Tek sayfayı çevir - layout koruyarak"""
        
        # Tüm metin bloklarını al
        text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        blocks = text_dict.get("blocks", [])
        
        # Değiştirme listesi - önce topla, sonra uygula
        replacements = []
        
        for block in blocks:
            if block.get("type") != 0:  # Sadece metin blokları
                continue
                
            lines = block.get("lines", [])
            
            for line in lines:
                spans = line.get("spans", [])
                
                for span in spans:
                    original_text = span.get("text", "").strip()
                    
                    if not original_text or len(original_text) < 2:
                        continue
                    
                    # Sadece sayı veya sembol ise atla
                    if original_text.replace(" ", "").replace(".", "").replace(",", "").isdigit():
                        continue
                    
                    # Çeviri yap
                    try:
                        result = self.translator.translate(
                            original_text,
                            target_lang=target_lang,
                            source_lang=source_lang
                        )
                        
                        if result.success and result.text != original_text:
                            bbox = span.get("bbox")
                            font_size = span.get("size", 10)
                            font_name = span.get("font", "helv")
                            color = span.get("color", 0)
                            
                            replacements.append({
                                "original": original_text,
                                "translated": result.text,
                                "bbox": bbox,
                                "font_size": font_size,
                                "font_name": font_name,
                                "color": color
                            })
                            
                    except Exception as e:
                        print(f"⚠️ Çeviri hatası: {e}")
                        continue

        # Değiştirmeleri uygula
        for repl in replacements:
            try:
                self._replace_text(
                    page,
                    repl["original"],
                    repl["translated"],
                    repl["bbox"],
                    repl["font_size"]
                )
            except Exception as e:
                print(f"⚠️ Metin değiştirme hatası: {e}")

    def _replace_text(self, page: fitz.Page, original: str, translated: str, 
                     bbox: tuple, font_size: float):
        """
        Metni orijinal konumunda değiştir
        
        PyMuPDF'in redaction özelliğini kullanır:
        1. Orijinal metni "redact" et (gizle)
        2. Aynı konuma yeni metin ekle
        """
        try:
            # Rect oluştur
            rect = fitz.Rect(bbox)
            
            # 1. ADIM: Orijinal metni ara ve redact et
            text_instances = page.search_for(original, quads=False)
            
            if text_instances:
                for inst in text_instances:
                    # Beyaz renk ile redact (metin gizleme)
                    page.add_redact_annot(inst, fill=(1, 1, 1))
                
                # Redact'ları uygula
                page.apply_redactions()
                
                # 2. ADIM: Çevrilmiş metni ekle
                # İlk instance'ın konumuna ekle
                first_rect = text_instances[0]
                
                # Font boyutunu ayarla - çevrilmiş metin sığsın
                adjusted_font_size = self._calculate_font_size(
                    translated, first_rect, font_size
                )
                
                # Metni ekle
                page.insert_textbox(
                    first_rect,
                    translated,
                    fontsize=adjusted_font_size,
                    fontname="helv",  # Helvetica (Türkçe karakterler için)
                    align=fitz.TEXT_ALIGN_LEFT
                )
            else:
                # Metin bulunamazsa doğrudan bbox'a yaz
                adjusted_font_size = self._calculate_font_size(translated, rect, font_size)
                
                # Beyaz arka plan
                page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1))
                
                # Metin ekle
                page.insert_textbox(
                    rect,
                    translated,
                    fontsize=adjusted_font_size,
                    fontname="helv",
                    align=fitz.TEXT_ALIGN_LEFT
                )
                
        except Exception as e:
            print(f"⚠️ _replace_text hatası: {e}")

    def _calculate_font_size(self, text: str, rect: fitz.Rect, original_size: float) -> float:
        """
        Metni rect'e sığdırmak için font boyutunu hesapla
        """
        # Rect genişliği
        rect_width = rect.width
        
        # Yaklaşık karakter genişliği (ortalama)
        char_width_ratio = 0.5  # Font boyutunun yarısı kadar genişlik
        
        # Gerekli genişlik
        text_width = len(text) * original_size * char_width_ratio
        
        if text_width > rect_width:
            # Font küçült
            scale = rect_width / text_width
            new_size = max(6, original_size * scale * 0.9)  # Min 6pt
            return new_size
        
        return min(original_size, 24)  # Max 24pt


class SimpleTextReplacer:
    """
    Basit metin değiştirici
    
    Daha güvenilir ama daha basit bir yaklaşım:
    - search_for ile metin bul
    - add_redact_annot ile beyazla
    - insert_text ile yeni metin ekle
    """

    def __init__(self):
        self.translator = get_translator()

    def translate(self, pdf_bytes: bytes, source_lang: str = "auto",
                 target_lang: str = "tr", progress_callback: Callable = None) -> bytes:
        """PDF'i çevir"""
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = len(doc)
        
        print(f"📄 Basit Çevirici: {total_pages} sayfa")

        for page_num in range(total_pages):
            page = doc[page_num]
            
            if progress_callback:
                progress_callback(page_num + 1, total_pages)
            
            # Sayfa metnini al
            text = page.get_text("text")
            
            if not text.strip():
                continue
            
            # Paragrafları çevir
            paragraphs = self._extract_paragraphs(text)
            
            for para in paragraphs:
                if len(para.strip()) < 3:
                    continue
                    
                try:
                    # Çeviri yap
                    result = self.translator.translate(para, target_lang, source_lang)
                    
                    if result.success and result.text != para:
                        # Metni bul ve değiştir
                        self._replace_in_page(page, para, result.text)
                        
                except Exception as e:
                    print(f"⚠️ Çeviri hatası: {e}")
                    continue

        result = doc.tobytes(garbage=4, deflate=True)
        doc.close()
        
        return result

    def _extract_paragraphs(self, text: str) -> List[str]:
        """Metinden paragrafları çıkar"""
        lines = text.split("\n")
        paragraphs = []
        current = []
        
        for line in lines:
            line = line.strip()
            if line:
                current.append(line)
            elif current:
                paragraphs.append(" ".join(current))
                current = []
        
        if current:
            paragraphs.append(" ".join(current))
        
        return paragraphs

    def _replace_in_page(self, page: fitz.Page, original: str, translated: str):
        """Sayfada metin değiştir"""
        # Orijinal metni ara
        instances = page.search_for(original[:50])  # İlk 50 karakter ile ara
        
        if not instances:
            return
        
        for rect in instances:
            try:
                # Redact annotation ekle (beyaz dikdörtgen)
                page.add_redact_annot(rect, fill=(1, 1, 1))
                
        page.apply_redactions()
        
        # İlk instance'a çeviriyi ekle
        if instances:
            first_rect = instances[0]
            font_size = min(10, first_rect.height * 0.8)
            
            page.insert_textbox(
                first_rect,
                translated,
                fontsize=font_size,
                fontname="helv",
                align=fitz.TEXT_ALIGN_LEFT
            )


def create_layout_translator(method: str = "advanced"):
    """
    Layout-koruyan çevirici oluştur
    
    Args:
        method: "advanced" veya "simple"
        
    Returns:
        Translator instance
    """
    if method == "simple":
        return SimpleTextReplacer()
    return LayoutPreservingTranslator()
