# PROJE AMACI VE ANA KURALLAR (PURPOSE)

## 🎯 Temel Vizyon
Bu proje, PDF işleme, çeviri ve dönüştürme işlemlerini **SIFIR MALİYET** ilkesiyle gerçekleştiren, profesyonel seviyede bir araç setidir.

## ⚖️ Temel Kurallar
1. **Sıfır Maliyet Kuralı**: Proje kapsamında kullanılan hiçbir API, kütüphane veya araç için ücret ödenmeyecek. Öncelik her zaman açık kaynaklı (Open Source), self-hosted veya ücretsiz kotalı servislerdedir.
2. **Düzen Koruma (Layout Preservation)**: PDF çeviri ve dönüşümlerinde orijinal görsel düzen (tablo, sütun, resim yerleşimi) milimetrik hassasiyetle korunmalıdır.
3. **Karakter Uyumluluğu**: Başta Türkçe olmak üzere tüm dillerde karakter encoding (UTF-8) ve font uyumluluğu hatasız sağlanmalıdır.
4. **AI Odaklı Geliştirme**: Geliştirme süreci en güncel AI modelleri ve araçları (Hugging Face, Local LLMs vb.) ile beslenmelidir.

## 🛠️ Seçilmiş Teknolojiler
- **Backend**: Python (Flask)
- **PDF Core**: PyMuPDF (fitz) - *Hızlı ve hassas low-level işlem için.*
- **Çeviri**: Hugging Face Inference (NLLB, OPUS), LibreTranslate, Argos Translate.
- **Dönüşüm**: pdf2docx, reportlab, pandas.

---
## 🚫 Kritik Teknik Engeller (ASLA YAPILMAMASI GEREKENLER)
1. **Flask @app.options**: Flask'ın standart sürümünde bu dekoratör bulunmaz ve sunucunun boot failure (çökme) almasına neden olur. Her zaman `@app.route(..., methods=['OPTIONS'])` kullanın.
2. **max() Tekli Argüman**: Floatlarda `max(x1)` kullanımı `TypeError: 'float' object is not iterable` hatasına yol açar. Her zaman `max(a, b)` formatında veya liste içindeyse `max([list])` şeklinde kullanın.
3. **Senkron/Sıralı Çeviri**: Bellek tasarrufu için paralel işlemi (ThreadPool) tamamen kaldırmak Railway'de `WORKER TIMEOUT` hatasına yol açar. Makul bir worker sayısı ile (örn: 5-8) paralel işlem korunmalıdır.
4. **HTMLBox Çıkmazı**: Standart PDF yerleşimi için `insert_textbox` en güvenilir yoldur; `insert_htmlbox` font ve karakter uyumunda karmaşıklığa yol açabilir.

---
*Bu dosya projenin ruhunu temsil eder. Senden sonraki oturumlarda projeyi tarayan modeller, bu kuralları (özellikle sıfır maliyet ve kaliteli düzen koruma) baz alarak hareket etmelidir.*
