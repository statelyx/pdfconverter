// ====================================
// PDF KOMUTA MERKEZİ - CONFIG
// ====================================

// Backend URL - Railway Production
// Bunu Railway deploy tamamlandığında güncelleyin
var BACKEND_URL = 'https://web-production-8310a.up.railway.app';

// Vercel build sırasında environment variable'dan al
if (typeof window !== 'undefined' && window.BACKEND_URL) {
    BACKEND_URL = window.BACKEND_URL;
}
