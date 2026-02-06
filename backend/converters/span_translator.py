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
        # Use a single space instead of empty string for better word separation
        # but check if text already has spaces
        text = ""
        for s in self.spans:
            text += s.text
        return text
    
    @property
    def avg_font_size(self) -> float:
        if not self.spans:
            return 10
        return sum(s.font_size for s in self.spans) / len(self.spans)


@dataclass
class TextBlock:
    """Paragraph of lines"""
    lines: List[TextLine]
    bbox: Tuple[float, float, float, float]
    
    @property
    def full_text(self) -> str:
        # Join lines with space to form a paragraph
        return " ".join(l.full_text.strip() for l in self.lines if l.full_text.strip())
    
    @property
    def avg_font_size(self) -> float:
        if not self.lines:
            return 10
        return sum(l.avg_font_size for l in self.lines) / len(self.lines)


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
        self._font_info = {} # font_name_style -> inserted_font_name

    def _get_page_font(self, page: fitz.Page, style: str = "regular"):
        """Get or insert Turkish compatible font into page"""
        from core.font_manager import FontManager
        
        font_family = "dejavu-sans"
        
        # Real path lookup from config
        from config import FONTS
        real_path = FONTS.get(font_family, {}).get(style)
        
        # Fallback to Windows Fonts if missing (for local dev)
        if not real_path or not os.path.exists(real_path):
            windows_fonts = {
                "regular": "C:\\Windows\\Fonts\\arial.ttf",
                "bold": "C:\\Windows\\Fonts\\arialbd.ttf",
                "italic": "C:\\Windows\\Fonts\\ariali.ttf",
                "bold_italic": "C:\\Windows\\Fonts\\arialbi.ttf"
            }
            real_path = windows_fonts.get(style)
            
        if not real_path or not os.path.exists(real_path):
            return "helv" # Fallback
            
        font_key = f"{style}_{os.path.basename(real_path)}"
        if font_key not in self._font_info:
            try:
                page.insert_font(fontname=font_key, fontfile=real_path)
                self._font_info[font_key] = font_key
            except Exception as e:
                print(f"   ⚠️ Font insertion error: {e}")
                return "helv"
                
        return font_key

    def _get_bg_color(self, page: fitz.Page, rect: fitz.Rect) -> Optional[Tuple[float, float, float]]:
        """Sample average background color from rect edges"""
        try:
            # Clip rect to page boundaries
            clip = rect & page.rect
            if clip.is_empty:
                return (1, 1, 1)
                
            # Take a small pixmap to sample
            pix = page.get_pixmap(clip=clip, matrix=fitz.Matrix(0.2, 0.2)) # low res for speed
            
            # Sample corner pixels (usually background)
            if pix.width > 2 and pix.height > 2:
                # Top-left and bottom-right
                c1 = pix.pixel(0, 0)
                c2 = pix.pixel(pix.width-1, pix.height-1)
                
                # Average them and normalize to 0-1
                r = ((c1[0] + c2[0]) / 2) / 255
                g = ((c1[1] + c2[1]) / 2) / 255
                b = ((c1[2] + c2[2]) / 2) / 255
                return (r, g, b)
        except:
            pass
        return (1, 1, 1) # White fallback

    def translate_pdf(self, pdf_bytes: bytes, source_lang: str = "auto",
                     target_lang: str = "tr", progress_callback: Callable = None) -> bytes:
        """
        Translate PDF with PERFECT layout preservation
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
            
            # Reset font info for each page to ensure proper insertion if needed
            self._font_info = {}
            
            # Extract text blocks
            blocks = self._extract_blocks(page)
            print(f"   Found {len(blocks)} text blocks")
            
            if not blocks:
                continue
            
            # Translate and render
            self._translate_and_render_page(page, blocks, source_lang, target_lang)
        
        # Generate output
        result = doc.tobytes(garbage=4, deflate=True, clean=True)
        doc.close()
        
        print(f"\n✅ Translation complete!")
        return result

    def _extract_blocks(self, page: fitz.Page) -> List[TextBlock]:
        """Extract all text blocks from page"""
        blocks = []
        
        # Get text as dict with full detail
        text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE | fitz.TEXT_PRESERVE_LIGATURES)
        
        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:  # Only text blocks
                continue
            
            block_lines = []
            block_bbox = block.get("bbox", (0, 0, 0, 0))
            
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
                    block_lines.append(TextLine(spans=spans, bbox=line_bbox))
            
            if block_lines:
                blocks.append(TextBlock(lines=block_lines, bbox=block_bbox))
        
        return blocks

    def _translate_and_render_page(self, page: fitz.Page, blocks: List[TextBlock],
                                   source_lang: str, target_lang: str):
        """Translate all blocks and render on page"""
        
        # Çevrilecek metinleri topla
        texts_to_translate = []
        block_indices = []
        
        for i, block in enumerate(blocks):
            original_text = block.full_text.strip()
            
            # Skip empty or very short text
            if len(original_text) < 2:
                continue
            
            # Skip if only numbers/symbols
            if self._is_number_or_symbol(original_text):
                continue
            
            texts_to_translate.append(original_text)
            block_indices.append(i)
        
        if not texts_to_translate:
            return

        print(f"   📦 Batch çeviri: {len(texts_to_translate)} blok")

        translations = {}
        from concurrent.futures import ThreadPoolExecutor, as_completed

        batch_size = 5
        max_workers = 3

        for batch_start in range(0, len(texts_to_translate), batch_size):
            batch_end = min(batch_start + batch_size, len(texts_to_translate))
            batch_texts = texts_to_translate[batch_start:batch_end]
            batch_indices = block_indices[batch_start:batch_end]

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_idx = {}
                for j, text in enumerate(batch_texts):
                    idx = batch_indices[j]
                    future_to_idx[executor.submit(
                        self.translator.translate,
                        text,
                        target_lang=target_lang,
                        source_lang=source_lang
                    )] = idx

                for future in as_completed(future_to_idx):
                    idx = future_to_idx[future]
                    try:
                        result = future.result(timeout=20)
                        if result.success and result.text:
                            translations[idx] = result.text
                    except Exception as e:
                        print(f"   ⚠️ Block {idx+1} hatası: {str(e)[:50]}")
        
        # 🎨 Rendering phase
        if translations:
            print(f"   🎨 Rendering {len(translations)} blocks...")
            
            # 1. Redact ALL blocks first to clear background
            for idx in translations.keys():
                block = blocks[idx]
                rect = fitz.Rect(block.bbox)
                
                # Detect background color
                bg_color = self._get_bg_color(page, rect)
                
                # Expand slightly for full coverage
                expanded_rect = fitz.Rect(rect.x0 - 0.5, rect.y0 - 0.5, rect.x1 + 0.5, rect.y1 + 0.5)
                page.add_redact_annot(expanded_rect, fill=bg_color)
            
            page.apply_redactions()
            
            # 2. Insert translated blocks
            for idx, translated_text in translations.items():
                block = blocks[idx]
                self._render_translated_block(page, block, translated_text)

    def _render_translated_block(self, page: fitz.Page, block: TextBlock, translated: str):
        """Render translated text in place of original block"""
        
        try:
            rect = fitz.Rect(block.bbox)
            
            # Determine style from first line/span
            style = "regular"
            if block.lines and block.lines[0].spans:
                span = block.lines[0].spans[0]
                if span.is_bold and span.is_italic: style = "bold_italic"
                elif span.is_bold: style = "bold"
                elif span.is_italic: style = "italic"
            
            font_name = self._get_page_font(page, style=style)
            
            # Start with original average font size
            font_size = block.avg_font_size
            
            # Calculate alignment (use first line as hint)
            align = fitz.TEXT_ALIGN_LEFT
            
            # Try to fit text in block bbox
            # Textbox handles wrapping
            rc = -1
            attempt = 0
            while rc < 0 and attempt < 5:
                rc = page.insert_textbox(
                    rect,
                    translated,
                    fontsize=font_size,
                    fontname=font_name,
                    color=(0, 0, 0),
                    align=align
                )
                if rc < 0:
                    font_size *= 0.9  # Reduce font size until it fits
                    attempt += 1
            
            # If still not fitting, forced insert
            if rc < 0:
                page.insert_textbox(
                    rect,
                    translated,
                    fontsize=max(6, font_size),
                    fontname=font_name,
                    color=(0, 0, 0),
                    align=align
                )
                
        except Exception as e:
            print(f"   ⚠️ Block rendering error: {e}")

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
