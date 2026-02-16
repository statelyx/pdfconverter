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
class TextSegment:
    """Contiguous text segment within a line (split by big horizontal gaps)"""
    spans: List[TextSpan]
    bbox: Tuple[float, float, float, float]
    text: str

    @property
    def avg_font_size(self) -> float:
        if not self.spans:
            return 10
        return sum(s.font_size for s in self.spans) / len(self.spans)

    @property
    def origin(self) -> Tuple[float, float]:
        for s in self.spans:
            if s.origin:
                return s.origin
        return (self.bbox[0], self.bbox[3])

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
        self._font_buffer_cache = {}  # font_key -> bytes (font data cache)
        self._turkish_font = True  # Font Türkçe karakter destekliyor mu?
        self._notos_available = None  # None=unknown, True/False
        self._notos_error_logged = False

    @staticmethod
    def _sanitize_text(text: str) -> str:
        """Metni font-güvenli ASCII/Latin1'e dönüştür
        
        Tüm PDF'ler için geçerli evrensel dönüşüm:
        - Türkçe özel karakterler (g, s, c, i vb.)
        - Aksan işaretli harfler (é, è, ê, å, æ, ø vb.)
        - Özel noktalama (–, —, ‘, ’, “, ” vb.)
        - Diğer Unicode karakterler
        """
        import unicodedata
        
        # Önce Türkçe özel karakterleri dönüştür
        tr_map = {
            'ı': 'i', 'İ': 'I',
            'ğ': 'g', 'Ğ': 'G',
            'ş': 's', 'Ş': 'S',
            'ç': 'c', 'Ç': 'C',
            'ö': 'o', 'Ö': 'O',
            'ü': 'u', 'Ü': 'U',
        }
        for tr_char, ascii_char in tr_map.items():
            text = text.replace(tr_char, ascii_char)
        
        # Özel noktalama ve sembolleri dönüştür
        punct_map = {
            '\u2013': '-',   # EN DASH
            '\u2014': '-',   # EM DASH
            '\u2018': "'",   # LEFT SINGLE QUOTE
            '\u2019': "'",   # RIGHT SINGLE QUOTE
            '\u201c': '"',   # LEFT DOUBLE QUOTE
            '\u201d': '"',   # RIGHT DOUBLE QUOTE
            '\u2026': '...',  # ELLIPSIS
            '\u00ab': '"',   # LEFT GUILLEMET
            '\u00bb': '"',   # RIGHT GUILLEMET
            '\u2022': '-',   # BULLET
            '\u00b7': '.',   # MIDDLE DOT
            '\u00a0': ' ',   # NON-BREAKING SPACE
            '\u200b': '',    # ZERO-WIDTH SPACE
            '\u00ad': '',    # SOFT HYPHEN
            '\u00b0': 'o',   # DEGREE SIGN
            '\u00ae': '(R)', # REGISTERED
            '\u00a9': '(C)', # COPYRIGHT
            '\u2122': '(TM)',# TRADEMARK
        }
        for uni_char, replacement in punct_map.items():
            text = text.replace(uni_char, replacement)
        
        # Aksan işaretli Avrupa harflerini decompose et
        accent_map = {
            'à': 'a', 'á': 'a', 'â': 'a', 'ã': 'a', 'ä': 'a', 'å': 'a',
            'À': 'A', 'Á': 'A', 'Â': 'A', 'Ã': 'A', 'Ä': 'A', 'Å': 'A',
            'è': 'e', 'é': 'e', 'ê': 'e', 'ë': 'e',
            'È': 'E', 'É': 'E', 'Ê': 'E', 'Ë': 'E',
            'ì': 'i', 'í': 'i', 'î': 'i', 'ï': 'i',
            'Ì': 'I', 'Í': 'I', 'Î': 'I', 'Ï': 'I',
            'ò': 'o', 'ó': 'o', 'ô': 'o', 'õ': 'o',
            'Ò': 'O', 'Ó': 'O', 'Ô': 'O', 'Õ': 'O',
            'ù': 'u', 'ú': 'u', 'û': 'u',
            'Ù': 'U', 'Ú': 'U', 'Û': 'U',
            'ñ': 'n', 'Ñ': 'N',
            'æ': 'ae', 'Æ': 'AE',
            'ø': 'o', 'Ø': 'O',
            'ß': 'ss',
            'œ': 'oe', 'Œ': 'OE',
        }
        for acc_char, replacement in accent_map.items():
            text = text.replace(acc_char, replacement)
        
        # Kalan non-ASCII karakterleri temizle
        # unicodedata.normalize ile decompose edip ASCII olmayan parçaları kaldır
        cleaned = []
        for ch in text:
            if ord(ch) < 128:
                cleaned.append(ch)
            else:
                # NFKD decomposition ile decompose et
                decomposed = unicodedata.normalize('NFKD', ch)
                ascii_part = ''.join(c for c in decomposed if ord(c) < 128)
                if ascii_part:
                    cleaned.append(ascii_part)
                # Tamamen dönüştürülemiyorsa atla (boş bırak)
        
        return ''.join(cleaned)

    def _get_page_font(self, page: fitz.Page, style: str = "regular"):
        """Get or insert Turkish compatible font into page
        
        Strateji: fontbuffer (byte) ile yükle — fontfile'dan daha güvenilir.
        
        Öncelik:
        1. PyMuPDF yerleşik 'notos' (Noto Sans — her yerde çalışır)
        2. Proje fontları (fonts/ dizini — fontbuffer ile)
        3. Sistem fontları (DejaVu, Arial — fontbuffer ile)
        4. Son çare: helv + transliterasyon
        """
        from config import FONTS, DEFAULT_FONT, ROOT_FONT_DIR, FONT_DIR
        
        # ---- ADIM 1: PyMuPDF yerleşik font (EN GÜVENİLİR) ----
        # fitz.Font("notos") = Noto Sans, Türkçe dahil 600+ dil desteği
        # Bu font PyMuPDF ile birlikte gelir, kurulum gerektirmez
        notos_key = f"TRFON_notos_{style}".lower()
        notos_base_key = "trfon_notos_base"
        if self._notos_available is not False:
            if self._notos_available is None:
                try:
                    builtin_font = fitz.Font("notos")
                    buf = builtin_font.buffer
                    if buf and len(buf) > 100:
                        self._font_buffer_cache[notos_base_key] = buf
                        self._notos_available = True
                        print(f"   ✅ PyMuPDF 'notos' fontu yüklendi ({len(buf)} bytes)")
                    else:
                        raise Exception("notos font buffer bos")
                except Exception as e:
                    self._notos_available = False
                    if not self._notos_error_logged:
                        print(f"   ⚠️ notos font hatası: {e}")
                        self._notos_error_logged = True

            if self._notos_available and notos_base_key in self._font_buffer_cache:
                if notos_key not in self._page_fonts:
                    page.insert_font(
                        fontname=notos_key,
                        fontbuffer=self._font_buffer_cache[notos_base_key]
                    )
                    self._page_fonts.add(notos_key)
                    self._font_info[notos_key] = "(builtin-notos)"
                self._turkish_font = True
                return notos_key
        
        # ---- ADIM 2: Dosyadan fontbuffer ile yükle ----
        # Font dosyasını byte olarak okuyup buffer ile ekle (daha güvenilir)
        font_paths_to_try = []
        seen_paths = set()

        def _add_font_path(label: str, path: str):
            if path and path not in seen_paths:
                font_paths_to_try.append((label, path))
                seen_paths.add(path)
        
        # Config'deki font aileleri
        font_families = [DEFAULT_FONT, "ltflode", "binoma", "dejavu-sans"]
        seen = set()
        for family in font_families:
            if family in seen:
                continue
            seen.add(family)
            path = FONTS.get(family, {}).get(style) or FONTS.get(family, {}).get("regular")
            if path:
                _add_font_path(family, path)
        
        # Linux sistem fontları
        if os.name == 'posix':
            for lpath in [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
            ]:
                _add_font_path("system", lpath)
        
        # Windows fontları
        if os.name == 'nt':
            win_path = {"regular": "C:\\Windows\\Fonts\\arial.ttf",
                        "bold": "C:\\Windows\\Fonts\\arialbd.ttf",
                        "italic": "C:\\Windows\\Fonts\\ariali.ttf"}
            wp = win_path.get(style) or win_path.get("regular")
            if wp:
                _add_font_path("arial_win", wp)
        
        # Proje fontları (fonts/ dizini)
        def _add_fonts_from_dir(base_dir: str):
            if not os.path.isdir(base_dir):
                return
            for root, _, files in os.walk(base_dir):
                for fname in files:
                    if fname.lower().endswith(('.ttf', '.otf')):
                        _add_font_path("project", os.path.join(root, fname))

        _add_fonts_from_dir(ROOT_FONT_DIR)
        _add_fonts_from_dir(FONT_DIR)
        
        # Hepsini dene
        for family_name, fpath in font_paths_to_try:
            if not os.path.exists(fpath):
                continue
            
            font_key = f"TRFON_{family_name}_{style}".replace("-", "_").lower()
            
            # Daha önce başarılı şekilde yüklendiyse tekrar kullan
            if font_key in self._page_fonts:
                self._turkish_font = True
                return font_key
            
            try:
                # Font dosyasını byte olarak oku
                if font_key not in self._font_buffer_cache:
                    with open(fpath, "rb") as f:
                        font_bytes = f.read()
                    if len(font_bytes) < 100:
                        continue
                    self._font_buffer_cache[font_key] = font_bytes
                    print(f"   ✅ Font dosyası okundu: {os.path.basename(fpath)} ({len(font_bytes)} bytes)")
                
                # fontbuffer ile ekle (fontfile yerine — daha güvenilir)
                page.insert_font(
                    fontname=font_key,
                    fontbuffer=self._font_buffer_cache[font_key]
                )
                self._page_fonts.add(font_key)
                self._font_info[font_key] = fpath
                self._turkish_font = True
                return font_key
                
            except Exception as e:
                print(f"   ⚠️ Font buffer hatası ({os.path.basename(fpath)}): {e}")
                continue
        
        # ---- ADIM 3: Hiçbir font yüklenemedi ----
        print(f"   ❌ HİÇBİR FONT YÜKLENEMEDİ — transliterasyon aktif")
        self._turkish_font = False
        return "helv"

    def _get_bg_color(self, page: fitz.Page, rect: fitz.Rect) -> Tuple[float, float, float]:
        """Metin bloğunun arka plan rengini doğru algıla
        
        Strateji: rect'in İÇİNDEN ama köşe bölgelerinden örnekle.
        Metin pikselleri koyu olacağı için filtrelenir.
        Tablo çizgileri de filtrelenir.
        """
        try:
            # Rect'i biraz küçült (tablo çizgilerinden kaçın)
            inset = 2
            sample_rect = fitz.Rect(
                rect.x0 + inset, rect.y0 + inset,
                rect.x1 - inset, rect.y1 - inset
            )
            sample_rect = sample_rect & page.rect
            if sample_rect.is_empty or sample_rect.width < 3 or sample_rect.height < 3:
                return (1, 1, 1)
            
            pix = page.get_pixmap(clip=sample_rect, colorspace=fitz.csRGB)
            if pix.width < 2 or pix.height < 2:
                return (1, 1, 1)
            
            # Köşe ve kenar piksellerini örnekle (metnin olmadığı yerler)
            w, h = pix.width, pix.height
            sample_points = [
                # 4 köşe
                (0, 0), (w-1, 0), (0, h-1), (w-1, h-1),
                # Kenar orta noktaları
                (w//2, 0), (w//2, h-1), (0, h//2), (w-1, h//2),
                # Köşe yakınları (2px içeride)
                (min(2, w-1), min(2, h-1)), (max(w-3, 0), min(2, h-1)),
                (min(2, w-1), max(h-3, 0)), (max(w-3, 0), max(h-3, 0)),
            ]
            
            colors = []
            for px, py in sample_points:
                px = max(0, min(px, w-1))
                py = max(0, min(py, h-1))
                try:
                    c = pix.pixel(px, py)
                    colors.append(c)
                except:
                    continue
            
            if not colors:
                return (1, 1, 1)
            
            # Çok koyu pikselleri filtrele (metin rengi genelde RGB < 50)
            # Ama koyu arka plan olabilir, o yüzden sadece tamamen siyahları filtrele
            bg_colors = []
            very_dark_count = 0
            for c in colors:
                brightness = (c[0] + c[1] + c[2]) / 3
                if brightness < 30:
                    very_dark_count += 1
                else:
                    bg_colors.append(c)
            
            # Eğer çoğunluk çok koyuysa, arka plan koyu demektir
            if very_dark_count > len(colors) * 0.6:
                # Koyu arka plan - tüm renkleri kullan
                bg_colors = colors
            
            if not bg_colors:
                bg_colors = colors
            
            # En yaygın rengi bul (32'lik gruplar)
            color_groups = {}
            for c in bg_colors:
                key = (c[0] // 32 * 32, c[1] // 32 * 32, c[2] // 32 * 32)
                color_groups[key] = color_groups.get(key, 0) + 1
            
            if color_groups:
                dominant = max(color_groups, key=color_groups.get)
                group = [c for c in bg_colors
                         if abs(c[0] - dominant[0]) < 40
                         and abs(c[1] - dominant[1]) < 40
                         and abs(c[2] - dominant[2]) < 40]
                if group:
                    return (
                        sum(c[0] for c in group) / len(group) / 255,
                        sum(c[1] for c in group) / len(group) / 255,
                        sum(c[2] for c in group) / len(group) / 255
                    )
            
            # Fallback: ortalama
            return (
                sum(c[0] for c in bg_colors) / len(bg_colors) / 255,
                sum(c[1] for c in bg_colors) / len(bg_colors) / 255,
                sum(c[2] for c in bg_colors) / len(bg_colors) / 255
            )
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

    def _split_line_segments(self, line: TextLine) -> List[TextSegment]:
        """Split a line into segments based on large horizontal gaps (columns)."""
        if not line.spans:
            return []

        spans = sorted(line.spans, key=lambda s: s.bbox[0])
        segments: List[TextSegment] = []

        current_spans: List[TextSpan] = []
        current_text = ""
        x0 = y0 = x1 = y1 = None
        last_x1 = None

        gap_threshold = max(8.0, line.avg_font_size * 1.1)
        space_threshold = max(2.0, line.avg_font_size * 0.25)

        def _flush():
            nonlocal current_spans, current_text, x0, y0, x1, y1
            if not current_spans:
                return
            seg = TextSegment(
                spans=current_spans,
                bbox=(x0, y0, x1, y1),
                text=current_text.strip()
            )
            segments.append(seg)
            current_spans = []
            current_text = ""
            x0 = y0 = x1 = y1 = None

        for span in spans:
            if not current_spans:
                current_spans = [span]
                current_text = span.text
                x0, y0, x1, y1 = span.bbox
                last_x1 = span.bbox[2]
                continue

            gap = span.bbox[0] - (last_x1 or span.bbox[0])
            if gap > gap_threshold:
                _flush()
                current_spans = [span]
                current_text = span.text
                x0, y0, x1, y1 = span.bbox
                last_x1 = span.bbox[2]
                continue

            if gap > space_threshold and current_text and not current_text.endswith(" ") and not span.text.startswith(" "):
                current_text += " "
            current_text += span.text
            current_spans.append(span)
            x0 = min(x0, span.bbox[0])
            y0 = min(y0, span.bbox[1])
            x1 = max(x1, span.bbox[2])
            y1 = max(y1, span.bbox[3])
            last_x1 = span.bbox[2]

        _flush()
        return segments

    def _translate_and_render_page(self, page: fitz.Page, blocks: List[TextBlock],
                                   source_lang: str, target_lang: str):
        """Translate all segments and render on page (segment-level for strict layout)"""
        
        texts_to_translate = []
        segment_keys = []  # (block_idx, line_idx, seg_idx)
        segments_map: Dict[Tuple[int, int, int], TextSegment] = {}
        
        for b_idx, block in enumerate(blocks):
            for l_idx, line in enumerate(block.lines):
                segments = self._split_line_segments(line)
                for s_idx, seg in enumerate(segments):
                    original_text = seg.text.strip()
                    if len(original_text) < 2:
                        continue
                    if self._is_number_or_symbol(original_text):
                        continue
                    key = (b_idx, l_idx, s_idx)
                    texts_to_translate.append(original_text)
                    segment_keys.append(key)
                    segments_map[key] = seg
        
        if not texts_to_translate:
            return

        print(f"   📦 Batch çeviri: {len(texts_to_translate)} segment")

        translations = {}
        from concurrent.futures import ThreadPoolExecutor, as_completed

        batch_size = 5
        max_workers = 3

        for batch_start in range(0, len(texts_to_translate), batch_size):
            batch_end = min(batch_start + batch_size, len(texts_to_translate))
            batch_texts = texts_to_translate[batch_start:batch_end]
            batch_keys = segment_keys[batch_start:batch_end]

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_key = {}
                for j, text in enumerate(batch_texts):
                    key = batch_keys[j]
                    future_to_key[executor.submit(
                        self.translator.translate,
                        text,
                        target_lang=target_lang,
                        source_lang=source_lang
                    )] = key

                for future in as_completed(future_to_key):
                    key = future_to_key[future]
                    try:
                        result = future.result(timeout=20)
                        if result.success and result.text:
                            translations[key] = result.text
                    except Exception as e:
                        print(f"   ⚠️ Segment hatası: {str(e)[:50]}")
        
        if translations:
            print(f"   🎨 Rendering {len(translations)} segment...")
            
            bg_colors = {}
            for key in translations.keys():
                seg = segments_map[key]
                rect = fitz.Rect(seg.bbox)
                bg_color = self._get_bg_color(page, rect)
                bg_colors[key] = bg_color
                expanded_rect = fitz.Rect(rect.x0 - 0.1, rect.y0 - 0.1, rect.x1 + 0.1, rect.y1 + 0.1)
                page.add_redact_annot(expanded_rect, fill=bg_color)
            
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
            
            for key, translated_text in translations.items():
                seg = segments_map[key]
                bg = bg_colors.get(key, (1, 1, 1))
                self._render_translated_segment(page, seg, translated_text, bg_color=bg)

    def _render_translated_segment(self, page: fitz.Page, seg: TextSegment, translated: str,
                                   bg_color: Tuple[float, float, float] = (1, 1, 1)):
        """Render translated text in place of original segment (strict bbox, no wrapping)"""
        try:
            translated = str(translated).encode("utf-8").decode("utf-8")
            # Transliterasyon HER ZAMAN açık
            translated = self._sanitize_text(translated)

            rect = fitz.Rect(seg.bbox)
            bg_brightness = (bg_color[0] + bg_color[1] + bg_color[2]) / 3
            text_color = (1, 1, 1) if bg_brightness < 0.45 else (0, 0, 0)

            # Style from first span
            style = "regular"
            if seg.spans:
                span = seg.spans[0]
                if span.is_bold and span.is_italic:
                    style = "bold_italic"
                elif span.is_bold:
                    style = "bold"
                elif span.is_italic:
                    style = "italic"

            font_name = self._get_page_font(page, style=style)

            # Preserve original text color if contrast ok
            if seg.spans:
                c_int = seg.spans[0].color
                if isinstance(c_int, int):
                    r = ((c_int >> 16) & 0xFF) / 255.0
                    g = ((c_int >> 8) & 0xFF) / 255.0
                    b = (c_int & 0xFF) / 255.0
                    original_text_color = (r, g, b)
                    text_brightness = (r + g + b) / 3
                    if (bg_brightness < 0.45 and text_brightness < 0.45) or (bg_brightness > 0.6 and text_brightness > 0.6):
                        text_color = (1, 1, 1) if bg_brightness < 0.45 else (0, 0, 0)
                    else:
                        text_color = original_text_color

            # Baseline koordinatları (span origin varsa onu kullan)
            base_x = rect.x0
            base_y = rect.y1 - max(1.0, seg.avg_font_size * 0.2)
            if seg.spans and seg.origin:
                try:
                    base_x = min(s.origin[0] for s in seg.spans if s.origin)
                    base_y = seg.origin[1]
                except Exception:
                    base_x = rect.x0
                    base_y = rect.y1 - max(1.0, seg.avg_font_size * 0.2)

            # Font boyutunu genişliğe sığdır (tek satır, wrap yok)
            max_width = rect.width
            min_font_size = 6
            current_font_size = seg.avg_font_size
            text_to_draw = translated
            text_width = None
            for _ in range(12):
                try:
                    text_width = fitz.get_text_length(text_to_draw, fontname=font_name, fontsize=current_font_size)
                except Exception:
                    text_width = max_width + 1  # güvenli fallback
                if text_width <= max_width or current_font_size <= min_font_size:
                    break
                current_font_size = max(min_font_size, current_font_size * 0.92)

            # Hâlâ sığmıyorsa orijinal metne dön (layout bozulmasın)
            if text_width is not None and text_width > max_width and current_font_size <= min_font_size:
                text_to_draw = self._sanitize_text(seg.text)
                current_font_size = seg.avg_font_size

            page.insert_text(
                fitz.Point(base_x, base_y),
                text_to_draw,
                fontsize=current_font_size,
                fontname=font_name,
                color=text_color
            )
        except Exception as e:
            print(f"   ⚠️ Render error on P{page.number}: {e}")

    def _render_translated_block(self, page: fitz.Page, block: TextBlock, translated: str, bg_color: Tuple[float, float, float] = (1, 1, 1)):
        """Render translated text in place of original block
        
        Metin sığdırma stratejisi:
        1. Orijinal bbox + küçük margin ile dene
        2. Sığmazsa font boyutunu oransal küçült (metin uzunluğuna göre)
        3. Hâlâ sığmazsa bbox'ı sağa genişlet (sayfa sınırına kadar)
        4. Son çare: minimum font boyutu ile genişletilmiş bbox
        
        Koyu arka plan → beyaz metin, açık arka plan → siyah metin
        Transliterasyon her zaman uygulanır (güvenlik için)
        """
        
        try:
            # Clean and normalize text encoding
            translated = str(translated).encode("utf-8").decode("utf-8")
            
            # Transliterasyonu HER ZAMAN uygula — güvenlik garantisi
            # notos font bile bazı Türkçe harfleri render edemeyebilir
            translated = self._sanitize_text(translated)
            
            rect = fitz.Rect(block.bbox)
            page_rect = page.rect
            
            # Arka plan parlaklığına göre metin rengi belirle
            bg_brightness = (bg_color[0] + bg_color[1] + bg_color[2]) / 3
            if bg_brightness < 0.45:
                # Koyu arka plan → beyaz metin
                text_color = (1, 1, 1)
            else:
                # Açık arka plan → siyah metin
                text_color = (0, 0, 0)
            
            # Determine style from first line/span
            style = "regular"
            if block.lines and block.lines[0].spans:
                span = block.lines[0].spans[0]
                if span.is_bold and span.is_italic: style = "bold_italic"
                elif span.is_bold: style = "bold"
                elif span.is_italic: style = "italic"
            
            font_name = self._get_page_font(page, style=style)
            
            # Orijinal metin rengini span'dan al
            original_text_color = None
            if block.lines and block.lines[0].spans:
                span = block.lines[0].spans[0]
                # PyMuPDF color int -> RGB tuple
                c_int = span.color
                if isinstance(c_int, int):
                    r = ((c_int >> 16) & 0xFF) / 255.0
                    g = ((c_int >> 8) & 0xFF) / 255.0
                    b = (c_int & 0xFF) / 255.0
                    original_text_color = (r, g, b)
            
            # Arka plan parlaklığına göre metin rengi:
            # 1. Orijinal metin rengi varsa ve arka planla uyumluysa onu kullan
            # 2. Değilse otomatik (koyu bg -> beyaz, açık bg -> siyah)
            if original_text_color:
                # Orijinal rengin arka planla kontrastlı olup olmadığını kontrol et
                text_brightness = (original_text_color[0] + original_text_color[1] + original_text_color[2]) / 3
                if bg_brightness < 0.45 and text_brightness < 0.45:
                    # İkisi de koyu - beyaz kullan
                    text_color = (1, 1, 1)
                elif bg_brightness > 0.6 and text_brightness > 0.6:
                    # İkisi de açık - siyah kullan
                    text_color = (0, 0, 0)
                else:
                    # Kontrast iyi - orijinal rengi kullan
                    text_color = original_text_color
            else:
                text_color = (1, 1, 1) if bg_brightness < 0.45 else (0, 0, 0)
            
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
            
            # ---- Render Denemesi 1: Orijinal bbox (minimal margin) ----
            render_rect = fitz.Rect(
                rect.x0, rect.y0 - 0.2,
                rect.x1 + 0.2, rect.y1 + 0.2
            )
            
            rc = -1
            attempt = 0
            
            while rc < 0 and attempt < 8:
                rc = page.insert_textbox(
                    render_rect,
                    translated,
                    fontsize=current_font_size,
                    fontname=font_name,
                    color=text_color,
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
                    color=text_color,
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
                    color=text_color,
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
