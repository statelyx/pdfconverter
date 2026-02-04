# -*- coding: utf-8 -*-
"""
PDF Komuta Merkezi - Extension Pack
Mevcut sisteme DOKUNMADAN çalışan eklentiler
"""

__version__ = "1.0.0"

# Extension durumları
EXTENSIONS = {
    "markdown_converter": True,
    "ocr_service": True,
    "translation_proxy": True,
    "google_trans_scraper": True,
    "llm_prep": True,
    "html2pdf_ext": True,
    "md2pdf_ext": True,
    "pdf_ocr_adder": True,
    "batch_translator": True
}


class ExtensionBase:
    """Tüm extension'lar için base sınıf"""

    def __init__(self, config=None):
        self.config = config or {}
        self.enabled = self.check_available()

    def check_available(self):
        """Extension kullanılabilir mi kontrol et"""
        return True

    def process(self, input_data, **kwargs):
        """Ana işlem metodu - override edilecek"""
        raise NotImplementedError

    def get_info(self):
        """Extension bilgisi"""
        return {
            "name": self.__class__.__name__,
            "enabled": self.enabled,
            "version": getattr(self, "__version__", "1.0.0")
        }


def get_extension_status():
    """Tüm extension'ların durumunu döndür"""
    status = {}

    for name, enabled in EXTENSIONS.items():
        status[name] = {
            "enabled": enabled,
            "available": True
        }

    return status
