# 🚀 Быстрый старт - SEO Frog Scanner

## Установка и запуск

### 1. Активация виртуального окружения
```bash
source venv/bin/activate
```

### 2. Запуск основного сканера
```bash
python main.py
```

### 3. Запуск с PageRank анализом
```bash
python example_usage.py
```

## 🆕 Новые возможности

### Фильтрация по основному домену
- ✅ Сканирует только `example.com` и `www.example.com`
- ❌ Исключает `blog.example.com`, `shop.example.com` и другие поддомены

### Внутренний PageRank
- 🏆 Ранжирует страницы по важности
- 📊 Показывает топ-10 страниц в интерфейсе
- 📈 Создает отдельный отчет Excel

## ⚙️ Настройки

### Включение/отключение функций
```python
scanner.config.update({
    'main_domain_only': True,        # Только основной домен
    'calculate_pagerank': True,      # Включить PageRank
    'pagerank_damping': 0.85,        # Коэффициент затухания
    'pagerank_iterations': 10,       # Итерации расчета
})
```

### Быстрый тест
```python
scanner.config.update({
    'max_depth': 2,                  # Ограниченная глубина
    'pagerank_iterations': 5,        # Меньше итераций
})
```

## 📊 Отчеты

После сканирования создаются файлы:
- `seo_отчет_основной.xlsx` - основной отчет с PageRank
- `seo_отчет_pagerank.xlsx` - детальный анализ PageRank
- `seo_отчет_ошибки.xlsx` - найденные ошибки
- `seo_errors.log` - лог ошибок

## 🧪 Тестирование

### Проверка фильтрации доменов
```bash
python test_pagerank.py
```

### Примеры URL для тестирования
- ✅ `https://example.com/page1`
- ✅ `https://www.example.com/page2`
- ❌ `https://blog.example.com/page3`
- ❌ `https://shop.example.com/page4`

## 📈 Интерпретация PageRank

- **>0.1** - Очень важная страница
- **0.01-0.1** - Обычная страница
- **<0.01** - Мало ссылок

## 🔧 Устранение неполадок

### Медленное сканирование
- Уменьшите `max_depth`
- Уменьшите `pagerank_iterations`
- Увеличьте `max_response_time`

### Ошибки подключения
- Проверьте интернет-соединение
- Увеличьте таймауты
- Проверьте robots.txt сайта

## 📞 Поддержка

При возникновении проблем:
1. Проверьте логи в `seo_errors.log`
2. Запустите тестовый скрипт
3. Уменьшите глубину сканирования 