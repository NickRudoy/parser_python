from datetime import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom
import itertools
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import concurrent.futures
import time

def get_filter_params(base_url):
    """Получает параметры фильтров с сайта"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(base_url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        filters = {}
        
        # Находим форму фильтра
        filter_form = soup.find('form', {'name': 'arrFilter_form'})
        if not filter_form:
            raise Exception("Форма фильтра не найдена")
            
        # Находим все панели фильтров
        filter_panels = filter_form.find_all('div', class_='zcatalogDetail__filter_panel')
        
        for panel in filter_panels:
            # Получаем название фильтра
            filter_name = panel.find('span', class_='zcatalogDetail__filter_name')
            if not filter_name:
                continue
                
            filter_name = filter_name.text.strip().lower()
            
            # Получаем значения фильтра
            values = []
            labels = panel.find_all('label', class_='label-text')
            for label in labels:
                value = label.text.strip().lower()
                # Преобразуем кириллицу в латиницу для URL
                value = translit_to_latin(value)
                if value:
                    values.append(value)
            
            if values:
                # Нормализуем названия фильтров
                if filter_name == 'по материалу':
                    filter_name = 'material'
                elif filter_name == 'по форме':
                    filter_name = 'type'
                elif filter_name == 'по цвету':
                    filter_name = 'color'
                elif filter_name == 'кому':
                    filter_name = 'for'
                    
                filters[filter_name] = values
                
        print("Найденные фильтры:", filters)
        return filters
    except Exception as e:
        print(f"Ошибка при получении фильтров: {e}")
        return None

def translit_to_latin(text):
    """Преобразует кириллицу в латиницу для URL"""
    translit_dict = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
        ' ': '-', ',': '', '.': '', '(': '', ')': '', '"': '', "'": ''
    }
    
    result = ''
    for char in text.lower():
        result += translit_dict.get(char, char)
    return result

def check_url_status(url):
    """Проверяет доступность URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.head(url, headers=headers, allow_redirects=True, timeout=5)
        return url if response.status_code == 200 else None
    except Exception:
        return None

def generate_sitemap():
    # Базовый URL сайта
    base_url = "https://obelisk.ru/catalog/pamyatniki"
    
    # Получаем параметры фильтров автоматически
    filters = get_filter_params(base_url)
    if not filters:
        print("Не удалось получить параметры фильтров. Используем тестовые данные.")
        filters = {
            'material': ['kapustinskiy', 'granit', 'mramor'],
            'type': ['derevo', 'krest', 'plita'],
            'color': ['chernyy', 'krasnyy', 'seryy']
        }
    
    # Создаем корневой элемент sitemap
    urlset = ET.Element('urlset', xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    
    # Проверяем базовую страницу
    if check_url_status(base_url):
        add_url(urlset, base_url, '1.0')
    
    # Собираем все возможные URL
    urls_to_check = []
    
    # Генерируем комбинации фильтров
    for r in range(1, len(filters) + 1):
        for keys in itertools.combinations(filters.keys(), r):
            values_list = [filters[key] for key in keys]
            for values in itertools.product(*values_list):
                url_parts = [base_url]
                for value in values:
                    url_parts.append(value)
                url = '/'.join(url_parts) + '/'
                urls_to_check.append(url)
    
    # Проверяем URL параллельно
    valid_urls = set()
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_url = {executor.submit(check_url_status, url): url for url in urls_to_check}
        for future in concurrent.futures.as_completed(future_to_url):
            result = future.result()
            if result:
                valid_urls.add(result)
                print(f"Валидный URL: {result}")
    
    # Добавляем валидные URL в sitemap
    for url in valid_urls:
        add_url(urlset, url, '0.8')
    
    # Создаем красиво отформатированный XML
    xml_str = minidom.parseString(ET.tostring(urlset)).toprettyxml(indent="    ")
    
    # Сохраняем в файл
    with open('sitemap_filters.xml', 'w', encoding='utf-8') as f:
        f.write(xml_str)
    
    print(f"Обработано URL: {len(urls_to_check)}")
    print(f"Валидных URL: {len(valid_urls)}")

def add_url(urlset, loc, priority):
    url = ET.SubElement(urlset, 'url')
    
    loc_elem = ET.SubElement(url, 'loc')
    loc_elem.text = loc
    
    lastmod = ET.SubElement(url, 'lastmod')
    lastmod.text = datetime.now().strftime('%Y-%m-%d')
    
    priority_elem = ET.SubElement(url, 'priority')
    priority_elem.text = priority

if __name__ == '__main__':
    generate_sitemap() 