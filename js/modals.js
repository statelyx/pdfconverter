// ====================================
// MODALS & HELPERS - LIGHTWEIGHT
// ====================================

function showPricingModal() {
    const m = document.getElementById('pricingModal');
    if (m) m.classList.add('active');
}

function closePricingModal() {
    const m = document.getElementById('pricingModal');
    if (m) m.classList.remove('active');
}

function buyCredits(n) {
    showToast(`Admin: ${n} kredi eklendi`, 'success');
    closePricingModal();
}

function showToast(msg, type = 'info') {
    const t = document.getElementById('toast');
    if (!t) { console.log(`[${type}] ${msg}`); return; }

    const m = t.querySelector('.toast-message');
    if (m) m.textContent = msg;

    t.className = 'toast show ' + type;
    setTimeout(() => t.classList.remove('show'), 3000);
}

// ESC to close
document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal.active').forEach(m => m.classList.remove('active'));
    }
});

// Click outside
document.addEventListener('click', e => {
    if (e.target.classList.contains('modal')) e.target.classList.remove('active');
});

window.showPricingModal = showPricingModal;
window.closePricingModal = closePricingModal;
window.buyCredits = buyCredits;
window.showToast = showToast;
