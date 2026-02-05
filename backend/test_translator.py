# -*- coding: utf-8 -*-
"""
Translator Test Script
Çeviri sistemini test eder
"""

import os
import sys

# Backend dizinini path'e ekle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_multi_translator():
    """Multi-Provider Translator testi"""
    print("\n" + "="*60)
    print("  🧪 Multi-Provider Translator Test")
    print("="*60)
    
    from translators.multi_translator import get_translator
    
    translator = get_translator()
    
    # Provider durumları
    print("\n📊 Provider Durumları:")
    for name, status in translator.get_provider_status().items():
        emoji = "✅" if status["available"] else "❌"
        print(f"   {emoji} {name}: {'Aktif' if status['available'] else 'Pasif'}")
    
    # Test metinleri
    test_cases = [
        ("Hello, how are you?", "en", "tr"),
        ("Good morning!", "en", "tr"),
        ("This is a test document.", "en", "tr"),
        ("The weather is nice today.", "en", "tr"),
    ]
    
    print("\n🌐 Çeviri Testleri:")
    success_count = 0
    
    for text, src, tgt in test_cases:
        result = translator.translate(text, tgt, src)
        status = "✅" if result.success else "❌"
        
        if result.success:
            success_count += 1
            print(f"   {status} [{result.provider}]")
            print(f"      EN: {text}")
            print(f"      TR: {result.text}")
        else:
            print(f"   {status} HATA: {result.error}")
            print(f"      EN: {text}")
        print()
    
    # Sonuç
    print("="*60)
    print(f"  📈 Sonuç: {success_count}/{len(test_cases)} başarılı")
    print("="*60 + "\n")
    
    return success_count == len(test_cases)


def test_hf_translator():
    """HF Translator testi (eski endpoint vs yeni endpoint)"""
    print("\n" + "="*60)
    print("  🧪 HF Translator Test (Yeni Endpoint)")
    print("="*60)
    
    from translators.hf_translator import get_translator, get_hf_token
    
    token = get_hf_token()
    if token:
        print(f"\n🔑 HF Token: ***{token[-4:]}")
    else:
        print("\n⚠️ HF Token bulunamadı!")
        return False
    
    translator = get_translator()
    
    # Test
    test_text = "Hello, this is a test."
    print(f"\n📝 Test: {test_text}")
    
    result = translator.translate(test_text, "tr", "en")
    
    if result.success:
        print(f"✅ Başarılı!")
        print(f"   Model: {result.model}")
        print(f"   Çeviri: {result.text}")
        return True
    else:
        print(f"❌ Başarısız: {result.error}")
        return False


def main():
    """Ana test fonksiyonu"""
    print("\n" + "🚀 PDF Komuta Merkezi - Translator Test Suite")
    print("="*60)
    
    # Environment değişkenlerini göster
    print("\n📋 Environment Değişkenleri:")
    env_vars = [
        "HUGGINGFACE_WRITE_API_KEY",
        "HUGGINGFACE_READ_API_KEY", 
        "HUGGINGFACE_API_KEY",
        "HF_TOKEN",
        "LIBRETRANSLATE_URL",
        "TRANSLATOR_PROVIDER"
    ]
    
    for var in env_vars:
        value = os.environ.get(var, "")
        if value:
            display = f"***{value[-4:]}" if len(value) > 4 else "***"
            print(f"   ✅ {var}: {display}")
        else:
            print(f"   ❌ {var}: (boş)")
    
    # Testleri çalıştır
    results = []
    
    # HF Translator testi
    try:
        results.append(("HF Translator", test_hf_translator()))
    except Exception as e:
        print(f"❌ HF Translator test hatası: {e}")
        results.append(("HF Translator", False))
    
    # Multi-Provider testi
    try:
        results.append(("Multi-Provider", test_multi_translator()))
    except Exception as e:
        print(f"❌ Multi-Provider test hatası: {e}")
        results.append(("Multi-Provider", False))
    
    # Özet
    print("\n" + "="*60)
    print("  📊 TEST SONUÇLARI")
    print("="*60)
    
    for name, passed in results:
        status = "✅ BAŞARILI" if passed else "❌ BAŞARISIZ"
        print(f"   {name}: {status}")
    
    all_passed = all(r[1] for r in results)
    print("\n" + "="*60)
    
    if all_passed:
        print("  🎉 TÜM TESTLER BAŞARILI!")
    else:
        print("  ⚠️ BAZI TESTLER BAŞARISIZ")
    
    print("="*60 + "\n")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
