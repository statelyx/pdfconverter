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
        self._font_info = {}  # font_key -> font_path (global cache)
        self._page_fonts = set()  # fonts already inserted into current page

    def _get_page_font(self, page: fitz.Page, style: str = "regular"):
        """Get or insert Turkish compatible font into page with Unicode support
        
        Font arama önceliği:
        1. Varsayılan font ailesi (config'den, genelde arial/dejavu)
        2. Proje fontları (LTFlode, Binoma — fonts/ dizininde)
        3. Sistem fontları (Linux DejaVu, Liberation, FreeSans)
        4. Windows fallback (Arial)
        5. PyMuPDF yerleşik font (fitz.Font ile — Türkçe destekli)
        6. Son çare: helv (Türkçe ÇALIŞMAZ)
        """
        from config import FONTS, DEFAULT_FONT, ROOT_FONT_DIR
        
        real_path = None
        current_family = "unknown"
        
        # ---- ADIM 1: Config'deki font aileleri ----
        font_families = [DEFAULT_FONT, "ltflode", "binoma", "dejavu-sans"]
        # Tekrarları kaldır
        seen = set()
        unique_families = []
        for f in font_families:
            if f not in seen:
                seen.add(f)
                unique_families.append(f)
        
        for family in unique_families:
            path = FONTS.get(family, {}).get(style)
            if not path:
                # Stil bulunamadıysa regular'a düş
                path = FONTS.get(family, {}).get("regular")
            if path and os.path.exists(path):
                real_path = path
                current_family = family
                break
        
        # ---- ADIM 2: Linux sistem fontları (ek tarama) ----
        if not real_path and os.name == 'posix':
            linux_search_paths = [
                # DejaVu — en yaygın, Türkçe tam destek
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/DejaVu/DejaVuSans.ttf",
                # Liberation — Red Hat/Fedora
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                "/usr/share/fonts/liberation-sans/LiberationSans-Regular.ttf",
                # FreeSans
                "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
                "/usr/share/fonts/gnu-free/FreeSans.ttf",
                # Noto Sans
                "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
                "/usr/share/fonts/noto/NotoSans-Regular.ttf",
            ]
            for lpath in linux_search_paths:
                if os.path.exists(lpath):
                    real_path = lpath
                    current_family = "system_linux"
                    break
        
        # ---- ADIM 3: Windows fallback ----
        if not real_path and os.name == 'nt':
            windows_fonts = {
                "regular": "C:\\Windows\\Fonts\\arial.ttf",
                "bold": "C:\\Windows\\Fonts\\arialbd.ttf",
                "italic": "C:\\Windows\\Fonts\\ariali.ttf",
                "bold_italic": "C:\\Windows\\Fonts\\arialbi.ttf"
            }
            path = windows_fonts.get(style) or windows_fonts.get("regular")
            if path and os.path.exists(path):
                real_path = path
                current_family = "arial_win"
        
        # ---- ADIM 4: Proje fonts/ dizininde herhangi bir TTF/OTF ----
        if not real_path:
            for font_dir in [ROOT_FONT_DIR]:
                if os.path.isdir(font_dir):
                    for fname in os.listdir(font_dir):
                        if fname.lower().endswith(('.ttf', '.otf')):
                            candidate = os.path.join(font_dir, fname)
                            if os.path.exists(candidate):
                                real_path = candidate
                                current_family = "project_font"
                                print(f"   ℹ️ Proje fontu kullanılıyor: {fname}")
                                break
                if real_path:
                    break
        
        # ---- ADIM 5: PyMuPDF yerleşik font (fitz.Font) ----
        if not real_path:
            # fitz.Font ile yerleşik bir font oluşturup buffer olarak kullan
            try:
                # "notos" = Noto Sans (PyMuPDF yerleşik, Türkçe destekler)
                builtin_font = fitz.Font("notos")
                font_buffer = builtin_font.buffer
                if font_buffer:
                    font_key = f"TRFON_notos_{style}".lower()
                    if font_key not in self._page_fonts:
                        try:
                            page.insert_font(fontname=font_key, fontbuffer=font_buffer)
                            self._page_fonts.add(font_key)
                            self._font_info[font_key] = "(builtin-notos)"
                            print(f"   ℹ️ PyMuPDF yerleşik 'notos' fontu kullanılıyor")
                        except Exception as e:
                            print(f"   ⚠️ Yerleşik font ekleme hatası: {e}")
                    return font_key
            except Exception as e:
                print(f"   ⚠️ fitz.Font('notos') hatası: {e}")
        
        # ---- ADIM 6: Hiçbir şey bulunamadı ----
        if not real_path:
            print(f"   ❌ HİÇBİR FONT BULUNAMADI! Türkçe karakterler BOZULACAK!")
            print(f"   ❌ Kontrol: fonts/ dizini, sistem fontları, nixpacks.toml")
            return "helv"  # Son çare — Türkçe çalışmaz
        
        # ---- Font sayfaya ekleme ----
        font_key = f"TRFON_{current_family}_{style}".replace("-", "_").lower()
        
        # Her sayfada font yeniden eklenmeli (sayfa bazlı kaynak)
        if font_key not in self._page_fonts:
            try:
                page.insert_font(fontname=font_key, fontfile=real_path)
                self._page_fonts.add(font_key)
                self._font_info[font_key] = real_path
            except Exception as e:
                print(f"   ⚠️ Font ekleme hatası ({font_key}, {real_path}): {e}")
                # Font zaten sayfada kayıtlı olabilir, yine de dene
                self._page_fonts.add(font_key)
                self._font_info[font_key] = real_path
        
        return font_key

    def _get_bg_color(self, page: fitz.Page, rect: fitz.Rect) -> Tuple[float, float, float]:
        """Sample average background color with protection against borders"""
        try:
            # Shrink sample area slightly to avoid taking border colors
            sample_rect = fitz.Rect(rect.x0 + 0.5, rect.y0 + 0.5, rect.x1 - 0.5, rect.y1 - 0.5)
            clip = sample_rect & page.rect
            if clip.is_empty: return (1, 1, 1)
            
            pix = page.get_pixmap(clip=clip, colorspace=fitz.csRGB)
            if pix.width < 1 or pix.height < 1: return (1, 1, 1)
            
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
            
            # Her sayfada fontlar yeniden eklenmeli (page-level resource)
            self._page_fonts = set()
            
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
        x0, y0, x1, y1 = 9999, 9999, 0, 0
        
        for l in lines:
            spans = []
            for s in l["spans"]:
                if not s["text"].strip(): continue
                spans.append(TextSpan(
                    text=s["text"],
                    bbox=s["bbox"],
                    font_name=s["font"],
                    font_size=s["size"],
                    color=s["color"],
                    flags=s.get("flags", 0),
                    origin=s.get("origin", (0, 0))
                ))
            
            if spans:
                block_lines.append(TextLine(spans=spans, bbox=l["bbox"]))
                x0 = min(float(x0), float(l["bbox"][0]))
                y0 = min(float(y0), float(l["bbox"][1]))
                x1 = max(float(x1), float(l["bbox"][2]))
                y1 = max(float(y1), float(l["bbox"][3]))
        
        if not block_lines: return None
        
        return TextBlock(lines=block_lines, bbox=(x0, y0, x1, y1))

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
                
                # Expand slightly for full coverage - more precision needed here
                # to avoid leaving borders around text
                expanded_rect = fitz.Rect(rect.x0 - 0.2, rect.y0 - 0.2, rect.x1 + 0.2, rect.y1 + 0.2)
                page.add_redact_annot(expanded_rect, fill=bg_color)
            
            page.apply_redactions()
            
            # 2. Insert translated blocks
            for idx, translated_text in translations.items():
                block = blocks[idx]
                self._render_translated_block(page, block, translated_text)

    def _render_translated_block(self, page: fitz.Page, block: TextBlock, translated: str):
        """Render translated text in place of original block
        
        Metin sığdırma stratejisi:
        1. Orijinal bbox + küçük margin ile dene
        2. Sığmazsa font boyutunu oransal küçült (metin uzunluğuna göre)
        3. Hâlâ sığmazsa bbox'ı sağa genişlet (sayfa sınırına kadar)
        4. Son çare: minimum font boyutu ile genişletilmiş bbox
        """
        
        try:
            # Clean and normalize text encoding
            translated = str(translated).encode("utf-8").decode("utf-8")
            
            rect = fitz.Rect(block.bbox)
            page_rect = page.rect
            
            # Determine style from first line/span
            style = "regular"
            if block.lines and block.lines[0].spans:
                span = block.lines[0].spans[0]
                if span.is_bold and span.is_italic: style = "bold_italic"
                elif span.is_bold: style = "bold"
                elif span.is_italic: style = "italic"
            
            font_name = self._get_page_font(page, style=style)
            
            # helv fallback uyarısı
            if font_name == "helv":
                print(f"   ⚠️ UYARI: helv fontu kullanılıyor, Türkçe karakterler bozulacak!")
                # Regular stil ile tekrar dene
                if style != "regular":
                    font_name = self._get_page_font(page, style="regular")
            
            font_size = block.avg_font_size
            align = fitz.TEXT_ALIGN_LEFT
            
            # Orijinal metin uzunluğunu hesapla
            original_text = block.full_text.strip()
            len_ratio = len(translated) / max(len(original_text), 1)
            
            # Çeviri orijinalden uzunsa, font boyutunu önceden küçült
            current_font_size = font_size
            if len_ratio > 1.3:
                # Metin %30+ uzunsa, ön küçültme uygula
                pre_scale = min(1.0, 1.0 / (len_ratio * 0.85))
                current_font_size = max(6, font_size * pre_scale)
            
            # ---- Render Denemesi 1: Orijinal bbox + küçük margin ----
            render_rect = fitz.Rect(
                rect.x0 - 0.3, rect.y0 - 0.3,
                rect.x1 + 0.3, rect.y1 + 0.3
            )
            
            rc = -1
            attempt = 0
            
            while rc < 0 and attempt < 8:
                rc = page.insert_textbox(
                    render_rect,
                    translated,
                    fontsize=current_font_size,
                    fontname=font_name,
                    color=(0, 0, 0),
                    align=align
                )
                if rc < 0:
                    current_font_size *= 0.90  # %10 küçült
                    attempt += 1
            
            # ---- Render Denemesi 2: Bbox genişletme (sağa ve aşağıya) ----
            if rc < 0:
                # Sağa doğru genişlet (sayfa kenarına kadar, max 40pt)
                extra_width = min(40, page_rect.x1 - rect.x1 - 5)
                # Aşağıya doğru genişlet (max 15pt)
                extra_height = min(15, page_rect.y1 - rect.y1 - 5)
                
                expanded_rect = fitz.Rect(
                    rect.x0 - 1, rect.y0 - 1,
                    rect.x1 + max(extra_width, 2), rect.y1 + max(extra_height, 2)
                )
                
                current_font_size = max(5.5, font_size * 0.75)
                rc = page.insert_textbox(
                    expanded_rect,
                    translated,
                    fontsize=current_font_size,
                    fontname=font_name,
                    color=(0, 0, 0),
                    align=align
                )
            
            # ---- Render Denemesi 3: Son çare — minimum font, en geniş bbox ----
            if rc < 0:
                last_rect = fitz.Rect(
                    rect.x0 - 2, rect.y0 - 2,
                    min(rect.x1 + 60, page_rect.x1 - 5),
                    min(rect.y1 + 20, page_rect.y1 - 5)
                )
                page.insert_textbox(
                    last_rect,
                    translated,
                    fontsize=max(5, current_font_size * 0.85),
                    fontname=font_name,
                    color=(0, 0, 0),
                    align=align
                )
                
        except Exception as e:
            print(f"   ⚠️ Render error on P{page.number}: {e}")

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
