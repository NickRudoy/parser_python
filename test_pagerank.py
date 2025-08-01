#!/usr/bin/env python3
"""
Тестовый скрипт для проверки функционала PageRank и фильтрации доменов
"""

import asyncio
from main import SEOFrogScanner

async def test_scanner():
    """Тестирование сканера с различными настройками"""
    
    # Тестовый URL (замените на реальный для тестирования)
    test_url = "https://example.com"
    
    print("🧪 Тестирование SEO Frog Scanner")
    print("=" * 50)
    
    # Создаем сканер с настройками
    scanner = SEOFrogScanner(test_url)
    
    # Настраиваем параметры для тестирования
    scanner.config.update({
        'main_domain_only': True,  # Только основной домен
        'calculate_pagerank': True,  # Включаем PageRank
        'max_depth': 3,  # Ограничиваем глубину для тестирования
        'pagerank_iterations': 5,  # Уменьшаем итерации для быстрого тестирования
    })
    
    print(f"🔗 Начальный URL: {test_url}")
    print(f"🌐 Основной домен: {scanner.get_main_domain(test_url)}")
    print(f"⚙️  Настройки:")
    print(f"   - Только основной домен: {scanner.config['main_domain_only']}")
    print(f"   - PageRank включен: {scanner.config['calculate_pagerank']}")
    print(f"   - Максимальная глубина: {scanner.config['max_depth']}")
    print(f"   - Итерации PageRank: {scanner.config['pagerank_iterations']}")
    print()
    
    # Тестируем фильтрацию доменов
    test_urls = [
        "https://example.com/page1",
        "https://sub.example.com/page2", 
        "https://www.example.com/page3",
        "https://blog.example.com/page4",
        "https://example.org/page5"  # Другой домен
    ]
    
    print("🔍 Тестирование фильтрации доменов:")
    for url in test_urls:
        is_main = scanner.is_main_domain_only(url)
        main_domain = scanner.get_main_domain(url)
        print(f"   {url} -> Основной домен: {main_domain}, Разрешено: {is_main}")
    
    print()
    print("🚀 Запуск сканирования...")
    print("(Для реального тестирования замените test_url на реальный сайт)")
    
    # Раскомментируйте для реального тестирования:
    # await scanner.run()

if __name__ == "__main__":
    asyncio.run(test_scanner()) 