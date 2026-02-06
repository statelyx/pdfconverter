# -*- coding: utf-8 -*-
"""
Span-Based PDF Translator v2 - HTMLBox Rendering
PDF'i satır satır çevirir, layout'ı korur, Türkçe karakterleri destekler

STRATEGY:
1. Extract all text lines with exact bbox
2. Translate each line separately
3. Render with insert_htmlbox (CSS support, Turkish characters)
4. Preserve original layout
"""

import fitz  # PyMuPDF
from typing import List, Dict, Tuple, Optional, Callable

# Multi-Provider Translator kullan (failover destekli)
try:
    from translators.multi_translator import get_translator
except ImportError:
    from translators.hf_translator import get_translator


class SpanBasedTranslator:
    """
    HTMLBox-based PDF translator with perfect layout preservation

    Features:
    - Line-by-line translation (each text item translated separately)
    - insert_htmlbox for rendering (CSS support, Turkish character support)
    - Preserves exact bbox positions
    - Auto word-wrap and alignment
    """

    def __init__(self):
        self.translator = get_translator()
        self._font_cache = {}

    def translate_pdf(self, pdf_bytes: bytes, source_lang: str = "auto",
                     target_lang: str = "tr", progress_callback: Callable = None) -> bytes:
        """
        Translate PDF with PERFECT layout preservation
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = len(doc)

        print(f"📄 HTMLBoxTranslator: {total_pages} pages")
        print(f"🌐 Translation: {source_lang} → {target_lang}")

        # Process each page
        for page_num in range(total_pages):
            page = doc[page_num]

            if progress_callback:
                progress_callback(page_num + 1, total_pages)

            print(f"\n📝 Page {page_num + 1}/{total_pages}")

            # 1. Extract text items (line by line)
            items = self._extract_text_items(page)
            print(f"   Found {len(items)} text items")

            if not items:
                continue

            # 2. Translate each item
            translations = self._translate_items(items, source_lang, target_lang)

            # 3. Render translated text
            self._render_translations(page, items, translations)

        # Generate output
        result = doc.tobytes(garbage=4, deflate=True, clean=True)
        doc.close()

        print(f"\n✅ Translation complete!")
        return result

    def _extract_text_items(self, page: fitz.Page) -> List[Dict]:
        """
        Her metin satırını ayrı ayrı çıkar.

        Returns:
            List[Dict]: {
                'text': str,
                'bbox': tuple,
                'font_size': float,
                'is_bold': bool,
                'is_italic': bool,
                'color': tuple,
                'alignment': int
            }
        """
        items = []
        text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:
                continue

            for line in block.get("lines", []):
                # Tüm span'ları birleştir (boşlukları koruyarak)
                line_text = ""
                for span in line.get("spans", []):
                    line_text += span.get("text", "")

                if not line_text.strip():
                    continue

                # İlk span'dan stil bilgilerini al
                first_span = line.get("spans", [{}])[0]
                bbox = tuple(line.get("bbox"))
                font_size = first_span.get("size", 10)
                flags = first_span.get("flags", 0)
                color = first_span.get("color", 0)

                # RGB color
                if isinstance(color, int):
                    r = (color >> 16) & 255
                    g = (color >> 8) & 255
                    b = color & 255
                    color_rgb = (r, g, b)
                else:
                    color_rgb = (0, 0, 0)

                # Hizalamayı tespit et
                alignment = self._detect_alignment(bbox, page.rect)

                items.append({
                    'text': line_text.strip(),
                    'bbox': bbox,
                    'font_size': font_size,
                    'is_bold': bool(flags & 2**4),
                    'is_italic': bool(flags & 2**1),
                    'color': color_rgb,
                    'alignment': alignment
                })

        return items

    def _detect_alignment(self, bbox: Tuple, page_rect: fitz.Rect) -> int:
        """
        Metin hizalamasını tespit et.

        Returns:
            0: left, 1: center, 2: right
        """
        x0, y0, x1, y1 = bbox
        rect_width = page_rect.x1 - page_rect.x0

        # Sol kenara yakın mı?
        if x0 < page_rect.x0 + rect_width * 0.3:
            return 0  # left

        # Sağ kenara yakın mı?
        if x1 > page_rect.x1 - rect_width * 0.3:
            return 2  # right

        # Ortada mı?
        center = page_rect.x0 + rect_width / 2
        if abs((x0 + x1) / 2 - center) < rect_width * 0.1:
            return 1  # center

        return 0  # default left

    def _translate_items(self, items: List[Dict], source_lang: str,
                        target_lang: str) -> List[Optional[str]]:
        """
        Her metin öğesini çevir - BATCH ile hızlı çeviri.

        Returns:
            List[Optional[str]]: Çevrilmiş metinler veya None (hata durumunda)
        """
        translations = [None] * len(items)

        # Batch çeviri - çok fazla istekten kaçınmak için
        batch_size = 20  # 20 satır bir anda
        texts_to_translate = []
        indices = []

        for i, item in enumerate(items):
            text = item['text']

            # Çok kısa metinleri atla
            if len(text) < 2:
                continue

            # Sadece rakamları atla
            if self._is_number_or_symbol(text):
                continue

            texts_to_translate.append(text)
            indices.append(i)

        # Batch çeviri - paralel değil, sıralı (timeout riski için)
        batch_size = 20  # Her seferde 20 satır
        all_translations = []

        for batch_start in range(0, len(texts_to_translate), batch_size):
            batch_end = min(batch_start + batch_size, len(texts_to_translate))
            batch_texts = texts_to_translate[batch_start:batch_end]

            # Bu batch'i çevir (sıralı, timeout için güvenli)
            for j, text in enumerate(batch_texts):
                try:
                    result = self.translator.translate(
                        text,
                        target_lang=target_lang,
                        source_lang=source_lang
                    )

                    if result.success and result.text and result.text != text:
                        all_translations.append(result.text)
                    else:
                        all_translations.append(text)  # Orijinali koru

                except Exception as e:
                    print(f"   ⚠️ Çeviri hatası: {str(e)[:50]}")
                    all_translations.append(text)  # Orijinali koru

        # Sonuçları doğru index'e yerleştir
        for idx, real_idx in enumerate(indices):
            original_text = texts_to_translate[idx]
            translated = all_translations[idx]

            if translated != original_text:  # Çeviri başarılıysa değiştir
                translations[real_idx] = translated
                print(f"   ✓ Çevrildi: {original_text[:30]}... → {translated[:30]}...")

        return translations

    def _render_translations(self, page: fitz.Page, items: List[Dict],
                            translations: List[Optional[str]]):
        """
        Çevrilmiş metinleri sayfaya render et.
        """
        # Tüm redaction'ları topla ve tek seferde uygula
        redacts = []

        for item, translated in zip(items, translations):
            if translated is None:
                continue  # Çeviri yok, atla

            rect = fitz.Rect(item['bbox'])

            # Arka plan rengi
            bg_color = self._get_bg_color(page, rect)

            # Redaction ekle
            redacts.append((rect, bg_color))

        # Redaction'ları uygula
        for rect, bg_color in redacts:
            page.draw_rect(rect, color=bg_color, fill=bg_color)

        # Çevrilmiş metinleri yaz
        for item, translated in zip(items, translations):
            if translated is None:
                continue

            self._render_with_htmlbox(page, item, translated)

    def _render_with_htmlbox(self, page: fitz.Page, item: Dict, translated: str):
        """
        insert_htmlbox ile rendering - Türkçe karakter desteği ile.

        HTML/CSS kullanarak:
        - Otomatik word wrap
        - Alignment
        - Font styling (bold, italic)
        - Türkçe karakterler (ş, ğ, ı, ö, ü)
        """
        rect = fitz.Rect(item['bbox'])

        # CSS oluştur
        css_parts = []

        # Font family - sans-serif (Türkçe karakter destekli)
        css_parts.append("font-family: sans-serif;")

        # Font size
        font_size = item['font_size']
        css_parts.append(f"font-size: {font_size}pt;")

        # Font weight
        if item['is_bold']:
            css_parts.append("font-weight: bold;")

        # Font style
        if item['is_italic']:
            css_parts.append("font-style: italic;")

        # Color
        r, g, b = item['color']
        css_parts.append(f"color: rgb({r}, {g}, {b});")

        # Line height
        css_parts.append("line-height: 1.2;")

        # Text align
        align_map = {0: "left", 1: "center", 2: "right"}
        css_parts.append(f"text-align: {align_map.get(item['alignment'], 'left')};")

        # Margin ve padding
        css_parts.append("margin: 0; padding: 0;")

        css = " ".join(css_parts)

        # HTML
        html = f'<p style="{css}">{translated}</p>'

        # insert_htmlbox - Türkçe karakterleri destekler
        try:
            page.insert_htmlbox(
                rect,
                html,
                css=css,
                align=item.get('alignment', 0)
            )
        except Exception as e:
            print(f"   ⚠️ insert_htmlbox hatası: {e}")
            # Fallback: insert_text
            self._render_with_insert_text(page, item, translated)

    def _render_with_insert_text(self, page: fitz.Page, item: Dict, translated: str):
        """
        insert_htmlbox başarısız olursa fallback.
        """
        rect = fitz.Rect(item['bbox'])

        # Basit font
        font_name = "helv"
        font_size = item['font_size']

        # Metni satırlara böl
        lines = self._simple_wrap(translated, rect.width, font_size)

        # Satırları yaz
        y_pos = rect.y0 + font_size
        line_height = font_size * 1.2

        for line in lines:
            if y_pos + font_size > rect.y1:
                break

            point = fitz.Point(rect.x0, y_pos)
            page.insert_text(
                point,
                line,
                fontname=font_name,
                fontsize=font_size,
                color=item['color']
            )
            y_pos += line_height

    def _simple_wrap(self, text: str, max_width: float, font_size: float) -> List[str]:
        """
        Basit word wrap.
        """
        avg_char_width = font_size * 0.6
        chars_per_line = int(max_width / avg_char_width)

        if chars_per_line < 10:
            chars_per_line = 10

        lines = []
        current_line = ""

        words = text.split(' ')

        for word in words:
            test_line = current_line + " " + word if current_line else word

            if len(test_line) <= chars_per_line:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        return lines

    def _get_bg_color(self, page: fitz.Page, rect: fitz.Rect) -> Tuple[float, float, float]:
        """Arka plan rengini al"""
        try:
            # Düşük çözünürlükte pixmap al
            sample_rect = fitz.Rect(rect.x0 + 0.5, rect.y0 + 0.5, rect.x1 - 0.5, rect.y1 - 0.5)
            clip = sample_rect & page.rect

            if clip.is_empty:
                return (1, 1, 1)

            pix = page.get_pixmap(clip=clip, colorspace=fitz.csRGB, matrix=fitz.Matrix(0.1, 0.1))

            if pix.width < 1 or pix.height < 1:
                return (1, 1, 1)

            # Ortadaki pikseli al
            try:
                c = pix.pixel(pix.width // 2, pix.height // 2)
                return (c[0] / 255, c[1] / 255, c[2] / 255)
            except:
                return (1, 1, 1)

        except:
            return (1, 1, 1)

    def _is_number_or_symbol(self, text: str) -> bool:
        """Sadece rakam/sembol kontrolü"""
        cleaned = text.replace(" ", "").replace(".", "").replace(",", "").replace("-", "")
        cleaned = cleaned.replace("€", "").replace("$", "").replace("%", "")
        return cleaned.isdigit() or len(cleaned) == 0


class InPlaceTranslator:
    """
    In-place PDF translator using search and replace
    Basit PDF'ler için alternatif yaklaşım
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

                if self._is_number_or_symbol(original_text):
                    continue

                try:
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
                        page.add_redact_annot(inst, fill=(1, 1, 1))

                    page.apply_redactions()

                    if instances:
                        rect = instances[0]
                        fit_size = min(10, rect.height * 0.8)

                        page.insert_textbox(
                            rect,
                            result.text,
                            fontsize=fit_size,
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

    def _is_number_or_symbol(self, text: str) -> bool:
        cleaned = text.replace(" ", "").replace(".", "").replace(",", "").replace("-", "")
        cleaned = cleaned.replace("€", "").replace("$", "").replace("%", "")
        return cleaned.isdigit() or len(cleaned) == 0


def create_span_translator(method: str = "span"):
    """
    Create translator instance

    Args:
        method: "span" (default) or "inplace"
    """
    if method == "inplace":
        return InPlaceTranslator()
    return SpanBasedTranslator()
