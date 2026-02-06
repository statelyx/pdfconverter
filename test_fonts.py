# -*- coding: utf-8 -*-
import fitz
import os

def test_rendering():
    doc = fitz.open()
    page = doc.new_page()
    
    # Test text with full Turkish characters
    text = "DANİMARKA'DA VİZE İÇİN KONTROL LİSTESİ - şğüöçİ"
    
    # Font paths
    fonts = [
        ("Arial", "C:\\Windows\\Fonts\\arial.ttf"),
        ("LTFlode", "c:\\Users\\furkan.avcilar\\Desktop\\Projelerim\\pdfconverter\\fonts\\LTFlodeNeue-Regular.otf"),
        ("Binoma", "c:\\Users\\furkan.avcilar\\Desktop\\Projelerim\\pdfconverter\\fonts\\Binoma-Regular.ttf"),
        ("Transforma", "c:\\Users\\furkan.avcilar\\Desktop\\Projelerim\\pdfconverter\\fonts\\TransformaSans-Medium.ttf")
    ]
    
    y = 50
    for name, path in fonts:
        if os.path.exists(path):
            try:
                # Use a unique name for each font insertion
                f_name = f"font_{name}"
                page.insert_font(fontname=f_name, fontfile=path)
                
                rect = fitz.Rect(50, y, 550, y + 50)
                page.draw_rect(rect, color=(0.8, 0.8, 0.8), width=0.5)
                
                page.insert_textbox(
                    rect, 
                    f"{name}: {text}", 
                    fontsize=14, 
                    fontname=f_name,
                    color=(0, 0, 0)
                )
                print(f"✓ Rendered with {name}")
            except Exception as e:
                print(f"✗ Error with {name}: {e}")
        else:
            print(f"! Path missing for {name}: {path}")
        y += 70
        
    output_path = "test_turkish_fonts.pdf"
    doc.save(output_path)
    doc.close()
    print(f"\nSaved test PDF to {output_path}")

if __name__ == "__main__":
    test_rendering()
