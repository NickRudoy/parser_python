from datetime import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom
import itertools
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import concurrent.futures
import time
from tqdm import tqdm
import pickle
from pathlib import Path
import logging
import aiohttp
import asyncio
from aiohttp import ClientTimeout
from functools import lru_cache

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Константы
MAX_WORKERS = 100  # Увеличено количество одновременных соединений
TIMEOUT = 2  # Упрощенный таймаут в секундах
BATCH_SIZE = 200  # Увеличен размер пакета
MAX_RETRIES = 3  # Увеличено количество попыток
SEMAPHORE_LIMIT = 50  # Ограничение количества одновременных запросов
CACHE_FILE = 'sitemap_cache.pkl'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def load_cache():
    """Загружает кэш проверенных URL"""
    try:
        if Path(CACHE_FILE).exists():
            with open(CACHE_FILE, 'rb') as f:
                return pickle.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки кэша: {e}")
    return {}

def save_cache(cache):
    """Сохраняет кэш проверенных URL"""
    try:
        with open(CACHE_FILE, 'wb') as f:
            pickle.dump(cache, f)
    except Exception as e:
        logger.error(f"Ошибка сохранения кэша: {e}")

def get_filter_params(base_url):
    """Получает параметры фильтров с сайта"""
    try:
        with requests.get(base_url, headers=HEADERS, timeout=TIMEOUT) as response:
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            filters = {}
            filter_form = soup.find('form', {'name': 'arrFilter_form'})
            if not filter_form:
                raise Exception("Форма фильтра не найдена")
                
            filter_panels = filter_form.find_all('div', class_='zcatalogDetail__filter_panel')
            
            filter_mapping = {
                'по материалу': 'material',
                'по форме': 'type',
                'по цвету': 'color',
                'кому': 'for'
            }
            
            for panel in filter_panels:
                filter_name = panel.find('span', class_='zcatalogDetail__filter_name')
                if not filter_name:
                    continue
                    
                filter_name = filter_name.text.strip().lower()
                filter_name = filter_mapping.get(filter_name, filter_name)
                
                values = [translit_to_latin(label.text.strip().lower())
                         for label in panel.find_all('label', class_='label-text')
                         if label.text.strip()]
                
                if values:
                    filters[filter_name] = values
                    
            logger.info(f"Найденные фильтры: {filters}")
            return filters
    except Exception as e:
        logger.error(f"Ошибка при получении фильтров: {e}")
        return None

@lru_cache(maxsize=1000)
def translit_to_latin(text):
    """Кэшируемая функция транслитерации"""
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

async def check_url_batch(urls, cache, session, semaphore):
    """Асинхронная проверка пакета URL с семафором"""
    tasks = []
    for url in urls:
        if url in cache:
            continue
        task = asyncio.create_task(check_single_url(url, session, semaphore))
        tasks.append(task)
    
    if not tasks:
        return []
        
    results = await asyncio.gather(*tasks, return_exceptions=True)
    valid_urls = []
    
    for url, result in zip(urls, results):
        if isinstance(result, bool) and result:
            valid_urls.append(url)
            cache[url] = url
        else:
            cache[url] = None
            
    return valid_urls

async def check_single_url(url, session, semaphore):
    """Проверка одного URL с семафором"""
    async with semaphore:  # Ограничиваем количество одновременных запросов
        for attempt in range(MAX_RETRIES):
            try:
                async with session.head(url, allow_redirects=True, timeout=TIMEOUT) as response:
                    return response.status == 200
            except Exception as e:
                if attempt == MAX_RETRIES - 1:
                    logger.debug(f"Failed to check {url}: {str(e)}")
                    return False
                await asyncio.sleep(0.1 * (attempt + 1))  # Увеличиваем задержку с каждой попыткой

async def check_urls_async(urls, cache):
    """Асинхронная проверка всех URL с прогресс-баром"""
    valid_urls = set()
    semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)
    
    connector = aiohttp.TCPConnector(limit=MAX_WORKERS, force_close=True, enable_cleanup_closed=True)
    timeout = aiohttp.ClientTimeout(total=TIMEOUT)
    
    async with aiohttp.ClientSession(
        headers=HEADERS, 
        connector=connector,
        timeout=timeout
    ) as session:
        with tqdm(total=len(urls), desc="Проверка URL") as pbar:
            for i in range(0, len(urls), BATCH_SIZE):
                batch = urls[i:i + BATCH_SIZE]
                batch_results = await check_url_batch(batch, cache, session, semaphore)
                valid_urls.update(batch_results)
                pbar.update(len(batch))
                
    return valid_urls

def generate_urls(base_url, filters):
    """Оптимизированная генерация URL"""
    urls = {base_url}
    
    # Предварительно вычисляем все возможные комбинации значений
    combinations = []
    for r in range(1, len(filters) + 1):
        for keys in itertools.combinations(filters.keys(), r):
            values_list = [filters[key] for key in keys]
            combinations.extend(itertools.product(*values_list))
    
    # Генерируем URL пакетами
    for combo in combinations:
        urls.add(f"{base_url}/{'/'.join(combo)}/")
    
    return list(urls)

async def async_generate_sitemap():
    """Асинхронная версия generate_sitemap с обработкой ошибок"""
    try:
        start_time = time.time()
        base_url = "https://obelisk.ru/catalog/pamyatniki"
        cache = load_cache()
        
        filters = get_filter_params(base_url)
        if not filters:
            logger.warning("Используем тестовые данные для фильтров")
            filters = {
                'material': ['kapustinskiy', 'granit', 'mramor'],
                'type': ['derevo', 'krest', 'plita'],
                'color': ['chernyy', 'krasnyy', 'seryy']
            }
        
        urls_to_check = generate_urls(base_url, filters)
        logger.info(f"Сгенерировано URL для проверки: {len(urls_to_check)}")
        
        valid_urls = await check_urls_async(urls_to_check, cache)
        
        # Создаем sitemap
        urlset = ET.Element('urlset', xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
        for url in valid_urls:
            add_url(urlset, url, '0.8' if url != base_url else '1.0')
        
        # Сохраняем результаты
        xml_str = minidom.parseString(ET.tostring(urlset)).toprettyxml(indent="    ")
        with open('sitemap_filters.xml', 'w', encoding='utf-8') as f:
            f.write(xml_str)
        
        save_cache(cache)
        
        elapsed_time = time.time() - start_time
        logger.info(f"Обработано URL: {len(urls_to_check)}")
        logger.info(f"Валидных URL: {len(valid_urls)}")
        logger.info(f"Время выполнения: {elapsed_time:.2f} секунд")
        
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        raise

def add_url(urlset, loc, priority):
    url = ET.SubElement(urlset, 'url')
    
    loc_elem = ET.SubElement(url, 'loc')
    loc_elem.text = loc
    
    lastmod = ET.SubElement(url, 'lastmod')
    lastmod.text = datetime.now().strftime('%Y-%m-%d')
    
    priority_elem = ET.SubElement(url, 'priority')
    priority_elem.text = priority

if __name__ == '__main__':
    asyncio.run(async_generate_sitemap()) 