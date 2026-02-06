# -*- coding: utf-8 -*-
"""
Font Manager - Türkçe Font Yönetimi
ReportLab ile Türkçe karakter destekli PDF oluşturma
"""

import os

from config import FONTS, DEFAULT_FONT, DEFAULT_FONT_STYLE


class FontManager:
    """Türkçe font yönetimi ve PDF embedding"""

    _fonts_registered = False
    _font_cache = {}
    _fallback_mode = True  # ReportLab yoksa fallback modu

    @classmethod
    def register_fonts(cls):
        """ReportLab'e Türkçe fontları kaydet"""
        if cls._fonts_registered:
            return True

        # ReportLab modülünü kontrol et
        try:
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont

            # Font dosyalarını kontrol et ve kaydet
            for font_family, styles in FONTS.items():
                for style, font_path in styles.items():
                    # Birden fazla olası yolu kontrol et
                    from config import FONT_DIR, ROOT_FONT_DIR, BASE_DIR
                    possible_paths = [
                        font_path,
                        os.path.join(FONT_DIR, os.path.basename(font_path)),
                        os.path.join(ROOT_FONT_DIR, os.path.basename(font_path)),
                        os.path.join(BASE_DIR, "fonts", os.path.basename(font_path)),
                        os.path.join(os.path.dirname(BASE_DIR), "fonts", os.path.basename(font_path))
                    ]
                    
                    real_path = None
                    for p in possible_paths:
                        if os.path.exists(p):
                            real_path = p
                            break
                            
                    if real_path:
                        try:
                            font_name = f"{font_family}-{style}"
                            pdfmetrics.registerFont(TTFont(font_name, real_path))
                            cls._font_cache[font_name] = real_path
                        except Exception as e:
                            print(f"Error registering font {font_family}-{style}: {e}")
                    else:
                        pass # Font bulunamadı

            cls._fonts_registered = True
            cls._fallback_mode = False
            return True

        except ImportError:
            # ReportLab yoksa sessizce fallback moduna geç
            cls._fallback_mode = True
            return True

    @classmethod
    def get_font_name(cls, font_family=None, style="regular"):
        """
        Font adı döndür
        Fallback modunda Helvetica döndürür
        """
        if font_family is None:
            font_family = DEFAULT_FONT

        # Fallback modunda
        if cls._fallback_mode:
            return "Helvetica"

        font_name = f"{font_family}-{style}"

        # Font kayıtlı mı kontrol et
        if font_name in cls._font_cache:
            return font_name

        # Alternatif fontları dene
        if style == "bold_italic":
            alternatives = ["bold", "regular"]
        elif style == "italic":
            alternatives = ["regular"]
        elif style == "bold":
            alternatives = ["regular"]
        else:
            alternatives = []

        for alt_style in alternatives:
            alt_name = f"{font_family}-{alt_style}"
            if alt_name in cls._font_cache:
                return alt_name

        # Son çare: varsayılan font
        default_name = f"{DEFAULT_FONT}-{DEFAULT_FONT_STYLE}"
        if default_name in cls._font_cache:
            return default_name

        # Hiçbir font yoksa, varsayılan ReportLab fontu
        return "Helvetica"

    @classmethod
    def get_registered_fonts(cls):
        """Kayıtlı font listesini döndür"""
        if cls._fallback_mode:
            return ["Helvetica (Fallback Mode)"]
        return list(cls._font_cache.keys())

    @classmethod
    def is_turkish_supported(cls):
        """Türkçe font desteği var mı kontrol et"""
        if cls._fallback_mode:
            return False  # Fallback modunda Türkçe desteği yok
        return len(cls._font_cache) > 0

    @classmethod
    def get_font_for_text(cls, text, font_family=None, style="regular"):
        """
        Metin için uygun font seç
        Fallback modunda Helvetica döndürür
        """
        return cls.get_font_name(font_family, style)


class TextStyles:
    """Metin stilleri ve hizalamalar"""

    ALIGNMENTS = {
        "left": 0,  # TA_LEFT
        "center": 1,  # TA_CENTER
        "right": 2,  # TA_RIGHT
        "justify": 3  # TA_JUSTIFY
    }

    @staticmethod
    def get_alignment(align_str):
        """Hizalama değerini döndür"""
        return TextStyles.ALIGNMENTS.get(align_str.lower(), 0)

    @staticmethod
    def get_font_size_from_span(span, default=10):
        """
        Span bilgilerinden font boyutu çıkar
        """
        try:
            size = span.get("size", default)
            # Çok küçük veya çok büyük değerleri düzelt
            if size < 6:
                return 6
            if size > 72:
                return 72
            return size
        except:
            return default


# Fontları başlat
FontManager.register_fonts()
