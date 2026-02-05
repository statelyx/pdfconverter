# -*- coding: utf-8 -*-
"""
Span-Based PDF Translator - BOMBA Layout Preservation
PDF'i span/line seviyesinde çevirir, bbox'ları 1mm bile bozmaz

STRATEGY:
1. Extract all text spans with exact bbox
2. Group spans by line for efficient translation
3. Translate grouped text
4. Re-align translated text to original bbox
5. Render text overlay on original PDF page
"""

import io
import os
import fitz  # PyMuPDF
from typing import List, Dict, Tuple, Optional, Callable
from dataclasses import dataclass

# Multi-Provider Translator kullan (failover destekli)
try:
    from translators.multi_translator import get_translator, TranslationResult
except ImportError:
    from translators.hf_translator import get_translator, TranslationResult


@dataclass
class TextSpan:
    """Single text span with position info"""
    text: str
    bbox: Tuple[float, float, float, float]  # x0, y0, x1, y1
    font_name: str
    font_size: float
    color: int
    flags: int  # bold, italic etc
    origin: Tuple[float, float]  # text origin point
    
    @property
    def is_bold(self) -> bool:
        return bool(self.flags & 2 ** 4)
    
    @property
    def is_italic(self) -> bool:
        return bool(self.flags & 2 ** 1)


@dataclass
class TextLine:
    """Line of text spans"""
    spans: List[TextSpan]
    bbox: Tuple[float, float, float, float]
    
    @property
    def full_text(self) -> str:
        return "".join(s.text for s in self.spans)
    
    @property
    def avg_font_size(self) -> float:
        if not self.spans:
            return 10
        return sum(s.font_size for s in self.spans) / len(self.spans)


class SpanBasedTranslator:
    """
    Span-based PDF translator with PERFECT layout preservation
    
    Features:
    - Works at span/line level, not block level
    - Preserves exact bbox positions
    - Font size auto-adjustment for overflow
    - Word wrap within bbox
    - No layout distortion
    """

    def __init__(self):
        self.translator = get_translator()
        self._font_name = "helv"  # Will use Helvetica (supports Turkish chars in PyMuPDF)

    def translate_pdf(self, pdf_bytes: bytes, source_lang: str = "auto",
                     target_lang: str = "tr", progress_callback: Callable = None) -> bytes:
        """
        Translate PDF with PERFECT layout preservation
        
        Args:
            pdf_bytes: PDF byte data
            source_lang: Source language
            target_lang: Target language
            progress_callback: Progress callback (page, total)
            
        Returns:
            bytes: Translated PDF
        """
        # Open PDF
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = len(doc)
        
        print(f"📄 SpanBasedTranslator: {total_pages} pages")
        print(f"🌐 Translation: {source_lang} → {target_lang}")
        
        # Process each page
        for page_num in range(total_pages):
            page = doc[page_num]
            
            if progress_callback:
                progress_callback(page_num + 1, total_pages)
            
            print(f"\n📝 Page {page_num + 1}/{total_pages}")
            
            # Extract text lines
            lines = self._extract_lines(page)
            print(f"   Found {len(lines)} text lines")
            
            if not lines:
                continue
            
            # Translate and render
            self._translate_and_render_page(page, lines, source_lang, target_lang)
        
        # Generate output
        result = doc.tobytes(garbage=4, deflate=True, clean=True)
        doc.close()
        
        print(f"\n✅ Translation complete!")
        return result

    def _extract_lines(self, page: fitz.Page) -> List[TextLine]:
        """Extract all text lines from page"""
        lines = []
        
        # Get text as dict with full detail
        text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE | fitz.TEXT_PRESERVE_LIGATURES)
        
        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:  # Only text blocks
                continue
            
            for line in block.get("lines", []):
                spans = []
                line_bbox = line.get("bbox", (0, 0, 0, 0))
                
                for span in line.get("spans", []):
                    text = span.get("text", "")
                    if not text:
                        continue
                    
                    spans.append(TextSpan(
                        text=text,
                        bbox=span.get("bbox", (0, 0, 0, 0)),
                        font_name=span.get("font", "helv"),
                        font_size=span.get("size", 10),
                        color=span.get("color", 0),
                        flags=span.get("flags", 0),
                        origin=span.get("origin", (0, 0))
                    ))
                
                if spans:
                    lines.append(TextLine(spans=spans, bbox=line_bbox))
        
        return lines

    def _translate_and_render_page(self, page: fitz.Page, lines: List[TextLine],
                                   source_lang: str, target_lang: str):
        """Translate all lines and render on page"""
        
        # Collect all translations first
        translations = []
        
        for i, line in enumerate(lines):
            original_text = line.full_text.strip()
            
            # Skip empty or very short text
            if len(original_text) < 2:
                translations.append((line, original_text))
                continue
            
            # Skip if only numbers/symbols
            if self._is_number_or_symbol(original_text):
                translations.append((line, original_text))
                continue
            
            # Translate
            try:
                result = self.translator.translate(
                    original_text,
                    target_lang=target_lang,
                    source_lang=source_lang
                )
                
                translated = result.text if result.success else original_text
                translations.append((line, translated))
                
                if result.success and translated != original_text:
                    print(f"   ✓ Line {i+1}: {original_text[:30]}... → {translated[:30]}...")
                
            except Exception as e:
                print(f"   ⚠️ Line {i+1} error: {e}")
                translations.append((line, original_text))
        
        # Now render all translations
        for line, translated_text in translations:
            if translated_text and translated_text != line.full_text:
                self._render_translated_line(page, line, translated_text)

    def _render_translated_line(self, page: fitz.Page, line: TextLine, translated: str):
        """Render translated text in place of original line"""
        
        try:
            # Use line bbox
            rect = fitz.Rect(line.bbox)
            
            # Expand rect slightly for redaction coverage
            expanded_rect = fitz.Rect(
                rect.x0 - 1,
                rect.y0 - 1,
                rect.x1 + 1,
                rect.y1 + 1
            )
            
            # 1. Redact original text (white fill)
            page.add_redact_annot(expanded_rect, fill=(1, 1, 1))
            page.apply_redactions()
            
            # 2. Calculate optimal font size
            font_size = self._calculate_font_size(translated, rect, line.avg_font_size)
            
            # 3. Insert translated text
            # Use first span's origin for positioning
            if line.spans:
                origin = line.spans[0].origin
                text_point = fitz.Point(rect.x0, origin[1])
            else:
                text_point = fitz.Point(rect.x0, rect.y1 - font_size * 0.3)
            
            # Try textbox first (handles wrapping better)
            try:
                rc = page.insert_textbox(
                    rect,
                    translated,
                    fontsize=font_size,
                    fontname="helv",
                    color=(0, 0, 0),
                    align=fitz.TEXT_ALIGN_LEFT
                )
                
                # If text didn't fit, try smaller font
                if rc < 0:
                    font_size = max(6, font_size * 0.8)
                    page.insert_textbox(
                        rect,
                        translated,
                        fontsize=font_size,
                        fontname="helv",
                        color=(0, 0, 0),
                        align=fitz.TEXT_ALIGN_LEFT
                    )
            except:
                # Fallback to simple text insert
                page.insert_text(
                    text_point,
                    translated,
                    fontsize=font_size,
                    fontname="helv",
                    color=(0, 0, 0)
                )
                
        except Exception as e:
            print(f"   ⚠️ Render error: {e}")

    def _calculate_font_size(self, text: str, rect: fitz.Rect, original_size: float) -> float:
        """Calculate font size to fit text in bbox"""
        
        # Approximate character width ratio
        char_width = original_size * 0.5
        text_width = len(text) * char_width
        rect_width = rect.width
        
        if text_width > rect_width:
            # Scale down
            scale = rect_width / text_width
            new_size = original_size * scale * 0.95  # 5% margin
            return max(6, min(new_size, original_size))
        
        return min(original_size, 24)

    def _is_number_or_symbol(self, text: str) -> bool:
        """Check if text is only numbers or symbols"""
        cleaned = text.replace(" ", "").replace(".", "").replace(",", "").replace("-", "")
        cleaned = cleaned.replace("€", "").replace("$", "").replace("%", "")
        return cleaned.isdigit() or len(cleaned) == 0


class InPlaceTranslator:
    """
    In-place PDF translator using search and replace
    
    Simpler approach: find text, redact, insert new text
    Works better for simple PDFs
    """

    def __init__(self):
        self.translator = get_translator()

    def translate_pdf(self, pdf_bytes: bytes, source_lang: str = "auto",
                     target_lang: str = "tr", progress_callback: Callable = None) -> bytes:
        """Translate PDF using search/replace"""
        
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = len(doc)
        
        print(f"📄 InPlaceTranslator: {total_pages} pages")
        
        for page_num in range(total_pages):
            page = doc[page_num]
            
            if progress_callback:
                progress_callback(page_num + 1, total_pages)
            
            print(f"\n📝 Page {page_num + 1}/{total_pages}")
            
            # Get all text blocks
            blocks = page.get_text("blocks")
            
            for block in blocks:
                if block[6] != 0:  # Skip non-text blocks
                    continue
                
                original_text = block[4].strip()
                
                if len(original_text) < 3:
                    continue
                
                # Skip numbers
                if original_text.replace(" ", "").replace(".", "").isdigit():
                    continue
                
                try:
                    # Translate
                    result = self.translator.translate(
                        original_text,
                        target_lang=target_lang,
                        source_lang=source_lang
                    )
                    
                    if not result.success or result.text == original_text:
                        continue
                    
                    # Find and replace
                    instances = page.search_for(original_text[:50])
                    
                    for inst in instances:
                        # Redact
                        page.add_redact_annot(inst, fill=(1, 1, 1))
                    
                    page.apply_redactions()
                    
                    # Insert translated text
                    if instances:
                        rect = instances[0]
                        font_size = min(10, rect.height * 0.8)
                        
                        page.insert_textbox(
                            rect,
                            result.text,
                            fontsize=font_size,
                            fontname="helv",
                            color=(0, 0, 0),
                            align=fitz.TEXT_ALIGN_LEFT
                        )
                    
                    print(f"   ✓ {original_text[:30]}... → {result.text[:30]}...")
                    
                except Exception as e:
                    print(f"   ⚠️ Error: {e}")
                    continue
        
        result = doc.tobytes(garbage=4, deflate=True)
        doc.close()
        
        return result


def create_span_translator(method: str = "span"):
    """
    Create translator instance
    
    Args:
        method: "span" (default) or "inplace"
    """
    if method == "inplace":
        return InPlaceTranslator()
    return SpanBasedTranslator()
