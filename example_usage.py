#!/usr/bin/env python3
"""
Пример использования SEO Frog Scanner с PageRank и фильтрацией доменов
"""

import asyncio
from main import SEOFrogScanner

async def scan_with_pagerank():
    """Пример сканирования сайта с PageRank анализом"""
    
    # Замените на реальный URL для тестирования
    website_url = input("Введите URL сайта для анализа (например, https://example.com): ")
    
    print(f"\n🔍 Начинаем анализ сайта: {website_url}")
    print("=" * 60)
    
    # Создаем сканер
    scanner = SEOFrogScanner(website_url)
    
    # Настраиваем параметры для анализа
    scanner.config.update({
        'main_domain_only': True,        # Только основной домен
        'calculate_pagerank': True,      # Включаем PageRank
        'pagerank_damping': 0.85,        # Стандартный коэффициент затухания
        'pagerank_iterations': 10,       # Количество итераций
        'max_depth': 5,                  # Ограничиваем глубину для быстрого анализа
        'max_response_time': 10,         # Увеличиваем таймаут
    })
    
    print("⚙️  Настройки анализа:")
    print(f"   - Основной домен: {scanner.get_main_domain(website_url)}")
    print(f"   - Только основной домен: {scanner.config['main_domain_only']}")
    print(f"   - PageRank включен: {scanner.config['calculate_pagerank']}")
    print(f"   - Максимальная глубина: {scanner.config['max_depth']}")
    print(f"   - Итерации PageRank: {scanner.config['pagerank_iterations']}")
    print()
    
    try:
        # Запускаем сканирование
        await scanner.run()
        
        print("\n✅ Анализ завершен!")
        print("\n📊 Результаты:")
        print(f"   - Проанализировано страниц: {scanner.total_scanned}")
        print(f"   - Найдено ошибок: {len(scanner.not_found_urls) + len(scanner.error_urls)}")
        
        if scanner.config['calculate_pagerank'] and scanner.pages_data:
            # Показываем топ-5 страниц по PageRank
            sorted_pages = sorted(
                scanner.pages_data.items(), 
                key=lambda x: x[1].page_rank, 
                reverse=True
            )[:5]
            
            print(f"   - Топ-5 страниц по PageRank:")
            for i, (url, data) in enumerate(sorted_pages, 1):
                short_url = url.split('/')[-1] if url.split('/')[-1] else url.split('/')[-2]
                print(f"     {i}. {short_url}: {data.page_rank:.4f}")
        
        print("\n📁 Отчеты сохранены в файлы Excel")
        
    except KeyboardInterrupt:
        print("\n⚠️  Сканирование прервано пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка при сканировании: {e}")

async def quick_test():
    """Быстрый тест с минимальными настройками"""
    
    website_url = input("Введите URL для быстрого теста: ")
    
    scanner = SEOFrogScanner(website_url)
    
    # Минимальные настройки для быстрого теста
    scanner.config.update({
        'main_domain_only': True,
        'calculate_pagerank': True,
        'max_depth': 2,
        'pagerank_iterations': 5,
    })
    
    print(f"🚀 Быстрый тест для {website_url}")
    await scanner.run()

if __name__ == "__main__":
    print("SEO Frog Scanner - PageRank и Фильтрация Доменов")
    print("=" * 50)
    print("1. Полный анализ с PageRank")
    print("2. Быстрый тест")
    
    choice = input("\nВыберите режим (1 или 2): ").strip()
    
    if choice == "1":
        asyncio.run(scan_with_pagerank())
    elif choice == "2":
        asyncio.run(quick_test())
    else:
        print("Неверный выбор. Запускаем полный анализ...")
        asyncio.run(scan_with_pagerank()) 