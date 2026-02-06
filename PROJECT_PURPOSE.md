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
*Bu dosya projenin ruhunu temsil eder. Senden sonraki oturumlarda projeyi tarayan modeller, bu kuralları (özellikle sıfır maliyet ve kaliteli düzen koruma) baz alarak hareket etmelidir.*
