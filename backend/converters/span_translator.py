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
        """
        Get or insert Turkish compatible font into page with Unicode support.

        Priority: Arial (en güvenilir Türkçe desteği) → Binoma → LTFlode → DejaVu
        """
        from config import FONTS, DEFAULT_FONT

        real_path = None
        current_family = "custom"

        # Try prioritized order: Arial first (Türkçe karakter desteği garantili)
        font_families = [DEFAULT_FONT, "binoma", "ltflode", "dejavu-sans"]

        for family in font_families:
            path = FONTS.get(family, {}).get(style)
            if path and os.path.exists(path):
                real_path = path
                current_family = family
                break

        # Linux fallback için sistem fontlarını dene
        if not real_path and os.name == 'posix':
            linux_fallbacks = {
                "regular": ["/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                           "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
                "bold": ["/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
                "italic": ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"],
                "bold_italic": ["/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf"]
            }
            for fallback_path in linux_fallbacks.get(style, []):
                if os.path.exists(fallback_path):
                    real_path = fallback_path
                    current_family = "linux-system"
                    break

        if not real_path:
            # Son çare - helv (Türkçe karakterler için sorumlu)
            print(f"   ⚠️ Türkçe font bulunamadı, style={style} - karakter sorunu yaşanabilir")
            return "helv"

        # Stable font key per style
        font_key = f"TRFON_{current_family}_{style}".replace("-", "_").lower()

        if font_key not in self._font_info:
            try:
                # encoding=0 = Unicode (Identity-H) - Türkçe karakterler için kritik
                page.insert_font(fontname=font_key, fontfile=real_path, encoding=0)
                self._font_info[font_key] = font_key
            except Exception as e:
                print(f"   ⚠️ Font yükleme hatası ({font_key}): {e}")
                return "helv"
                
        return font_key

    def _get_bg_color(self, page: fitz.Page, rect: fitz.Rect) -> Tuple[float, float, float]:
        """
        Sample average background color with protection against borders.

        Bellek optimizasyonu: Pixmap yerine daha hafif yöntemler kullan.
        """
        try:
            # Shrink sample area slightly to avoid taking border colors
            sample_rect = fitz.Rect(rect.x0 + 0.5, rect.y0 + 0.5, rect.x1 - 0.5, rect.y1 - 0.5)
            clip = sample_rect & page.rect
            if clip.is_empty: return (1, 1, 1)

            # Bellek dostu: Düşük çözünürlükte pixmap al (max 50x50 pixel)
            # Bu, bellek kullanımını %80+ azaltır
            pix = page.get_pixmap(clip=clip, colorspace=fitz.csRGB, matrix=fitz.Matrix(0.1, 0.1))
            if pix.width < 1 or pix.height < 1:
                return (1, 1, 1)

            colors = []
            # Sample 6 points
            points = [
                (0, 0), (pix.width-1, 0), (0, pix.height-1),
                (pix.width-1, pix.height-1), (pix.width//2, pix.height//2),
                (pix.width//2, 0)
            ]

            for px, py in points:
                try:
                    c = pix.pixel(px, py)
                    colors.append(c)
                except: continue

            # Pixmap'ı hemen temizle - belleği boşalt
            pix = None

            if not colors: return (1, 1, 1)

            avg_r = sum(c[0] for c in colors) / len(colors) / 255
            avg_g = sum(c[1] for c in colors) / len(colors) / 255
            avg_b = sum(c[2] for c in colors) / len(colors) / 255

            return (avg_r, avg_g, avg_b)
        except:
            return (1, 1, 1)

    def translate_pdf(self, pdf_bytes: bytes, source_lang: str = "auto",
                     target_lang: str = "tr", progress_callback: Callable = None) -> bytes:
        """
        Translate PDF with PERFECT layout preservation
        """
        # Font cache'i her doküman başında bir kez reset (global cache stratejisi)
        self._font_info = {}

        # Open PDF
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = len(doc)

        print(f"📄 SpanBasedTranslator: {total_pages} pages")
        print(f"🌐 Translation: {source_lang} → {target_lang}")
        print(f"   🔡 Font stratejisi: Global cache (Arial öncelikli)")

        # Process each page
        for page_num in range(total_pages):
            page = doc[page_num]

            if progress_callback:
                progress_callback(page_num + 1, total_pages)

            print(f"\n📝 Page {page_num + 1}/{total_pages}")

            # Extract text blocks
            blocks = self._extract_blocks(page)
            print(f"   Found {len(blocks)} text blocks")

            if not blocks:
                continue

            # Translate and render
            self._translate_and_render_page(page, blocks, source_lang, target_lang)

            # Belleği temizle - pixmap cache'i boşalt
            page = None

        # Generate output
        result = doc.tobytes(garbage=4, deflate=True, clean=True)
        doc.close()

        print(f"\n✅ Translation complete!")
        return result

    def _extract_blocks(self, page: fitz.Page) -> List[TextBlock]:
        """Extract text blocks with style sensitivity for better layout preservation"""
        blocks = []
        text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        
        for b in text_dict.get("blocks", []):
            if b.get("type") != 0: continue
            
            # Group lines by style to prevent merging headers with body text
            current_group = []
            last_style = None
            
            for line in b.get("lines", []):
                # Sample dominant style (from first span)
                if line["spans"]:
                    s = line["spans"][0]
                    # style = (font_name, font_size_rounded)
                    style = (s["font"], round(s["size"]))
                    
                    if last_style and style != last_style:
                        if current_group:
                            new_block = self._assemble_block(current_group)
                            if new_block: blocks.append(new_block)
                            current_group = []
                    
                    current_group.append(line)
                    last_style = style
                else:
                    current_group.append(line)
            
            if current_group:
                new_block = self._assemble_block(current_group)
                if new_block: blocks.append(new_block)
                
        return blocks

    def _assemble_block(self, lines: List[Dict]) -> Optional[TextBlock]:
        """Convert raw dict lines into a TextBlock object"""
        if not lines: return None

        block_lines = []

        # bbox değerlerini güvenli şekilde hesapla
        x0_list, y0_list, x1_list, y1_list = [], [], [], []

        for l in lines:
            # bbox'ın tuple/list formatında olduğunu kontrol et
            bbox = l.get("bbox")
            if not bbox or len(bbox) < 4:
                continue

            spans = []
            for s in l.get("spans", []):
                if not s.get("text", "").strip(): continue
                spans.append(TextSpan(
                    text=s["text"],
                    bbox=tuple(s["bbox"]) if isinstance(s["bbox"], list) else s["bbox"],
                    font_name=s["font"],
                    font_size=s["size"],
                    color=s["color"],
                    flags=s.get("flags", 0),
                    origin=tuple(s.get("origin", (0, 0))) if isinstance(s.get("origin"), list) else s.get("origin", (0, 0))
                ))

            if spans:
                # bbox'ı tuple'a çevir ve değerleri topla
                bbox_tuple = tuple(bbox) if isinstance(bbox, list) else bbox
                block_lines.append(TextLine(spans=spans, bbox=bbox_tuple))
                x0_list.append(float(bbox_tuple[0]))
                y0_list.append(float(bbox_tuple[1]))
                x1_list.append(float(bbox_tuple[2]))
                y1_list.append(float(bbox_tuple[3]))

        if not block_lines: return None

        # Liste varsa min/max kullan, yoksa varsayılan değerler
        final_bbox = (
            min(x0_list) if x0_list else 0.0,
            min(y0_list) if y0_list else 0.0,
            max(x1_list) if x1_list else 0.0,
            max(y1_list) if y1_list else 0.0
        )

        return TextBlock(lines=block_lines, bbox=final_bbox)

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

        # CPU ve bellek optimizasyonu: Makul worker sayısı ile paralel işlem
        max_workers = 5  # Hız ve bellek dengesi
        batch_size = 10  # Daha büyük batch ile timeout riski azalır

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
                        result = future.result(timeout=45) # Block başına max 45sn
                        if result.success and result.text:
                            translations[idx] = result.text
                            print(f"   ✓ Block {idx+1} çevrildi")
                    except Exception as e:
                        print(f"   ⚠️ Block {idx+1} hatası: {str(e)[:50]}")

        # 🎨 Rendering phase
        if translations:
            print(f"   🎨 Rendering {len(translations)} blocks...")

            # Arka plan renklerini önceden hesapla (pixmaps için)
            bg_colors = {}
            for idx in translations.keys():
                block = blocks[idx]
                rect = fitz.Rect(block.bbox)
                bg_colors[idx] = self._get_bg_color(page, rect)

            # 1. Redact ALL blocks first to clear background
            for idx in translations.keys():
                block = blocks[idx]
                rect = fitz.Rect(block.bbox)

                # Expand slightly for full coverage
                expanded_rect = fitz.Rect(rect.x0 - 0.2, rect.y0 - 0.2, rect.x1 + 0.2, rect.y1 + 0.2)
                page.add_redact_annot(expanded_rect, fill=bg_colors[idx])

            page.apply_redactions()

            # 2. Insert translated blocks
            for idx, translated_text in translations.items():
                block = blocks[idx]
                self._render_translated_block(page, block, translated_text)

            # Temizlik
            bg_colors.clear()

    def _render_translated_block(self, page: fitz.Page, block: TextBlock, translated: str):
        """Render translated text in place of original block"""
        
        try:
            # Clean and normalize text encoding - NO IGNORE to catch issues
            translated = str(translated).encode("utf-8").decode("utf-8")
            
            # Print first 10 chars for debug in console
            # print(f"   DEBUG: Rendering '{translated[:15]}...'")
            
            rect = fitz.Rect(block.bbox)
            
            # Determine style from first line/span
            style = "regular"
            if block.lines and block.lines[0].spans:
                span = block.lines[0].spans[0]
                if span.is_bold and span.is_italic: style = "bold_italic"
                elif span.is_bold: style = "bold"
                elif span.is_italic: style = "italic"
            
            font_name = self._get_page_font(page, style=style)
            
            # If we fall back to helv, Turkish characters WILL break.
            # We must try to avoid this.
            
            font_size = block.avg_font_size
            align = fitz.TEXT_ALIGN_LEFT
            
            # 🎨 FONT SCALE OPTIMIZATION
            rc = -1
            attempt = 0
            current_font_size = font_size
            
            # Slightly adjust rect to ensure text fits without clipping
            # Use original bbox but expanded by 0.5pt
            render_rect = fitz.Rect(rect.x0 - 0.5, rect.y0 - 0.5, rect.x1 + 0.5, rect.y1 + 0.5)
            
            while rc < 0 and attempt < 12:
                # Try to fit text into mailbox
                rc = page.insert_textbox(
                    render_rect,
                    translated,
                    fontsize=current_font_size,
                    fontname=font_name,
                    color=(0, 0, 0),
                    align=align
                )
                if rc < 0:
                    current_font_size *= 0.92  # Slightly more aggressive reduction
                    attempt += 1
            
            # Final attempt if still failing - enlarge rect slightly
            if rc < 0:
                page.insert_textbox(
                    fitz.Rect(rect.x0 - 2, rect.y0 - 2, rect.x1 + 2, rect.y1 + 2),
                    translated,
                    fontsize=max(5, current_font_size),
                    fontname=font_name,
                    color=(0, 0, 0),
                    align=align
                )
                
        except Exception as e:
            print(f"   ⚠️ Render error on P{page.number}: {e}")

    def _calculate_font_size(self, text: str, rect: fitz.Rect, original_size: float) -> float:
        """Calculate font size to fit text in bbox with better precision"""
        if not text:
            return original_size
            
        # Standard character width ratio (typical for sans fonts)
        # Using 0.48 instead of 0.5 for safer Turkish character handling
        char_width_ratio = 0.48
        char_count = len(text)
        
        # Estimate required width
        estimated_width = char_count * original_size * char_width_ratio
        rect_width = rect.width
        
        if estimated_width > rect_width:
            # Scale down to fit width
            scale = rect_width / estimated_width
            new_size = original_size * scale * 0.96  # 4% margin
            return max(5, min(new_size, original_size))
        
        # If it's a short text, don't let it be huge
        return min(original_size, 32)

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
            
            # Try to register a Turkish support font on the page
            from core.font_manager import FontManager
            from config import DEFAULT_FONT, FONTS
            
            font_name = "helv" # Fallback
            real_path = None
            current_family = "std"
            
            # Find a valid font
            for family in [DEFAULT_FONT, "ltflode", "arial"]:
                if family in FONTS and "regular" in FONTS[family]:
                    path = FONTS[family]["regular"]
                    if os.path.exists(path):
                        real_path = path
                        current_family = family
                        break
            
            if real_path:
                font_key = f"trf_in_{current_family}".lower()
                try:
                    page.insert_font(fontname=font_key, fontfile=real_path, encoding=0)
                    font_name = font_key
                except: pass

            for block in blocks:
                if block[6] != 0:  # Skip non-text blocks
                    continue
                
                original_text = block[4].strip()
                
                if len(original_text) < 3:
                    continue
                
                # Skip numbers
                if self._is_number_or_symbol(original_text):
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
                        fit_size = min(10, rect.height * 0.8)
                        
                        page.insert_textbox(
                            rect,
                            result.text,
                            fontsize=fit_size,
                            fontname=font_name,
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
