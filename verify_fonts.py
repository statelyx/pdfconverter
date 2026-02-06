# -*- coding: utf-8 -*-
import fitz
import os

def verify_fonts():
    root_fonts = "c:\\Users\\furkan.avcilar\\Desktop\\Projelerim\\pdfconverter\\fonts"
    fonts = [
        "Binoma-Regular.ttf",
        "LTFlodeNeue-Regular.otf",
        "TransformaSans-Medium.ttf"
    ]
    
    chars = ['İ', 'ı', 'ş', 'Ş', 'ğ', 'Ğ', 'ü', 'Ü', 'ö', 'Ö', 'ç', 'Ç']
    
    print("🔍 Font Verification:")
    for f_name in fonts:
        path = os.path.join(root_fonts, f_name)
        if os.path.exists(path):
            try:
                font = fitz.Font(fontfile=path)
                print(f"\nFont: {f_name}")
                missing = []
                for char in chars:
                    if not font.has_glyph(ord(char)):
                        missing.append(char)
                
                if not missing:
                    print(f"  ✓ All Turkish characters supported!")
                else:
                    print(f"  ✗ Missing characters: {' '.join(missing)}")
            except Exception as e:
                print(f"  ✗ Error loading font: {e}")
        else:
            print(f"  ! Font not found at {path}")

if __name__ == "__main__":
    verify_fonts()
