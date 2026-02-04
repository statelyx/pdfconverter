# -*- coding: utf-8 -*-
"""
Extension: Markdown to PDF Converter
Kaynak: https://github.com/alanshaw/markdown-pdf (esinlenilmiş)
Mevcut systeme DOKUNMADAN çalışır
Markdown'ı PDF'e dönüştürür
"""

import io
from typing import Dict, Optional, List

try:
    import markdown
    from xhtml2pdf import pisa
    from reportlab.lib.pagesizes import letter, A4
    MARKDOWN_PDF_AVAILABLE = True
except ImportError:
    MARKDOWN_PDF_AVAILABLE = False


class MarkdownToPDFConverter:
    """
    Markdown'dan PDF'e dönüştürücü
    Markdown → HTML → PDF
    """

    __version__ = "1.0.0"

    def __init__(self, config: Optional[Dict] = None):
        """
        Markdown to PDF converter başlat

        Args:
            config: Yapılandırma
                - page_size: Sayfa boyutu (letter, a4)
                - margin: Kenar boşlukları
                - extensions: Markdown extension'ları
                - theme: Tema (default, github, minimalist)
        """
        if not MARKDOWN_PDF_AVAILABLE:
            raise ImportError("Gerekli kütüphaneler kurulu değil. pip install markdown xhtml2pdf")

        self.config = config or {}
        self.page_size = self.config.get("page_size", "a4").lower()
        self.margin = self.config.get("margin", 0.75)
        self.theme = self.config.get("theme", "default")

        # Markdown extension'ları
        default_extensions = [
            "extra",
            "codehilite",
            "tables",
            "toc",
            "fenced_code",
            "nl2br",
            "sane_lists"
        ]
        self.extensions = self.config.get("extensions", default_extensions)

        # Markdown'ı başlat
        self.md = markdown.Markdown(extensions=self.extensions)

    def convert(self, markdown_text: str, output_path: str = None) -> bytes:
        """
        Markdown'ı PDF'e dönüştür

        Args:
            markdown_text: Markdown içeriği
            output_path: Çıktı dosya yolu (opsiyonel)

        Returns:
            bytes: PDF bayt verisi
        """
        # Markdown'ı HTML'e çevir
        html = self._markdown_to_html(markdown_text)

        # HTML'i PDF'e çevir
        return self._html_to_pdf(html, output_path)

    def _markdown_to_html(self, markdown_text: str) -> str:
        """Markdown'ı HTML'e çevir"""
        # Markdown'ı sıfırla ve çevir
        self.md.reset()
        html = self.md.convert(markdown_text)

        # Temayı uygula
        styled_html = self._apply_theme(html)

        return styled_html

    def _apply_theme(self, html: str) -> str:
        """HTML'e tema uygula"""
        themes = {
            "default": self._default_theme(),
            "github": self._github_theme(),
            "minimalist": self._minimalist_theme()
        }

        theme_css = themes.get(self.theme, themes["default"])

        return f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>Markdown to PDF</title>
    {theme_css}
</head>
<body>
    <div class="container">
        {html}
    </div>
</body>
</html>"""

    def _default_theme(self) -> str:
        """Varsayılan tema CSS"""
        return """<style>
        body {
            font-family: 'DejaVu Sans', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            margin: 0;
            padding: 0;
        }
        .container {
            max-width: 800px;
            margin: 2cm auto;
            padding: 20px;
        }
        h1, h2, h3, h4, h5, h6 {
            color: #333;
            margin-top: 24px;
            margin-bottom: 16px;
            font-weight: 600;
        }
        h1 { font-size: 28px; border-bottom: 2px solid #667eea; padding-bottom: 10px; }
        h2 { font-size: 24px; border-bottom: 1px solid #ddd; padding-bottom: 8px; }
        h3 { font-size: 20px; }
        p { margin-bottom: 16px; }
        code {
            background-color: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 0.9em;
        }
        pre {
            background-color: #f4f4f4;
            padding: 16px;
            border-radius: 5px;
            overflow-x: auto;
        }
        pre code {
            background-color: transparent;
            padding: 0;
        }
        blockquote {
            border-left: 4px solid #667eea;
            padding-left: 16px;
            margin-left: 0;
            color: #666;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
        }
        table th, table td {
            border: 1px solid #ddd;
            padding: 8px 12px;
            text-align: left;
        }
        table th {
            background-color: #f2f2f2;
            font-weight: 600;
        }
        ul, ol { margin-bottom: 16px; padding-left: 30px; }
        a { color: #667eea; text-decoration: none; }
        a:hover { text-decoration: underline; }
        img { max-width: 100%; height: auto; }
        .page-break { page-break-after: always; }
    </style>"""

    def _github_theme(self) -> str:
        """GitHub benzeri tema"""
        return """<style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            line-height: 1.6;
            color: #24292f;
            background: #ffffff;
        }
        .container { max-width: 900px; margin: 0 auto; padding: 40px 20px; }
        h1, h2 { border-bottom: 1px solid #d0d7de; padding-bottom: 0.3em; }
        h1 { font-size: 32px; font-weight: 600; }
        h2 { font-size: 24px; font-weight: 600; margin-top: 30px; }
        h3 { font-size: 20px; font-weight: 600; }
        code {
            background: rgba(175,184,193,0.2);
            padding: 0.2em 0.4em;
            border-radius: 6px;
            font-size: 85%;
            font-family: ui-monospace, SFMono-Regular, SF Mono, Menlo, monospace;
        }
        pre {
            background: #f6f8fa;
            padding: 16px;
            border-radius: 6px;
            overflow: auto;
        }
        pre code { background: transparent; padding: 0; }
        blockquote {
            border-left: 4px solid #d0d7de;
            padding: 0 16px;
            color: #57606a;
            margin: 0 0 16px 0;
        }
        table { border-collapse: collapse; width: 100%; }
        table th, table td { border: 1px solid #d0d7de; padding: 6px 13px; }
        table th { background: #f6f8fa; }
        a { color: #0969da; text-decoration: none; }
    </style>"""

    def _minimalist_theme(self) -> str:
        """Minimalist tema"""
        return """<style>
        body {
            font-family: 'Georgia', serif;
            line-height: 1.8;
            color: #222;
        }
        .container { max-width: 700px; margin: 3cm auto; }
        h1, h2, h3 { font-weight: normal; letter-spacing: 0.5px; }
        h1 { font-size: 26px; border-bottom: 1px solid #ccc; }
        h2 { font-size: 22px; margin-top: 40px; }
        p { margin-bottom: 20px; text-align: justify; }
        code { font-family: 'Consolas', monospace; background: #eee; padding: 2px 6px; }
        pre { background: #f5f5f5; padding: 20px; border-radius: 3px; }
        blockquote { font-style: italic; color: #666; border-left: 3px solid #ccc; padding-left: 20px; }
        table { border-collapse: collapse; margin: 30px 0; }
        table th, table td { border: 1px solid #ccc; padding: 10px; }
    </style>"""

    def _html_to_pdf(self, html: str, output_path: str = None) -> bytes:
        """HTML'i PDF'e çevir"""
        output = io.BytesIO()

        pagesize = A4 if self.page_size == "a4" else letter

        pisa.CreatePDF(
            output,
            pisa.PMLDocument(html, encoding="UTF-8", pagesize=pagesize)
        )

        pdf_bytes = output.getvalue()
        output.close()

        if output_path:
            with open(output_path, "wb") as f:
                f.write(pdf_bytes)

        return pdf_bytes

    def convert_with_cover(self, markdown_text: str, title: str,
                          author: str = "", output_path: str = None) -> bytes:
        """
        Kapak sayfası ile PDF oluştur

        Args:
            markdown_text: Markdown içeriği
            title: Belge başlığı
            author: Yazar
            output_path: Çıktı dosya yolu

        Returns:
            bytes: PDF bayt verisi
        """
        # Kapak sayfası ekle
        cover_html = f"""
        <div style="page-break-after: always; text-align: center; padding-top: 200px;">
            <h1 style="font-size: 36px; color: #333;">{title}</h1>
            <p style="font-size: 18px; color: #666;">{author}</p>
            <p style="color: #999;">PDF Komuta Merkezi</p>
        </div>
        """

        # Markdown'ı HTML'e çevir
        self.md.reset()
        content_html = self.md.convert(markdown_text)
        full_html = self._apply_theme(cover_html + f'<div class="page-break"></div>' + content_html)

        return self._html_to_pdf(full_html, output_path)

    def convert_multiple(self, markdown_files: List[str],
                        output_path: str = None) -> bytes:
        """
        Birden fazla Markdown'ı tek PDF'e dönüştür

        Args:
            markdown_files: Markdown içerikleri listesi
            output_path: Çıktı dosya yolu

        Returns:
            bytes: PDF bayt verisi
        """
        combined_html = ""

        for i, md in enumerate(markdown_files):
            self.md.reset()
            html = self.md.convert(md)

            if i > 0:
                combined_html += '<div class="page-break"></div>'

            combined_html += html

        full_html = self._apply_theme(combined_html)
        return self._html_to_pdf(full_html, output_path)


class SimpleMarkdownToPDF(MarkdownToPDFConverter):
    """
    Basit Markdown to PDF converter
    Daha hızlı, daha az özellik
    """

    def __init__(self, config=None):
        config = config or {}
        config["extensions"] = ["extra", "nl2br"]  # Sadece temel extension'lar
        super().__init__(config)


# Kolay kullanım fonksiyonları
def markdown_to_pdf(markdown_text: str, config: Dict = None) -> bytes:
    """
    Markdown'ı PDF'e dönüştür (kolay fonksiyon)

    Args:
        markdown_text: Markdown içeriği
        config: Yapılandırma

    Returns:
        bytes: PDF bayt verisi
    """
    converter = MarkdownToPDFConverter(config)
    return converter.convert(markdown_text)


def markdown_to_pdf_with_cover(markdown_text: str, title: str,
                              author: str = "", config: Dict = None) -> bytes:
    """
    Markdown'ı kapakla PDF'e dönüştür (kolay fonksiyon)

    Args:
        markdown_text: Markdown içeriği
        title: Belge başlığı
        author: Yazar
        config: Yapılandırma

    Returns:
        bytes: PDF bayt verisi
    """
    converter = MarkdownToPDFConverter(config)
    return converter.convert_with_cover(markdown_text, title, author)
