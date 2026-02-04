// ====================================
// PDF KOMUTA MERKEZİ - v3.0
// ====================================

// API Key backend tarafından yönetiliyor
const _k = { g: null };

const state = { currentTool: null, files: [] };

const toolConfig = {
    'translate': { title: 'PDF Çeviri', accept: '.pdf', options: 'translateOptions' },
    'pdf-to-word': { title: 'PDF → Word', accept: '.pdf' },
    'word-to-pdf': { title: 'Word → PDF', accept: '.doc,.docx' },
    'jpg-to-pdf': { title: 'Görsel → PDF', accept: '.jpg,.jpeg,.png,.gif,.webp', options: 'imageOptions', multiple: true },
    'pdf-to-jpg': { title: 'PDF → Görsel', accept: '.pdf', options: 'formatOptions' },
    'merge-pdf': { title: 'PDF Birleştir', accept: '.pdf', multiple: true },
    'split-pdf': { title: 'PDF Böl', accept: '.pdf', options: 'splitOptions' },
    'compress-pdf': { title: 'PDF Sıkıştır', accept: '.pdf' }
};

// INIT
window.addEventListener('DOMContentLoaded', function () {
    console.log('🚀 PDF Komuta Merkezi v3.0');

    // PDF.js
    if (typeof pdfjsLib !== 'undefined') {
        pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
    }

    // Tool cards - direct click handlers
    var cards = document.querySelectorAll('.tool-card');
    for (var i = 0; i < cards.length; i++) {
        (function (card) {
            card.addEventListener('click', function (e) {
                e.preventDefault();
                var tool = card.getAttribute('data-tool');
                if (tool) openTool(tool);
            });
        })(cards[i]);
    }

    // File input change handler
    var fileInput = document.getElementById('fileInput');
    if (fileInput) {
        fileInput.addEventListener('change', function (e) {
            console.log('📁 Dosya değişti:', this.files.length);
            if (this.files && this.files.length > 0) {
                handleFiles(this.files);
            }
        });
    }

    // Drag and drop on upload zone
    var uploadZone = document.getElementById('uploadZone');
    if (uploadZone) {
        uploadZone.addEventListener('dragover', function (e) {
            e.preventDefault();
            e.stopPropagation();
            this.classList.add('dragover');
        });

        uploadZone.addEventListener('dragleave', function (e) {
            e.preventDefault();
            this.classList.remove('dragover');
        });

        uploadZone.addEventListener('drop', function (e) {
            e.preventDefault();
            e.stopPropagation();
            this.classList.remove('dragover');
            var dt = e.dataTransfer;
            if (dt && dt.files && dt.files.length > 0) {
                // Manually trigger file handling
                handleFiles(dt.files);
            }
        });
    }

    // Split method
    var splitMethod = document.getElementById('splitMethod');
    if (splitMethod) {
        splitMethod.addEventListener('change', function () {
            var rg = document.getElementById('rangeGroup');
            if (rg) rg.style.display = this.value === 'range' ? 'block' : 'none';
        });
    }

    console.log('✅ Hazır!');
});

function openTool(toolName) {
    console.log('🔧 Araç:', toolName);
    state.currentTool = toolName;
    state.files = [];

    var config = toolConfig[toolName];
    if (!config) return;

    // Update UI
    var toolTitle = document.getElementById('toolTitle');
    var fileInput = document.getElementById('fileInput');
    var uploadHint = document.getElementById('uploadHint');
    var btnCost = document.getElementById('btnCost');
    var processBtn = document.getElementById('processBtn');

    if (toolTitle) toolTitle.textContent = config.title;
    if (fileInput) {
        fileInput.accept = config.accept;
        fileInput.multiple = !!config.multiple;
        fileInput.value = ''; // Reset
    }
    if (uploadHint) uploadHint.textContent = config.accept.replace(/\./g, '').toUpperCase();
    if (btnCost) btnCost.textContent = 'ÜCRETSİZ';
    if (processBtn) processBtn.textContent = toolName === 'translate' ? '🌐 Çevir' : '⚡ Dönüştür';

    // Options
    var optionPanels = ['translateOptions', 'formatOptions', 'imageOptions', 'splitOptions'];
    for (var i = 0; i < optionPanels.length; i++) {
        var el = document.getElementById(optionPanels[i]);
        if (el) {
            el.style.display = (optionPanels[i] === config.options) ? 'block' : 'none';
        }
    }

    // Clear file list
    var fileList = document.getElementById('fileList');
    if (fileList) fileList.innerHTML = '';

    goToStep(1);

    // Open modal
    var modal = document.getElementById('toolModal');
    if (modal) modal.classList.add('active');
}

function closeModal() {
    var modal = document.getElementById('toolModal');
    if (modal) modal.classList.remove('active');
    state.files = [];
    state.currentTool = null;
}

function goToStep(step) {
    for (var i = 1; i <= 4; i++) {
        var el = document.getElementById('step' + i);
        if (el) {
            el.style.display = (i === step) ? 'block' : 'none';
            if (i === step) el.classList.remove('hidden');
            else el.classList.add('hidden');
        }
    }
}

function handleFiles(fileList) {
    if (!fileList || fileList.length === 0) return;

    console.log('📁 Dosya sayısı:', fileList.length);

    var config = toolConfig[state.currentTool];
    if (!config) return;

    // Clear if single file mode
    if (!config.multiple && state.files.length > 0) {
        state.files = [];
        var fl = document.getElementById('fileList');
        if (fl) fl.innerHTML = '';
    }

    for (var i = 0; i < fileList.length; i++) {
        var file = fileList[i];
        state.files.push(file);
        addFileToList(file);
        console.log('✅ Dosya eklendi:', file.name);
    }

    if (state.files.length > 0) {
        setTimeout(function () { goToStep(2); }, 300);
    }
}

function addFileToList(file) {
    var fileList = document.getElementById('fileList');
    if (!fileList) return;

    var item = document.createElement('div');
    item.className = 'file-item';
    item.innerHTML = '<div class="file-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/></svg></div>' +
        '<div class="file-info"><div class="file-name">' + file.name + '</div><div class="file-size">' + (file.size / 1024).toFixed(1) + ' KB</div></div>' +
        '<button class="file-remove" type="button">&times;</button>';

    var removeBtn = item.querySelector('.file-remove');
    removeBtn.onclick = function () {
        state.files = state.files.filter(function (f) { return f.name !== file.name; });
        item.remove();
        if (state.files.length === 0) goToStep(1);
    };

    fileList.appendChild(item);
}

// File readers
function readFileAsArrayBuffer(file) {
    return new Promise(function (resolve, reject) {
        var r = new FileReader();
        r.onload = function () { resolve(r.result); };
        r.onerror = function () { reject(new Error('Dosya okunamadı')); };
        r.readAsArrayBuffer(file);
    });
}

function readFileAsDataURL(file) {
    return new Promise(function (resolve, reject) {
        var r = new FileReader();
        r.onload = function () { resolve(r.result); };
        r.onerror = function () { reject(new Error('Dosya okunamadı')); };
        r.readAsDataURL(file);
    });
}

// Global functions
window.openTool = openTool;
window.closeModal = closeModal;
window.goToStep = goToStep;
