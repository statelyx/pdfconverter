# -*- coding: utf-8 -*-
"""
Extension: HTML to PDF Converter
Kaynak: https://github.com/xhtml2pdf/xhtml2pdf
Mevcut sisteme DOKUNMADAN çalışır
HTML'i PDF'e dönüştürür
"""

import io
import os
from typing import Dict, Optional, List

try:
    from xhtml2pdf import pisa
    from reportlab.lib.units import inch
    from reportlab.lib.pagesizes import letter, A4
    XHTML2PDF_AVAILABLE = True
except ImportError:
    XHTML2PDF_AVAILABLE = False


class HTMLToPDFConverter:
    """
    HTML'den PDF'e dönüştürücü
    xhtml2pdf wrapper'ı
    """

    __version__ = "1.0.0"

    def __init__(self, config: Optional[Dict] = None):
        """
        HTML to PDF converter başlat

        Args:
            config: Yapılandırma
                - page_size: Sayfa boyutu (letter, a4)
                - margin: Kenar boşlukları
                - encoding: Karakter kodlaması
                - links_visible: Linkler görünür mü
        """
        if not XHTML2PDF_AVAILABLE:
            raise ImportError("xhtml2pdf kurulu değil. pip install xhtml2pdf")

        self.config = config or {}
        self.page_size = self.config.get("page_size", "a4").lower()
        self.margin = self.config.get("margin", 0.75)  # inch
        self.encoding = self.config.get("encoding", "UTF-8")

    def convert(self, html: str, output_path: str = None) -> bytes:
        """
        HTML'i PDF'e dönüştür

        Args:
            html: HTML içeriği
            output_path: Çıktı dosya yolu (opsiyonel)

        Returns:
            bytes: PDF bayt verisi
        """
        # Sayfa boyutunu ayarla
        pagesize = A4 if self.page_size == "a4" else letter

        # Çıktı buffer'ı
        output = io.BytesIO()

        # PDF oluşturma bağlamı
        context = pisa.CreatePDF(
            output,
            err_enc=self.encoding,
            page_size=pagesize
        )

        # Kenar boşlukları
        margin = self.margin * inch

        # Meta ayarları
        meta = context.meta
        meta.set("margin-top", margin)
        meta.set("margin-bottom", margin)
        meta.set("margin-left", margin)
        meta.set("margin-right", margin)

        # HTML'den PDF'e
        pisa.pisaDocument(html, context, encoding=self.encoding)

        # PDF'i al
        pdf_bytes = output.getvalue()
        output.close()

        # Dosyaya yaz
        if output_path:
            with open(output_path, "wb") as f:
                f.write(pdf_bytes)

        return pdf_bytes

    def convert_with_template(self, title: str, content: str,
                             output_path: str = None) -> bytes:
        """
        HTML'i şablon ile PDF'e dönüştür

        Args:
            title: Belge başlığı
            content: HTML içeriği
            output_path: Çıktı dosya yolu

        Returns:
            bytes: PDF bayt verisi
        """
        # HTML şablonu
        html_template = f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="{self.encoding}">
    <title>{title}</title>
    <style>
        body {{
            font-family: 'DejaVu Sans', Arial, sans-serif;
            margin: {self.margin}in;
            line-height: 1.6;
        }}
        h1 {{
            color: #333;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }}
        p {{
            margin-bottom: 12px;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
        }}
        table th, table td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}
        table th {{
            background-color: #f2f2f2;
        }}
        .page-break {{
            page-break-after: always;
        }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    {content}
</body>
</html>"""

        return self.convert(html_template, output_path)

    def convert_url(self, url: str, output_path: str = None) -> bytes:
        """
        URL'den HTML çekip PDF'e dönüştür

        Args:
            url: HTML URL'si
            output_path: Çıktı dosya yolu

        Returns:
            bytes: PDF bayt verisi
        """
        import requests

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            html = response.text.decode(self.encoding)
            return self.convert(html, output_path)
        except Exception as e:
            raise ValueError(f"URL'den HTML alınamadı: {e}")

    def convert_multiple(self, html_list: List[str],
                        output_path: str = None) -> bytes:
        """
        Birden fazla HTML'i tek PDF'e dönüştür

        Args:
            html_list: HTML içerikleri listesi
            output_path: Çıktı dosya yolu

        Returns:
            bytes: PDF bayt verisi
        """
        # Tüm HTML'leri birleştir
        combined_html = []

        for i, html in enumerate(html_list):
            if i > 0:
                combined_html.append('<div class="page-break"></div>')
            combined_html.append(html)

        full_html = """<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>Combined Document</title>
    <style>
        body { font-family: Arial, sans-serif; }
        .page-break { page-break-after: always; }
    </style>
</head>
<body>
""" + "\n".join(combined_html) + """
</body>
</html>"""

        return self.convert(full_html, output_path)


class AdvancedHTMLToPDFConverter(HTMLToPDFConverter):
    """
    Gelişmiş HTML to PDF converter
    Daha fazla özellik
    """

    def __init__(self, config=None):
        super().__init__(config)

    def convert_with_header_footer(self, content: str, header: str = "",
                                   footer: str = "", output_path: str = None) -> bytes:
        """
        Header ve footer ile PDF oluştur

        Args:
            content: Ana içerik
            header: Header HTML
            footer: Footer HTML
            output_path: Çıktı dosya yolu

        Returns:
            bytes: PDF bayt verisi
        """
        html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <style>
        @page {{
            size: {self.page_size};
            margin: {self.margin}in;
            @top-center {{ content: "{header}"; }}
            @bottom-center {{ content: "{footer}"; }}
        }}
        body {{ font-family: Arial, sans-serif; }}
    </style>
</head>
<body>
    {content}
</body>
</html>"""

        return self.convert(html, output_path)

    def convert_with_toc(self, sections: List[Dict],
                        output_path: str = None) -> bytes:
        """
        İçindekiler ile PDF oluştur

        Args:
            sections: [{title: str, content: str}] formatında bölüm listesi
            output_path: Çıktı dosya yolu

        Returns:
            bytes: PDF bayt verisi
        """
        # İçindekiler oluştur
        toc_html = "<h1>İçindekiler</h1><ul>"
        for i, section in enumerate(sections):
            toc_html += f'<li><a href="#section{i}">{section["title"]}</a></li>'
        toc_html += "</ul>"

        # Bölümler
        sections_html = ""
        for i, section in enumerate(sections):
            sections_html += f'<h2 id="section{i}">{section["title"]}</h2>'
            sections_html += section["content"]
            sections_html += '<div class="page-break"></div>'

        html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>Document with TOC</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 1in; }}
        h1 {{ color: #333; border-bottom: 2px solid #667eea; }}
        h2 {{ color: #555; margin-top: 30px; }}
        .page-break {{ page-break-after: always; }}
        a {{ text-decoration: none; color: #667eea; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    {toc_html}
    {sections_html}
</body>
</html>"""

        return self.convert(html, output_path)


# Kolay kullanım fonksiyonları
def html_to_pdf(html: str, config: Dict = None) -> bytes:
    """
    HTML'i PDF'e dönüştür (kolay fonksiyon)

    Args:
        html: HTML içeriği
        config: Yapılandırma

    Returns:
        bytes: PDF bayt verisi
    """
    converter = HTMLToPDFConverter(config)
    return converter.convert(html)


def html_to_pdf_with_template(title: str, content: str,
                             config: Dict = None) -> bytes:
    """
    HTML'i şablon ile PDF'e dönüştür (kolay fonksiyon)

    Args:
        title: Belge başlığı
        content: HTML içeriği
        config: Yapılandırma

    Returns:
        bytes: PDF bayt verisi
    """
    converter = HTMLToPDFConverter(config)
    return converter.convert_with_template(title, content)
