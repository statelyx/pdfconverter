// ====================================
// DÖNÜŞTÜRÜCÜLER - LIGHTWEIGHT
// ====================================

// PDF to Word
async function pdfToWord() {
    const file = state.files[0];
    const arr = await readFileAsArrayBuffer(file);
    const pdf = await pdfjsLib.getDocument({ data: arr }).promise;

    let html = '<!DOCTYPE html><html><head><meta charset="UTF-8"><style>body{font-family:Arial;margin:40px;}.page{page-break-after:always;margin-bottom:30px;}</style></head><body>';

    for (let i = 1; i <= pdf.numPages; i++) {
        const page = await pdf.getPage(i);
        const tc = await page.getTextContent();
        html += `<div class="page"><h3>Sayfa ${i}</h3><p>${tc.items.map(x => x.str).join(' ')}</p></div>`;
        updateProgress(i / pdf.numPages * 100);
    }

    html += '</body></html>';
    const blob = new Blob([html], { type: 'text/html' });
    return [{ name: file.name.replace('.pdf', '.html'), size: blob.size, url: URL.createObjectURL(blob) }];
}

// Word to PDF
async function wordToPDF() {
    const file = state.files[0];
    const arr = await readFileAsArrayBuffer(file);

    let text = '';
    try {
        const result = await mammoth.extractRawText({ arrayBuffer: arr });
        text = result.value;
    } catch (e) {
        text = new TextDecoder().decode(arr);
    }

    updateProgress(50);

    const { jsPDF } = window.jspdf;
    const doc = new jsPDF();
    const lines = doc.splitTextToSize(text, 180);
    let y = 20;

    lines.forEach(line => {
        if (y > 280) { doc.addPage(); y = 20; }
        doc.text(line, 15, y);
        y += 7;
    });

    updateProgress(100);
    const blob = doc.output('blob');
    return [{ name: file.name.replace(/\.(doc|docx)$/i, '.pdf'), size: blob.size, url: URL.createObjectURL(blob) }];
}

// Images to PDF
async function imagesToPDF() {
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF();

    for (let i = 0; i < state.files.length; i++) {
        if (i > 0) doc.addPage();

        const dataUrl = await readFileAsDataURL(state.files[i]);
        const img = new Image();
        await new Promise(r => { img.onload = r; img.src = dataUrl; });

        const pw = doc.internal.pageSize.getWidth();
        const ph = doc.internal.pageSize.getHeight();
        let iw = pw - 20, ih = (img.height * iw) / img.width;

        if (ih > ph - 20) { ih = ph - 20; iw = (img.width * ih) / img.height; }

        doc.addImage(dataUrl, 'JPEG', (pw - iw) / 2, (ph - ih) / 2, iw, ih);
        updateProgress((i + 1) / state.files.length * 100);
    }

    const blob = doc.output('blob');
    return [{ name: 'gorseller.pdf', size: blob.size, url: URL.createObjectURL(blob) }];
}

// PDF to Images
async function pdfToImages() {
    const file = state.files[0];
    const arr = await readFileAsArrayBuffer(file);
    const pdf = await pdfjsLib.getDocument({ data: arr }).promise;

    const results = [];
    const fmt = document.getElementById('outputFormat')?.value || 'jpg';

    for (let i = 1; i <= pdf.numPages; i++) {
        const page = await pdf.getPage(i);
        const vp = page.getViewport({ scale: 1.5 });

        const canvas = document.createElement('canvas');
        canvas.width = vp.width;
        canvas.height = vp.height;

        await page.render({ canvasContext: canvas.getContext('2d'), viewport: vp }).promise;

        const dataUrl = canvas.toDataURL(fmt === 'png' ? 'image/png' : 'image/jpeg', 0.85);
        const blob = await fetch(dataUrl).then(r => r.blob());

        results.push({ name: `sayfa_${i}.${fmt}`, size: blob.size, url: URL.createObjectURL(blob) });
        updateProgress(i / pdf.numPages * 100);
    }

    return results;
}

// Merge PDFs
async function mergePDFs() {
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF();
    let first = true;

    for (let f = 0; f < state.files.length; f++) {
        const arr = await readFileAsArrayBuffer(state.files[f]);
        const pdf = await pdfjsLib.getDocument({ data: arr }).promise;

        for (let i = 1; i <= pdf.numPages; i++) {
            if (!first) doc.addPage();
            first = false;

            const page = await pdf.getPage(i);
            const vp = page.getViewport({ scale: 1.5 });

            const canvas = document.createElement('canvas');
            canvas.width = vp.width;
            canvas.height = vp.height;

            await page.render({ canvasContext: canvas.getContext('2d'), viewport: vp }).promise;
            doc.addImage(canvas.toDataURL('image/jpeg', 0.8), 'JPEG', 0, 0, doc.internal.pageSize.getWidth(), doc.internal.pageSize.getHeight());
        }
        updateProgress((f + 1) / state.files.length * 100);
    }

    const blob = doc.output('blob');
    return [{ name: 'birlesik.pdf', size: blob.size, url: URL.createObjectURL(blob) }];
}

// Split PDF
async function splitPDF() {
    const file = state.files[0];
    const arr = await readFileAsArrayBuffer(file);
    const pdf = await pdfjsLib.getDocument({ data: arr }).promise;

    const { jsPDF } = window.jspdf;
    const results = [];

    for (let i = 1; i <= pdf.numPages; i++) {
        const page = await pdf.getPage(i);
        const vp = page.getViewport({ scale: 1.5 });

        const canvas = document.createElement('canvas');
        canvas.width = vp.width;
        canvas.height = vp.height;

        await page.render({ canvasContext: canvas.getContext('2d'), viewport: vp }).promise;

        const doc = new jsPDF();
        doc.addImage(canvas.toDataURL('image/jpeg', 0.8), 'JPEG', 0, 0, doc.internal.pageSize.getWidth(), doc.internal.pageSize.getHeight());

        const blob = doc.output('blob');
        results.push({ name: `sayfa_${i}.pdf`, size: blob.size, url: URL.createObjectURL(blob) });
        updateProgress(i / pdf.numPages * 100);
    }

    return results;
}

// Compress PDF
async function compressPDF() {
    const file = state.files[0];
    const arr = await readFileAsArrayBuffer(file);
    const pdf = await pdfjsLib.getDocument({ data: arr }).promise;

    const { jsPDF } = window.jspdf;
    const doc = new jsPDF();

    for (let i = 1; i <= pdf.numPages; i++) {
        if (i > 1) doc.addPage();

        const page = await pdf.getPage(i);
        const vp = page.getViewport({ scale: 1 });

        const canvas = document.createElement('canvas');
        canvas.width = vp.width;
        canvas.height = vp.height;

        await page.render({ canvasContext: canvas.getContext('2d'), viewport: vp }).promise;
        doc.addImage(canvas.toDataURL('image/jpeg', 0.5), 'JPEG', 0, 0, doc.internal.pageSize.getWidth(), doc.internal.pageSize.getHeight());
        updateProgress(i / pdf.numPages * 100);
    }

    const blob = doc.output('blob');
    const ratio = ((1 - blob.size / file.size) * 100).toFixed(0);
    console.log(`📦 Sıkıştırma: %${ratio}`);

    return [{ name: file.name.replace('.pdf', '_sikistirilmis.pdf'), size: blob.size, url: URL.createObjectURL(blob) }];
}
