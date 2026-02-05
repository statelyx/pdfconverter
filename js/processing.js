// ====================================
// PDF İŞLEME - BACKEND v5 ENTEGRASYONU
// Profesyonel PDF Isleme ve Ceviri Sistemi
// ====================================

// Backend URL - config.js'den alınıyor
// Railway deploy tamamlandığında js/config.js içindeki URL'yu güncelleyin

// ====================================
// ANA İŞLEM FONKSİYONU
// ====================================

async function processFiles() {
    if (!state.files || state.files.length === 0) {
        showToast('Lütfen dosya seçin!', 'error');
        return;
    }

    console.log('⚙️ İşlem:', state.currentTool);
    goToStep(3);
    updateProgress(0);

    try {
        var results = [];

        // Backend işlemleri
        if (state.currentTool === 'translate') {
            results = await translatePDFBackend();
        } else if (state.currentTool === 'compress-pdf') {
            results = await compressPDFBackend();
        } else if (state.currentTool === 'pdf-to-word') {
            results = await pdfToWordBackend();
        } else if (state.currentTool === 'pdf-to-excel') {
            results = await pdfToExcelBackend();
        } else if (state.currentTool === 'pdf-to-image') {
            results = await pdfToImageBackend();
        } else if (state.currentTool === 'pdf-to-images') {
            results = await pdfToImagesBackend();
        }
        // Tarayıcı işlemleri (fallback)
        else {
            switch (state.currentTool) {
                case 'word-to-pdf': results = await wordToPDF(); break;
                case 'jpg-to-pdf': results = await imagesToPDF(); break;
                case 'pdf-to-jpg': results = await pdfToImages(); break;
                case 'merge-pdf': results = await mergePDFs(); break;
                case 'split-pdf': results = await splitPDF(); break;
            }
        }

        showResults(results);
        showToast('Tamamlandı!', 'success');

    } catch (error) {
        console.error('❌', error);
        showToast('Hata: ' + error.message, 'error');
        goToStep(2);
    }
}

// ====================================
// PROGRESS VE UI
// ====================================

function updateProgress(p) {
    var el = document.getElementById('progressFill');
    if (el) el.style.width = Math.min(p, 100) + '%';

    var status = document.getElementById('processingStatus');
    if (status) {
        if (p < 20) status.textContent = 'Dosya yükleniyor...';
        else if (p < 40) status.textContent = 'Dönüştürme başlatıldı...';
        else if (p < 70) status.textContent = 'Çeviri yapılıyor...';
        else if (p < 90) status.textContent = 'Çıktı hazırlanıyor...';
        else status.textContent = 'Tamamlanıyor...';
    }
}

function showResults(results) {
    goToStep(4);
    var dl = document.getElementById('downloadList');
    if (!dl) return;

    dl.innerHTML = '';
    window.downloadResults = results;

    for (var i = 0; i < results.length; i++) {
        (function (idx, r) {
            var item = document.createElement('div');
            item.className = 'download-item';
            item.innerHTML = '<div class="file-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/></svg></div>' +
                '<div class="file-info"><div class="file-name">' + r.name + '</div><div class="file-size">' + formatFileSize(r.size) + '</div></div>' +
                '<button class="download-btn" type="button">İndir</button>';

            item.querySelector('.download-btn').onclick = function () {
                var a = document.createElement('a');
                a.href = r.url;
                a.download = r.name;
                a.click();
            };
            dl.appendChild(item);
        })(i, results[i]);
    }
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function resetTool() {
    state.files = [];
    var fl = document.getElementById('fileList');
    if (fl) fl.innerHTML = '';
    var fi = document.getElementById('fileInput');
    if (fi) fi.value = '';
    goToStep(1);
}

// ====================================
// BACKEND ENDPOINT'LER - v5
// ====================================

/**
 * PDF Çeviri - Profesyonel Version
 * Türkçe font ile, görsel bütünlüğü koruyarak
 */
async function translatePDFBackend() {
    console.log('🌐 Backend çeviri v5 başlıyor...');
    updateProgress(10);

    var file = state.files[0];
    var formData = new FormData();
    formData.append('file', file);

    var srcLang = document.getElementById('sourceLang');
    var tgtLang = document.getElementById('targetLang');
    var formatSelect = document.getElementById('translateFormat');

    formData.append('source', srcLang ? srcLang.value : 'auto');
    formData.append('target', tgtLang ? tgtLang.value : 'tr');

    var format = formatSelect ? formatSelect.value : 'html';
    var endpoint = format === 'html' ? '/translate-html' : '/translate';

    console.log('📄 Format:', format);
    console.log('🌐', (srcLang ? srcLang.value : 'auto'), '→', (tgtLang ? tgtLang.value : 'tr'));
    updateProgress(30);

    try {
        var response = await fetch(BACKEND_URL + endpoint, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            var err = await response.json().catch(function () { return {}; });
            throw new Error(err.error || 'Backend hatası');
        }

        updateProgress(90);

        var blob = await response.blob();
        var targetLang = tgtLang ? tgtLang.value : 'tr';
        var ext = format === 'html' ? '.html' : '.pdf';
        var fileName = file.name.replace('.pdf', '_ceviri_' + targetLang + ext);

        updateProgress(100);
        console.log('✅ Çeviri tamamlandı:', fileName);

        return [{ name: fileName, size: blob.size, url: URL.createObjectURL(blob) }];

    } catch (error) {
        console.error('❌ Backend hatası:', error);
        throw error;
    }
}

/**
 * PDF → Word - Yeni Version
 * pdf2docx ile görselleri koruyarak
 */
async function pdfToWordBackend() {
    console.log('📄 Backend PDF→Word başlıyor...');
    updateProgress(10);

    var file = state.files[0];
    var formData = new FormData();
    formData.append('file', file);

    // Çeviri seçeneği
    var translate = document.getElementById('translateOption');
    if (translate) {
        formData.append('translate', translate.checked ? 'true' : 'false');
    } else {
        formData.append('translate', 'false');
    }

    var srcLang = document.getElementById('sourceLang');
    var tgtLang = document.getElementById('targetLang');
    if (srcLang) formData.append('source', srcLang.value);
    if (tgtLang) formData.append('target', tgtLang.value);

    updateProgress(30);

    try {
        var response = await fetch(BACKEND_URL + '/pdf-to-word', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            var err = await response.json().catch(function () { return {}; });
            throw new Error(err.error || 'Backend hatası');
        }

        updateProgress(90);

        var blob = await response.blob();
        var fileName = file.name.replace('.pdf', '.docx');

        updateProgress(100);
        console.log('✅ PDF→Word tamamlandı:', fileName);

        return [{ name: fileName, size: blob.size, url: URL.createObjectURL(blob) }];

    } catch (error) {
        console.warn('⚠️ Backend erişilemiyor:', error);
        throw error;
    }
}

/**
 * PDF → Excel - Yeni Endpoint
 * Camelot ile tablo extraction
 */
async function pdfToExcelBackend() {
    console.log('📊 Backend PDF→Excel başlıyor...');
    updateProgress(10);

    var file = state.files[0];
    var formData = new FormData();
    formData.append('file', file);

    // Çeviri seçeneği
    var translate = document.getElementById('translateOption');
    if (translate) {
        formData.append('translate', translate.checked ? 'true' : 'false');
    } else {
        formData.append('translate', 'false');
    }

    var srcLang = document.getElementById('sourceLang');
    var tgtLang = document.getElementById('targetLang');
    if (srcLang) formData.append('source', srcLang.value);
    if (tgtLang) formData.append('target', tgtLang.value);

    updateProgress(30);

    try {
        var response = await fetch(BACKEND_URL + '/pdf-to-excel', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            var err = await response.json().catch(function () { return {}; });
            throw new Error(err.error || 'Backend hatası');
        }

        updateProgress(90);

        var blob = await response.blob();
        var fileName = file.name.replace('.pdf', '.xlsx');

        updateProgress(100);
        console.log('✅ PDF→Excel tamamlandı:', fileName);

        return [{ name: fileName, size: blob.size, url: URL.createObjectURL(blob) }];

    } catch (error) {
        console.warn('⚠️ Backend hatası:', error);
        throw error;
    }
}

/**
 * PDF → Resim (Tek Sayfa)
 */
async function pdfToImageBackend() {
    console.log('🖼️ Backend PDF→Resim başlıyor...');
    updateProgress(10);

    var file = state.files[0];
    var formData = new FormData();
    formData.append('file', file);

    var pageSelect = document.getElementById('imagePage');
    var page = pageSelect ? parseInt(pageSelect.value) : 0;
    formData.append('page', page.toString());

    var formatSelect = document.getElementById('imageFormat');
    var format = formatSelect ? formatSelect.value : 'png';
    formData.append('format', format);

    var dpiSelect = document.getElementById('imageDPI');
    var dpi = dpiSelect ? parseInt(dpiSelect.value) : 300;
    formData.append('dpi', dpi.toString());

    console.log('📄 Sayfa:', page, 'Format:', format, 'DPI:', dpi);
    updateProgress(30);

    try {
        var response = await fetch(BACKEND_URL + '/pdf-to-image', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            var err = await response.json().catch(function () { return {}; });
            throw new Error(err.error || 'Backend hatası');
        }

        updateProgress(90);

        var blob = await response.blob();
        var ext = format === 'jpg' ? 'jpg' : 'png';
        var fileName = file.name.replace('.pdf', '_page' + (page + 1) + '.' + ext);

        updateProgress(100);
        console.log('✅ PDF→Resim tamamlandı:', fileName);

        return [{ name: fileName, size: blob.size, url: URL.createObjectURL(blob) }];

    } catch (error) {
        console.warn('⚠️ Backend hatası:', error);
        throw error;
    }
}

/**
 * PDF → Tüm Resimler (ZIP)
 */
async function pdfToImagesBackend() {
    console.log('🖼️ Backend PDF→Tüm Resimler başlıyor...');
    updateProgress(10);

    var file = state.files[0];
    var formData = new FormData();
    formData.append('file', file);

    var formatSelect = document.getElementById('imageFormat');
    var format = formatSelect ? formatSelect.value : 'png';
    formData.append('format', format);

    var dpiSelect = document.getElementById('imageDPI');
    var dpi = dpiSelect ? parseInt(dpiSelect.value) : 300;
    formData.append('dpi', dpi.toString());

    console.log('📄 Format:', format, 'DPI:', dpi);
    updateProgress(30);

    try {
        var response = await fetch(BACKEND_URL + '/pdf-to-images', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            var err = await response.json().catch(function () { return {}; });
            throw new Error(err.error || 'Backend hatası');
        }

        updateProgress(90);

        var blob = await response.blob();
        var fileName = file.name.replace('.pdf', '_images.zip');

        updateProgress(100);
        console.log('✅ PDF→Tüm Resimler tamamlandı:', fileName);

        return [{ name: fileName, size: blob.size, url: URL.createObjectURL(blob) }];

    } catch (error) {
        console.warn('⚠️ Backend hatası:', error);
        throw error;
    }
}

/**
 * PDF Sıkıştırma
 */
async function compressPDFBackend() {
    console.log('📦 Backend sıkıştırma başlıyor...');
    updateProgress(10);

    var file = state.files[0];
    var formData = new FormData();
    formData.append('file', file);

    updateProgress(30);

    try {
        var response = await fetch(BACKEND_URL + '/compress', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            var err = await response.json().catch(function () { return {}; });
            throw new Error(err.error || 'Backend hatası');
        }

        updateProgress(90);

        var blob = await response.blob();
        var fileName = file.name.replace('.pdf', '_compressed.pdf');

        var ratio = ((1 - blob.size / file.size) * 100).toFixed(0);
        console.log('📦 Sıkıştırma oranı: %' + ratio);

        updateProgress(100);
        showToast('%' + ratio + ' küçüldü!', 'success');

        return [{ name: fileName, size: blob.size, url: URL.createObjectURL(blob) }];

    } catch (error) {
        console.warn('⚠️ Backend erişilemiyor');
        throw error;
    }
}

// ====================================
// BACKEND SAĞLIK KONTROLÜ
// ====================================

async function checkBackendHealth() {
    try {
        var response = await fetch(BACKEND_URL + '/health');
        if (response.ok) {
            var data = await response.json();
            console.log('✅ Backend v' + data.version + ' aktif');
            console.log('📋 Özellikler:', data.features);
            return data;
        }
    } catch (e) {
        console.warn('⚠️ Backend erişilemiyor');
    }
    return null;
}

// Export
window.processFiles = processFiles;
window.resetTool = resetTool;
window.checkBackendHealth = checkBackendHealth;
window.translatePDFBackend = translatePDFBackend;
window.pdfToWordBackend = pdfToWordBackend;
window.pdfToExcelBackend = pdfToExcelBackend;
window.pdfToImageBackend = pdfToImageBackend;
window.pdfToImagesBackend = pdfToImagesBackend;
window.compressPDFBackend = compressPDFBackend;
