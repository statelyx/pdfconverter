# -*- coding: utf-8 -*-
"""
PDF Komuta Merkezi - Backend v5
Profesyonel PDF Isleme ve Ceviri Sistemi
Turkce font destekli, gorsel bütünlüğü koruyan
"""

import io
import os
import sys
import traceback
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

# Modülleri import et
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    LANGUAGE_NAMES,
    MAX_FILE_SIZE,
    PDF_DPI,
    AI_MODEL
)

# PyMuPDF
import fitz

# Core modüller
from core.font_manager import FontManager
from core.pdf_reader import PDFReader

# Converters
from converters.pdf_to_pdf import create_converter
# pdf_to_word LAZY IMPORT - opencv bağımlılığı nedeniyle boot sırasında import edilmiyor
# from converters.pdf_to_word import convert_pdf_to_word
from converters.pdf_to_excel import convert_pdf_to_excel
from converters.pdf_to_image import PDFToImageConverter, PDFPreviewGenerator

# Translators
from translators.gemini_translator import get_translator

# Flask uygulaması
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# Maksimum dosya boyutu
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Fontları yükle
FontManager.register_fonts()

print("=" * 60)
print("  PDF KOMUTA MERKEZI - BACKEND v5")
print("  Profesyonel PDF Isleme ve Ceviri Sistemi")
print("=" * 60)
print(f"  AI Model: {AI_MODEL}")
print(f"  PDF DPI: {PDF_DPI}")
print(f"  Turkce Font: {'✅ Hazir' if FontManager.is_turkish_supported() else '❌ Yok'}")
print(f"  Kayitli Fontlar: {FontManager.get_registered_fonts()}")
print("=" * 60)


# ============================================================================
# YARDIMCI FONKSIYONLAR
# ============================================================================

def json_response(data, status=200):
    """JSON yanıtı döndür"""
    return jsonify(data), status


def error_response(message, status=500):
    """Hata yanıtı döndür"""
    return jsonify({"error": message}), status


def handle_request(endpoint_func):
    """
    Endpoint'i güvenli şekilde çalıştır
    Hataları yakala ve uygun yanıt döndür
    """
    try:
        return endpoint_func()
    except ValueError as e:
        return error_response(str(e), 400)
    except Exception as e:
        print(f"❌ Hata: {e}")
        traceback.print_exc()
        return error_response(f"Islem sirasinda hata olustu: {str(e)}", 500)


# ============================================================================
# SYSTEM ENDPOINTS
# ============================================================================

@app.route('/health', methods=['GET'])
def health():
    """Saglik kontrolü"""
    return jsonify({
        'status': 'ok',
        'version': 'v5',
        'features': {
            'pdf_to_pdf': True,
            'pdf_to_word': True,
            'pdf_to_excel': True,
            'pdf_to_image': True,
            'turkish_font': FontManager.is_turkish_supported()
        },
        'fonts': FontManager.get_registered_fonts()
    })


@app.route('/languages', methods=['GET'])
def get_languages():
    """Desteklenen dilleri listele"""
    return jsonify(LANGUAGE_NAMES)


# ============================================================================
# PDF TO PDF (CEVIRI) - YENI PROFESYONEL VERSION
# ============================================================================

@app.route('/translate', methods=['POST'])
def translate_pdf():
    """
    PDF'i PDF'e çevir - Profesyonel Version
    Türkce font ile, gorsel bütünlüğü koruyarak
    """
    def _process():
        if 'file' not in request.files:
            raise ValueError("Dosya bulunamadi")

        file = request.files['file']
        source_lang = request.form.get('source', 'auto')
        target_lang = request.form.get('target', 'tr')

        print(f"📄 PDF Çeviri: {file.filename}")
        print(f"🌐 {source_lang} → {target_lang}")

        # PDF'i oku
        pdf_bytes = file.read()

        # Converter oluştur
        converter = create_converter("hybrid")

        # İlerleme callback'i
        def progress(page, total):
            print(f"✅ Sayfa {page}/{total} tamamlandı")

        # Çevir
        result = converter.convert(
            pdf_bytes,
            source_lang=source_lang,
            target_lang=target_lang,
            progress_callback=progress
        )

        output_filename = file.filename.replace('.pdf', f'_ceviri_{target_lang}.pdf')
        print(f"✅ Tamamlandı: {output_filename}")

        return send_file(
            io.BytesIO(result),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=output_filename
        )

    return handle_request(_process)


@app.route('/translate-html', methods=['POST'])
def translate_html():
    """
    PDF'ten HTML'e çeviri
    Türkçe karakter destekli
    """
    def _process():
        if 'file' not in request.files:
            raise ValueError("Dosya bulunamadi")

        file = request.files['file']
        source_lang = request.form.get('source', 'auto')
        target_lang = request.form.get('target', 'tr')

        pdf_bytes = file.read()
        translator = get_translator()

        with PDFReader(pdf_bytes=pdf_bytes) as reader:
            html = '''<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>PDF Çeviri</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 40px; background: #f5f5f5; }
        .header { text-align: center; padding: 30px; background: linear-gradient(135deg, #667eea, #764ba2); color: white; border-radius: 15px; margin-bottom: 30px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
        .page { background: white; padding: 40px; margin-bottom: 30px; border-radius: 15px; box-shadow: 0 2px 15px rgba(0,0,0,0.08); }
        .page-title { color: #667eea; border-bottom: 2px solid #667eea; padding-bottom: 15px; margin-bottom: 20px; font-size: 18px; }
        .content { line-height: 2; color: #333; }
        .line { margin: 10px 0; padding: 5px 0; }
    </style>
</head>
<body>
    <div class="header"><h1>📄 PDF Komuta Merkezi</h1></div>
'''

            for page_num in range(len(reader)):
                page = reader.get_page(page_num)
                text = page.get_text("text")

                if text.strip():
                    # Çeviri yap
                    result = translator.translate(text, target_lang, source_lang)
                    translated = result.text if result.success else text

                    html += f'<div class="page"><h2 class="page-title">📑 Sayfa {page_num + 1}</h2><div class="content">'

                    for line in translated.split('\n'):
                        if line.strip():
                            html += f'<div class="line">{line}</div>'

                    html += '</div></div>'

                print(f"✅ Sayfa {page_num + 1}")

            reader.close()
            html += '</body></html>'

        return send_file(
            io.BytesIO(html.encode('utf-8')),
            mimetype='text/html',
            as_attachment=True,
            download_name=file.filename.replace('.pdf', f'_ceviri_{target_lang}.html')
        )

    return handle_request(_process)


# ============================================================================
# PDF TO WORD
# ============================================================================

@app.route('/pdf-to-word', methods=['POST'])
def pdf_to_word():
    """
    PDF'ten Word'e dönüştürme
    Görselleri koruyarak
    """
    def _process():
        if 'file' not in request.files:
            raise ValueError("Dosya bulunamadi")

        file = request.files['file']
        translate = request.form.get('translate', 'false').lower() == 'true'
        source_lang = request.form.get('source', 'auto')
        target_lang = request.form.get('target', 'tr')

        print(f"📄 PDF → Word: {file.filename}")
        if translate:
            print(f"🌐 Çeviri aktif: {source_lang} → {target_lang}")

        pdf_bytes = file.read()

        # LAZY IMPORT - opencv bağımlılığı boot sırasında yüklenmesin
        from converters.pdf_to_word import convert_pdf_to_word
        
        result = convert_pdf_to_word(
            pdf_bytes,
            translate=translate,
            source_lang=source_lang,
            target_lang=target_lang
        )

        output_filename = file.filename.replace('.pdf', '.docx')
        print(f"✅ Tamamlandı: {output_filename}")

        return send_file(
            io.BytesIO(result),
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            as_attachment=True,
            download_name=output_filename
        )

    return handle_request(_process)


# ============================================================================
# PDF TO EXCEL
# ============================================================================

@app.route('/pdf-to-excel', methods=['POST'])
def pdf_to_excel():
    """
    PDF'ten Excel'e dönüştürme
    Tabloları koruyarak
    """
    def _process():
        if 'file' not in request.files:
            raise ValueError("Dosya bulunamadi")

        file = request.files['file']
        translate = request.form.get('translate', 'false').lower() == 'true'
        source_lang = request.form.get('source', 'auto')
        target_lang = request.form.get('target', 'tr')

        print(f"📊 PDF → Excel: {file.filename}")
        if translate:
            print(f"🌐 Çeviri aktif: {source_lang} → {target_lang}")

        pdf_bytes = file.read()

        result = convert_pdf_to_excel(
            pdf_bytes,
            translate=translate,
            source_lang=source_lang,
            target_lang=target_lang
        )

        output_filename = file.filename.replace('.pdf', '.xlsx')
        print(f"✅ Tamamlandı: {output_filename}")

        return send_file(
            io.BytesIO(result),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=output_filename
        )

    return handle_request(_process)


# ============================================================================
# PDF TO IMAGE
# ============================================================================

@app.route('/pdf-to-image', methods=['POST'])
def pdf_to_image():
    """
    PDF'ten gösele dönüştürme
    Yüksek kaliteli PNG/JPG
    """
    def _process():
        if 'file' not in request.files:
            raise ValueError("Dosya bulunamadi")

        file = request.files['file']
        page_num = int(request.form.get('page', 0))
        format_type = request.form.get('format', 'png').lower()
        dpi = int(request.form.get('dpi', PDF_DPI))

        print(f"🖼️ PDF → Resim: {file.filename}")
        print(f"📄 Sayfa: {page_num + 1}, Format: {format_type}, DPI: {dpi}")

        pdf_bytes = file.read()

        with PDFReader(pdf_bytes=pdf_bytes) as reader:
            if page_num >= len(reader):
                page_num = 0

            pixmap = reader.get_page_pixmap(page_num, dpi=dpi)
            img_bytes = pixmap.tobytes(format_type)

        ext = format_type if format_type in ['png', 'jpg', 'jpeg'] else 'png'
        output_filename = file.filename.replace('.pdf', f'_page{page_num+1}.{ext}')

        print(f"✅ Tamamlandı: {output_filename}")

        return send_file(
            io.BytesIO(img_bytes),
            mimetype=f'image/{ext}',
            as_attachment=True,
            download_name=output_filename
        )

    return handle_request(_process)


@app.route('/pdf-to-images', methods=['POST'])
def pdf_to_images():
    """
    PDF'in tüm sayfalarını gösele dönüştürme (ZIP)
    """
    def _process():
        if 'file' not in request.files:
            raise ValueError("Dosya bulunamadi")

        file = request.files['file']
        format_type = request.form.get('format', 'png').lower()
        dpi = int(request.form.get('dpi', PDF_DPI))

        print(f"🖼️ PDF → Tüm Resimler: {file.filename}")

        pdf_bytes = file.read()

        converter = PDFToImageConverter(dpi=dpi)
        zip_bytes = converter.convert_to_zip(pdf_bytes, format=format_type)

        output_filename = file.filename.replace('.pdf', '_images.zip')

        print(f"✅ Tamamlandı: {output_filename}")

        return send_file(
            io.BytesIO(zip_bytes),
            mimetype='application/zip',
            as_attachment=True,
            download_name=output_filename
        )

    return handle_request(_process)


# ============================================================================
# PDF PREVIEW
# ============================================================================

@app.route('/preview', methods=['POST'])
def preview_pdf():
    """
    PDF önizleme görselleri oluştur
    """
    def _process():
        if 'file' not in request.files:
            raise ValueError("Dosya bulunamadi")

        file = request.files['file']

        pdf_bytes = file.read()

        generator = PDFPreviewGenerator(preview_dpi=72)
        grid_bytes = generator.generate_preview_grid(pdf_bytes, cols=5, max_pages=10)

        return send_file(
            io.BytesIO(grid_bytes),
            mimetype='image/png',
            as_attachment=False
        )

    return handle_request(_process)


# ============================================================================
# PDF COMPRESS
# ============================================================================

@app.route('/compress', methods=['POST'])
def compress_pdf():
    """
    PDF sıkıştırma
    """
    def _process():
        if 'file' not in request.files:
            raise ValueError("Dosya bulunamadi")

        file = request.files['file']
        pdf_bytes = file.read()

        print(f"🗜️ PDF Sıkıştırma: {file.filename}")

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        output = doc.tobytes(garbage=4, deflate=True, clean=True)
        doc.close()

        output_filename = file.filename.replace('.pdf', '_compressed.pdf')
        original_size = len(pdf_bytes)
        compressed_size = len(output)
        ratio = (1 - compressed_size / original_size) * 100

        print(f"✅ Tamamlandı: {output_filename}")
        print(f"📊 Oran: {ratio:.1f}% küçüldü")

        return send_file(
            io.BytesIO(output),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=output_filename
        )

    return handle_request(_process)


# ============================================================================
# EXTENSION ENDPOINTS (NON-BREAKING - MEVCUT KODA DOKUNULMADI)
# ============================================================================

# Extension modüllerini import et
try:
    from extensions.markdown_converter import PDFToMarkdownConverter
    from extensions.ocr_service import TurkishOCRService
    from extensions.translation_proxy import LibreTranslateProxy
    from extensions.google_trans_scraper import SafeGoogleTranslator
    from extensions.llm_prep import PDFToLLMPreparator
    from extensions.html2pdf_ext import HTMLToPDFConverter
    from extensions.md2pdf_ext import MarkdownToPDFConverter
    from extensions.pdf_ocr_adder import TurkishPDFOCRAdder
    from extensions.batch_translator import BatchTranslator
    from extensions import get_extension_status
    EXTENSIONS_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Extension modülleri yüklenemedi: {e}")
    EXTENSIONS_AVAILABLE = False


@app.route('/extensions/status', methods=['GET'])
def extensions_status():
    """Extension durumlarını listele"""
    if EXTENSIONS_AVAILABLE:
        return jsonify({
            'available': True,
            'extensions': get_extension_status()
        })
    else:
        return jsonify({
            'available': False,
            'message': 'Extension modülleri yüklenmedi'
        })


@app.route('/extensions/health', methods=['GET'])
def extensions_health():
    """Extension sağlık kontrolü"""
    health_status = {
        'extensions': {},
        'overall': 'degraded'
    }

    if EXTENSIONS_AVAILABLE:
        try:
            # LibreTranslate kontrolü
            try:
                lt_proxy = LibreTranslateProxy()
                health_status['extensions']['libretranslate'] = lt_proxy.available
            except:
                health_status['extensions']['libretranslate'] = False

            # Tesseract kontrolü
            try:
                ocr_service = TurkishOCRService()
                health_status['extensions']['tesseract'] = ocr_service.available
            except:
                health_status['extensions']['tesseract'] = False

            # Diğer extension'lar
            health_status['extensions']['markdown'] = True
            health_status['extensions']['llm_prep'] = True
            health_status['extensions']['html2pdf'] = True
            health_status['extensions']['md2pdf'] = True

            # Genel durum
            if all(health_status['extensions'].values()):
                health_status['overall'] = 'healthy'
            elif any(health_status['extensions'].values()):
                health_status['overall'] = 'partial'

        except Exception as e:
            health_status['error'] = str(e)

    return jsonify(health_status)


@app.route('/extensions/pdf-to-markdown', methods=['POST'])
def ext_pdf_to_markdown():
    """
    Extension: PDF → Markdown
    PDF'i Markdown formatına çevirir
    """
    def _process():
        if not EXTENSIONS_AVAILABLE:
            raise ValueError("Extension modülleri yüklenmedi")

        if 'file' not in request.files:
            raise ValueError("Dosya bulunamadi")

        file = request.files['file']
        pdf_bytes = file.read()

        print(f"📝 PDF → Markdown: {file.filename}")

        converter = PDFToMarkdownConverter()
        markdown_text = converter.convert(pdf_bytes)

        output_filename = file.filename.replace('.pdf', '.md')

        return send_file(
            io.BytesIO(markdown_text.encode('utf-8')),
            mimetype='text/markdown',
            as_attachment=True,
            download_name=output_filename
        )

    return handle_request(_process)


@app.route('/extensions/pdf-ocr', methods=['POST'])
def ext_pdf_ocr():
    """
    Extension: PDF OCR
    Taranmış PDF'i metne çevirir (Tesseract + Türkçe)
    """
    def _process():
        if not EXTENSIONS_AVAILABLE:
            raise ValueError("Extension modülleri yüklenmedi")

        if 'file' not in request.files:
            raise ValueError("Dosya bulunamadi")

        file = request.files['file']
        lang = request.form.get('lang', 'tr')

        pdf_bytes = file.read()
        print(f"🔍 PDF OCR: {file.filename}, Dil: {lang}")

        ocr_service = TurkishOCRService()
        result = ocr_service.ocr_pdf(pdf_bytes, lang)

        return jsonify({
            'text': result.text,
            'confidence': result.confidence,
            'pages': result.pages,
            'language': result.language
        })

    return handle_request(_process)


@app.route('/extensions/pdf-with-ocr', methods=['POST'])
def ext_pdf_with_ocr():
    """
    Extension: PDF'e OCR ekle
    PDF'e görünmez metin katmanı ekler (OCRmyPDF)
    """
    def _process():
        if not EXTENSIONS_AVAILABLE:
            raise ValueError("Extension modülleri yüklenmedi")

        if 'file' not in request.files:
            raise ValueError("Dosya bulunamadi")

        file = request.files['file']
        lang = request.form.get('lang', 'tr')

        pdf_bytes = file.read()
        print(f"📄 PDF + OCR: {file.filename}, Dil: {lang}")

        ocr_adder = TurkishPDFOCRAdder()
        result = ocr_adder.add_ocr_to_pdf(pdf_bytes, lang)

        output_filename = file.filename.replace('.pdf', '_ocr.pdf')

        return send_file(
            io.BytesIO(result.output_pdf),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=output_filename
        )

    return handle_request(_process)


@app.route('/extensions/batch-translate', methods=['POST'])
def ext_batch_translate():
    """
    Extension: Toplu dosya çevirisi
    Birden fazla PDF dosyasını aynı anda çevirir
    """
    def _process():
        if not EXTENSIONS_AVAILABLE:
            raise ValueError("Extension modülleri yüklenmedi")

        files = request.files.getlist('files')
        if not files:
            raise ValueError("Dosya bulunamadi")

        target_lang = request.form.get('target', 'tr')
        source_lang = request.form.get('source', 'auto')
        service = request.form.get('service', 'libretranslate')

        print(f"🔄 Batch Translate: {len(files)} dosya, {source_lang} → {target_lang}")

        # Dosya bilgilerini hazırla
        file_list = []
        for file in files:
            file_list.append({
                'name': file.filename,
                'bytes': file.read()
            })

        # Çeviri yap
        config = {'service': service, 'target_lang': target_lang, 'source_lang': source_lang}
        translator = BatchTranslator(config)
        zip_bytes, zip_name = translator.translate_to_zip(file_list)

        return send_file(
            io.BytesIO(zip_bytes),
            mimetype='application/zip',
            as_attachment=True,
            download_name=zip_name
        )

    return handle_request(_process)


@app.route('/extensions/html-to-pdf', methods=['POST'])
def ext_html_to_pdf():
    """
    Extension: HTML → PDF
    HTML'i PDF'e dönüştürür
    """
    def _process():
        if not EXTENSIONS_AVAILABLE:
            raise ValueError("Extension modülleri yüklenmedi")

        # HTML içeriği al
        html_content = request.form.get('html')
        html_file = request.files.get('file')

        if html_file:
            html_content = html_file.read().decode('utf-8')
            file_name = html_file.filename
        elif html_content:
            file_name = 'document.html'
        else:
            raise ValueError("HTML içeriği bulunamadi")

        print(f"📄 HTML → PDF")

        converter = HTMLToPDFConverter()
        pdf_bytes = converter.convert(html_content)

        output_filename = file_name.replace('.html', '.pdf').replace('.htm', '.pdf')

        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=output_filename
        )

    return handle_request(_process)


@app.route('/extensions/md-to-pdf', methods=['POST'])
def ext_md_to_pdf():
    """
    Extension: Markdown → PDF
    Markdown'ı PDF'e dönüştürür
    """
    def _process():
        if not EXTENSIONS_AVAILABLE:
            raise ValueError("Extension modülleri yüklenmedi")

        # Markdown içeriği al
        md_content = request.form.get('markdown')
        md_file = request.files.get('file')
        title = request.form.get('title', 'Markdown Document')

        if md_file:
            md_content = md_file.read().decode('utf-8')
            file_name = md_file.filename
        elif md_content:
            file_name = 'document.md'
        else:
            raise ValueError("Markdown içeriği bulunamadi")

        print(f"📝 Markdown → PDF")

        converter = MarkdownToPDFConverter()
        pdf_bytes = converter.convert(md_content)

        output_filename = file_name.replace('.md', '.pdf').replace('.markdown', '.pdf')

        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=output_filename
        )

    return handle_request(_process)


@app.route('/extensions/llm-prep', methods=['POST'])
def ext_llm_prep():
    """
    Extension: LLM Prep
    PDF'i LLM input formatına hazırlar
    """
    def _process():
        if not EXTENSIONS_AVAILABLE:
            raise ValueError("Extension modülleri yüklenmedi")

        if 'file' not in request.files:
            raise ValueError("Dosya bulunamadi")

        file = request.files['file']
        format_type = request.form.get('format', 'json')  # json, markdown, rag

        pdf_bytes = file.read()
        print(f"🤖 LLM Prep: {file.filename}, Format: {format_type}")

        preparator = PDFToLLMPreparator()

        if format_type == 'json':
            result = preparator.to_json(pdf_bytes)
            mimetype = 'application/json'
            ext = '.json'
        elif format_type == 'markdown':
            result = preparator.to_markdown(pdf_bytes)
            mimetype = 'text/markdown'
            ext = '.md'
        elif format_type == 'rag':
            import json
            rag_data = preparator.to_rag_format(pdf_bytes)
            result = json.dumps(rag_data, ensure_ascii=False)
            mimetype = 'application/json'
            ext = '_rag.json'
        else:
            result = preparator.to_markdown(pdf_bytes)
            mimetype = 'text/markdown'
            ext = '.md'

        output_filename = file.filename.replace('.pdf', ext)

        return send_file(
            io.BytesIO(result.encode('utf-8')),
            mimetype=mimetype,
            as_attachment=True,
            download_name=output_filename
        )

    return handle_request(_process)


@app.route('/extensions/translate-fallback', methods=['POST'])
def ext_translate_fallback():
    """
    Extension: Çeviri Fallback
    LibreTranslate veya Google Translate ile çeviri
    """
    def _process():
        if not EXTENSIONS_AVAILABLE:
            raise ValueError("Extension modülleri yüklenmedi")

        text = request.form.get('text')
        target_lang = request.form.get('target', 'tr')
        source_lang = request.form.get('source', 'auto')
        service = request.form.get('service', 'libretranslate')

        if not text:
            raise ValueError("Metin bulunamadi")

        print(f"🌐 Fallback Translate: {service}, {source_lang} → {target_lang}")

        if service == 'google':
            translator = SafeGoogleTranslator()
            result = translator.translate(text, target_lang, source_lang)
            translated = result.text
        else:
            proxy = LibreTranslateProxy()
            result = proxy.translate(text, target_lang, source_lang)
            translated = result.text

        return jsonify({
            'original': text,
            'translated': translated,
            'source_lang': getattr(result, 'source_lang', source_lang),
            'target_lang': target_lang,
            'service': service
        })

    return handle_request(_process)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    print("\n🚀 Sunucu başlatılıyor...")
    print("📡 http://localhost:5000")
    print("\n📋 Kullanılabilir Endpoint'ler:")

    print("  Ana Endpoint'ler:")
    print("  POST /translate         - PDF → PDF (Çeviri)")
    print("  POST /translate-html    - PDF → HTML (Çeviri)")
    print("  POST /pdf-to-word      - PDF → Word")
    print("  POST /pdf-to-excel     - PDF → Excel")
    print("  POST /pdf-to-image     - PDF → Resim (tek sayfa)")
    print("  POST /pdf-to-images    - PDF → Resimler (ZIP)")
    print("  POST /preview          - PDF Önizleme")
    print("  POST /compress         - PDF Sıkıştırma")
    print("  GET  /health           - Sağlık Kontrolü")
    print("  GET  /languages        - Desteklenen Diller")

    if EXTENSIONS_AVAILABLE:
        print("\n  Extension Endpoint'ler:")
        print("  POST /extensions/pdf-to-markdown   - PDF → Markdown")
        print("  POST /extensions/pdf-ocr            - Taranmış PDF → Metin")
        print("  POST /extensions/pdf-with-ocr       - PDF'e OCR eklenmiş hali")
        print("  POST /extensions/batch-translate     - Toplu dosya çevirisi")
        print("  POST /extensions/html-to-pdf        - HTML → PDF")
        print("  POST /extensions/md-to-pdf          - Markdown → PDF")
        print("  POST /extensions/llm-prep            - PDF'i LLM için hazırla")
        print("  POST /extensions/translate-fallback   - Fallback çeviri")
        print("  GET  /extensions/status              - Extension durumları")
        print("  GET  /extensions/health             - Extension sağlık kontrolü")

    print("\n")

    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=os.environ.get('FLASK_DEBUG', 'True').lower() == 'true')
