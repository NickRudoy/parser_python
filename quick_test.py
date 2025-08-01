#!/usr/bin/env python3
"""
Быстрый тест для проверки исправления ошибки
"""

import asyncio
from main import SEOFrogScanner

async def quick_test():
    """Быстрый тест с минимальными настройками"""
    
    # Используем простой сайт для тестирования
    website_url = "https://httpbin.org"
    
    print(f"🧪 Быстрый тест для {website_url}")
    print("=" * 50)
    
    scanner = SEOFrogScanner(website_url)
    
    # Минимальные настройки для быстрого теста
    scanner.config.update({
        'main_domain_only': True,
        'calculate_pagerank': True,
        'max_depth': 1,  # Очень ограниченная глубина
        'pagerank_iterations': 3,
        'max_response_time': 15,
    })
    
    print("⚙️  Настройки:")
    print(f"   - Основной домен: {scanner.get_main_domain(website_url)}")
    print(f"   - Максимальная глубина: {scanner.config['max_depth']}")
    print(f"   - Итерации PageRank: {scanner.config['pagerank_iterations']}")
    print()
    
    try:
        await scanner.run()
        print("\n✅ Тест завершен успешно!")
        print(f"📊 Проанализировано страниц: {scanner.total_scanned}")
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(quick_test()) 