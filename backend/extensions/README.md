# PDF Komuta Merkezi - Extension Pack
# Mevcut sisteme DOKUNMADAN çalışan eklentiler

## 📦 Extension Paketi İçeriği

| Extension | Açıklama | Durum |
|-----------|----------|-------|
| `markdown_converter.py` | PDF → Markdown dönüştürücü | ✅ |
| `ocr_service.py` | Tesseract OCR wrapper (Türkçe) | ✅ |
| `translation_proxy.py` | LibreTranslate adapter | ✅ |
| `google_trans_scraper.py` | Google Translate scraper (fallback) | ✅ |
| `llm_prep.py` | pymupdf4llm wrapper (LLM input) | ✅ |
| `html2pdf_ext.py` | HTML → PDF dönüştürücü | ✅ |
| `md2pdf_ext.py` | Markdown → PDF dönüştürücü | ✅ |
| `pdf_ocr_adder.py` | PDF'e görünmez metin ekle (OCRmyPDF) | ✅ |
| `batch_translator.py` | Toplu dosya çevirisi | ✅ |

## 🚀 Kurulum

### 1. Python Bağımlılıkları

```bash
pip install -r requirements.txt
```

### 2. Tesseract OCR (Windows)

```bash
# 1. İndir: https://github.com/UB-Mannheim/tesseract/wiki
# 2. Yükle: C:\Program Files\Tesseract-OCR\
# 3. PATH'e ekle
```

### 3. Türkçe OCR Data

```bash
# İndir: https://github.com/tesseract-ocr/tessdata/raw/main/tur.traineddata
# Kopyala: C:\Program Files\Tesseract-OCR\tessdata\tur.traineddata
```

### 4. LibreTranslate (Opsiyonel - Docker)

```bash
docker run -d -p 5001:5000 libretranslate/libretranslate
```

## 📡 Yeni Endpoint'ler

Tüm endpoint'ler `/extensions/` prefix'i altındadır.

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| POST | `/extensions/pdf-to-markdown` | PDF → Markdown |
| POST | `/extensions/pdf-ocr` | Taranmış PDF → Text |
| POST | `/extensions/pdf-with-ocr` | PDF'e OCR eklenmiş hali |
| POST | `/extensions/batch-translate` | Toplu dosya çevirisi |
| POST | `/extensions/html-to-pdf` | HTML → PDF |
| POST | `/extensions/md-to-pdf` | Markdown → PDF |
| POST | `/extensions/llm-prep` | PDF'i LLM için hazırla |
| GET | `/extensions/status` | Extension durumları |
| GET | `/extensions/health` | Extension sağlık kontrolü |

## 🔧 Kullanım

### PDF → Markdown

```python
import requests

files = {'file': open('document.pdf', 'rb')}
response = requests.post('http://localhost:5000/extensions/pdf-to-markdown', files=files)
markdown_text = response.text
```

### PDF OCR

```python
files = {'file': open('scanned.pdf', 'rb')}
data = {'lang': 'tur'}  # Türkçe
response = requests.post('http://localhost:5000/extensions/pdf-ocr', files=files, data=data)
text = response.json()['text']
```

### LibreTranslate ile Çeviri

```python
files = {'file': open('document.pdf', 'rb')}
data = {'target': 'en', 'service': 'libretranslate'}
response = requests.post('http://localhost:5000/extensions/batch-translate', files=files, data=data)
```

## ⚙️ Yapılandırma

Extension'lar için `.env` dosyasına ekleyin:

```env
# OCR
TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe
TESSDATA_PREFIX=C:\Program Files\Tesseract-OCR\tessdata

# LibreTranslate
LIBRETRANSLATE_URL=http://localhost:5001

# LLM
LLM_MODEL=gpt-4
LLM_MAX_TOKENS=4096
```

## 🛡️ Güvenlik

- Tüm extension'lar sandbox'ta çalışır
- Dosya boyutu limiti: 50MB
- Desteklenen formatlar: PDF, HTML, MD
- OCR için Türkçe karakter desteği

## 📊 Performans

| Extension | Ortalama Süre (1 sayfa) | Bellek |
|-----------|------------------------|--------|
| Markdown Converter | 2-3 sn | 50MB |
| OCR Service | 5-10 sn | 200MB |
| Translation Proxy | 3-5 sn | 100MB |
| HTML2PDF | 1-2 sn | 30MB |
| MD2PDF | 1-2 sn | 30MB |

## 🐛 Sorun Giderme

### Tesseract Bulunamadı

```
❌ Hata: Tesseract is not installed
✅ Çözüm: Tesseract'ı kur ve PATH'e ekle
```

### LibreTranslate Bağlanamadı

```
❌ Hata: Connection refused
✅ Çözüm: LibreTranslate servisini başlat (docker run)
```

### Türkçe Karakter Bozuk

```
❌ Hata: Türkçe karakterler gösterilmiyor
✅ Çözüm: tur.traineddata dosyasını tessdata klasörüne koy
```

## 📝 Geliştirme

Yeni extension eklemek için:

1. `extensions/` klasörüne yeni dosya oluştur
2. `ExtensionBase` sınıfından türet
3. `process()` metodunu implement et
4. `app.py`'ye yeni endpoint ekle (NON-BREAKING)

## 🔗 Kaynaklar

- [pdf-to-markdown](https://github.com/jzillmann/pdf-to-markdown)
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract)
- [LibreTranslate](https://github.com/LibreTranslate/LibreTranslate)
- [pymupdf4llm](https://github.com/pymupdf/pymupdf4llm)
- [OCRmyPDF](https://github.com/ocrmypdf/OCRmyPDF)
