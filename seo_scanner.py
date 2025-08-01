import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
import pandas as pd
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
from rich.table import Table
from rich.text import Text
from rich import box
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn, TimeRemainingColumn
from dataclasses import dataclass
import time
from typing import Set, List, Dict
from collections import defaultdict
import re
from urllib.robotparser import RobotFileParser
import hashlib
from PIL import Image
from io import BytesIO
import requests
import ssl
from concurrent.futures import ThreadPoolExecutor
import xml.etree.ElementTree as ET

@dataclass
class PageSEOData:
    url: str
    status_code: int
    content_type: str
    title: str = ""
    meta_description: str = ""
    h1: List[str] = None
    h2: List[str] = None
    canonical: str = ""
    robots_meta: str = ""
    word_count: int = 0
    content_length: int = 0
    response_time: float = 0
    redirect_url: str = ""
    images: List[Dict] = None
    inlinks: List[str] = None
    outlinks: List[str] = None
    hreflang: Dict[str, str] = None
    schema_org: List[str] = None
    open_graph: Dict[str, str] = None
    twitter_cards: Dict[str, str] = None
    duplicate_content: bool = False
    content_hash: str = ""
    page_rank: float = 1.0
    internal_links_count: int = 0  # Количество внутренних ссылок НА эту страницу
    
    def __post_init__(self):
        self.h1 = self.h1 or []
        self.h2 = self.h2 or []
        self.images = self.images or []
        self.inlinks = self.inlinks or []
        self.outlinks = self.outlinks or []
        self.hreflang = self.hreflang or {}
        self.schema_org = self.schema_org or []
        self.open_graph = self.open_graph or {}
        self.twitter_cards = self.twitter_cards or {}

class SEOFrogScanner:
    def __init__(self, start_url: str):
        # Нормализация начального URL
        if not urlparse(start_url).scheme:
            start_url = f"https://{start_url}"
        self.start_url = start_url
        
        # Улучшенная нормализация домена
        parsed = urlparse(start_url)
        self.domain = parsed.netloc.lower().replace('www.', '')
        self.main_domain = self.get_main_domain(start_url)
        
        self.visited_urls: Set[str] = set()
        self.pages_data: Dict[str, PageSEOData] = {}
        self.console = Console()
        self.status_counts = defaultdict(int)
        self.current_url = ""
        self.total_scanned = 0
        self.content_hashes = defaultdict(list)
        self.robots_parser = None
        self.internal_links_graph = defaultdict(set)  # Граф внутренних ссылок
        
        # Настройки автосохранения и прогресса
        self.save_interval = 500  # Сохранять каждые 500 ссылок
        self.last_save_count = 0
        self.estimated_total_urls = 0  # Оценка общего количества URL
        self.scan_start_time = None
        self.progress_data = {
            'scanned': 0,
            'found': 0,
            'errors': 0,
            'start_time': None,
            'estimated_completion': None
        }
        
        # Инициализация анимации лягушки
        self.current_frame = 0
        self.frog_frames = [
            r"""
    [green]  ⋱(◉ᴥ◉)⋰  [/green]
    """,
            r"""
    [green]  ⋱(◉‿◉)⋰  [/green]
    """,
            r"""
    [green]  ⋱(◉ᴗ◉)⋰  [/green]
    """
        ]
        
        self.headers = {
            'User-Agent': 'SEOFrog/1.0 (+https://example.com/bot)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }

        # Настройки сканирования
        self.config = {
            'follow_robots_txt': True,
            'check_images': True,
            'check_css': True,
            'check_js': True,
            'max_depth': 10,
            'respect_canonical': True,
            'find_duplicates': True,
            'check_schema': True,
            'check_social_tags': True,
            'check_hreflang': True,
            'analyze_performance': True,
            'max_response_time': 5,
            'min_word_count': 300,
            'main_domain_only': True,
            'calculate_pagerank': True,
            'pagerank_damping': 0.85,
            'pagerank_iterations': 20,  # Увеличено для лучшей точности
        }

        # Структуры для хранения ошибок
        self.not_found_urls = []
        self.error_urls = []
        self.error_sources = defaultdict(list)
        self.redirects = {}

        # Логирование
        self.logs = []
        self.max_logs = 8
        self.error_log_file = "seo_errors.log"
        
        # Очищаем файл логов при старте
        with open(self.error_log_file, 'w', encoding='utf-8') as f:
            f.write(f"SEO Frog Scanner Error Log - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("-" * 80 + "\n\n")

    def get_main_domain(self, url: str) -> str:
        """Извлекает основной домен из URL (без поддоменов и www)"""
        parsed = urlparse(url)
        domain = parsed.netloc.lower().replace('www.', '')
        domain_parts = domain.split('.')
        
        # Для российских доменов типа .com.ru, .net.ru и т.д.
        if len(domain_parts) >= 3 and domain_parts[-2] in ['com', 'net', 'org', 'edu', 'gov']:
            return '.'.join(domain_parts[-3:])
        elif len(domain_parts) >= 2:
            return '.'.join(domain_parts[-2:])
        return domain

    def is_main_domain_only(self, url: str) -> bool:
        """Улучшенная проверка основного домена"""
        if not self.config['main_domain_only']:
            return True
        
        parsed = urlparse(url)
        url_domain = parsed.netloc.lower().replace('www.', '')
        url_main_domain = self.get_main_domain(url)
        
        # Проверяем, что это тот же основной домен
        if url_main_domain != self.main_domain:
            return False
        
        # Проверяем, что нет поддоменов (кроме www)
        url_parts = url_domain.split('.')
        main_parts = self.main_domain.split('.')
        
        # Если количество частей больше, чем у основного домена, это поддомен
        return len(url_parts) <= len(main_parts)

    def normalize_url(self, url: str) -> str:
        """Нормализация URL для единообразия"""
        parsed = urlparse(url)
        
        # Убираем фрагменты (#)
        normalized = f"{parsed.scheme}://{parsed.netloc.lower()}{parsed.path}"
        
        # Добавляем query параметры если есть
        if parsed.query:
            normalized += f"?{parsed.query}"
        
        # Убираем trailing slash для не-корневых страниц
        if normalized.endswith('/') and normalized.count('/') > 3:
            normalized = normalized[:-1]
        
        return normalized

    def build_internal_links_graph(self):
        """Строит граф внутренних ссылок для расчета PageRank"""
        self.internal_links_graph = defaultdict(set)
        
        # Сбрасываем счетчики входящих ссылок
        for page_data in self.pages_data.values():
            page_data.internal_links_count = 0
        
        for url, page_data in self.pages_data.items():
            # Добавляем все исходящие внутренние ссылки
            for outlink in page_data.outlinks:
                normalized_outlink = self.normalize_url(outlink)
                if normalized_outlink in self.pages_data:
                    self.internal_links_graph[url].add(normalized_outlink)
                    # Увеличиваем счетчик входящих ссылок
                    self.pages_data[normalized_outlink].internal_links_count += 1

    def update_internal_links_for_page(self, page_url: str, page_data: PageSEOData):
        """Обновляет граф внутренних ссылок для конкретной страницы"""
        outgoing_count = 0
        incoming_count = 0
        
        # Добавляем исходящие ссылки от этой страницы
        for outlink in page_data.outlinks:
            normalized_outlink = self.normalize_url(outlink)
            if normalized_outlink in self.pages_data:
                self.internal_links_graph[page_url].add(normalized_outlink)
                # Увеличиваем счетчик входящих ссылок
                self.pages_data[normalized_outlink].internal_links_count += 1
                outgoing_count += 1
        
        # Проверяем, есть ли ссылки НА эту страницу от других уже проанализированных страниц
        for other_url, other_data in self.pages_data.items():
            if other_url != page_url:
                for outlink in other_data.outlinks:
                    normalized_outlink = self.normalize_url(outlink)
                    if normalized_outlink == page_url:
                        self.internal_links_graph[other_url].add(page_url)
                        page_data.internal_links_count += 1
                        incoming_count += 1
        
        # Отладочная информация (только для первых нескольких страниц)
        if len(self.pages_data) <= 10:
            short_url = self.get_short_url(page_url)
            self.add_log(f"🔗 {short_url}: {outgoing_count} исходящих, {incoming_count} входящих", "info")

    def calculate_internal_pagerank(self):
        """Улучшенный расчет внутреннего PageRank"""
        if not self.config['calculate_pagerank'] or not self.pages_data:
            return

        self.add_log("Строим граф внутренних ссылок...", "info")
        self.build_internal_links_graph()
        
        self.add_log("Начинаем расчет внутреннего PageRank...", "info")
        
        urls = list(self.pages_data.keys())
        n_pages = len(urls)
        
        # Инициализируем PageRank равномерно
        pagerank = {url: 1.0 / n_pages for url in urls}
        damping_factor = self.config['pagerank_damping']
        iterations = self.config['pagerank_iterations']
        
        # Итеративный расчет PageRank
        for iteration in range(iterations):
            new_pagerank = {}
            
            for target_url in urls:
                # Базовая вероятность (random surfer model)
                base_rank = (1 - damping_factor) / n_pages
                
                # Ранг от входящих ссылок
                incoming_rank = 0.0
                
                for source_url in urls:
                    if target_url in self.internal_links_graph[source_url]:
                        # Количество исходящих ссылок с исходной страницы
                        outgoing_count = len(self.internal_links_graph[source_url])
                        if outgoing_count > 0:
                            # Передаем часть PageRank пропорционально
                            incoming_rank += pagerank[source_url] / outgoing_count
                
                new_pagerank[target_url] = base_rank + damping_factor * incoming_rank
            
            # Проверяем сходимость
            max_diff = max(abs(new_pagerank[url] - pagerank[url]) for url in urls)
            pagerank = new_pagerank
            
            if (iteration + 1) % 5 == 0:
                self.add_log(f"PageRank итерация {iteration + 1}/{iterations}, сходимость: {max_diff:.6f}", "info")
            
            # Если достигнута сходимость, можно остановиться
            if max_diff < 1e-6:
                self.add_log(f"PageRank сошелся на итерации {iteration + 1}", "success")
                break
        
        # Нормализуем результаты
        total_rank = sum(pagerank.values())
        if total_rank > 0:
            for url in urls:
                pagerank[url] = (pagerank[url] / total_rank) * n_pages
        
        # Обновляем данные страниц
        for url, rank in pagerank.items():
            self.pages_data[url].page_rank = rank
        
        # Показываем топ-страницы
        sorted_pages = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)
        
        self.add_log(f"PageRank рассчитан! Топ-5 страниц:", "success")
        for i, (url, rank) in enumerate(sorted_pages[:5]):
            short_url = self.get_short_url(url)
            incoming_links = self.pages_data[url].internal_links_count
            self.add_log(f"  {i+1}. {short_url}: {rank:.4f} ({incoming_links} входящих)", "info")
        
        # Отладочная информация о графе
        total_links = sum(len(links) for links in self.internal_links_graph.values())
        self.add_log(f"📊 Граф внутренних ссылок: {len(self.pages_data)} страниц, {total_links} связей", "info")
        
        return pagerank

    def get_short_url(self, url: str) -> str:
        """Получает короткую версию URL для отображения"""
        parsed = urlparse(url)
        path_parts = [p for p in parsed.path.split('/') if p]
        
        if not path_parts:
            return "Главная"
        elif len(path_parts) == 1:
            return path_parts[0]
        else:
            return f".../{path_parts[-1]}"

    async def analyze_page(self, session: aiohttp.ClientSession, url: str, html: str, response) -> PageSEOData:
        """Анализ страницы и сбор SEO-данных"""
        start_time = time.time()
        soup = BeautifulSoup(html, 'html.parser')
        
        # Базовые данные
        page_data = PageSEOData(
            url=url,
            status_code=response.status,
            content_type=response.headers.get('content-type', ''),
            response_time=time.time() - start_time
        )

        try:
            # Title и Meta Description
            if soup.title:
                page_data.title = soup.title.string.strip() if soup.title.string else ""
            
            meta_desc = soup.find('meta', {'name': 'description'})
            if meta_desc and meta_desc.get('content'):
                page_data.meta_description = meta_desc['content'].strip()

            # Заголовки
            page_data.h1 = [h1.get_text(strip=True) for h1 in soup.find_all('h1')]
            page_data.h2 = [h2.get_text(strip=True) for h2 in soup.find_all('h2')]

            # Canonical и Robots meta
            canonical = soup.find('link', {'rel': 'canonical'})
            page_data.canonical = canonical['href'] if canonical else ""
            
            robots_meta = soup.find('meta', {'name': 'robots'})
            page_data.robots_meta = robots_meta['content'] if robots_meta else ""

            # Подсчет слов и размер контента
            text_elements = []
            for tag in ['p', 'div', 'span', 'article', 'section', 'main']:
                text_elements.extend([elem.get_text(strip=True) for elem in soup.find_all(tag)])
            text_content = ' '.join(text_elements)
            page_data.word_count = len(re.findall(r'\w+', text_content))
            page_data.content_length = len(html)

            # Хеш контента для поиска дубликатов
            content_hash = hashlib.md5(text_content.encode('utf-8')).hexdigest()
            page_data.content_hash = content_hash
            if content_hash in self.content_hashes and self.content_hashes[content_hash]:
                page_data.duplicate_content = True
            self.content_hashes[content_hash].append(url)

            # Анализ изображений
            if self.config['check_images']:
                for img in soup.find_all('img'):
                    img_data = {
                        'src': img.get('src', ''),
                        'alt': img.get('alt', ''),
                        'title': img.get('title', ''),
                    }
                    if img_data['src']:
                        img_data['src'] = urljoin(url, img_data['src'])
                        page_data.images.append(img_data)

            # Schema.org
            if self.config['check_schema']:
                schema_tags = soup.find_all('script', {'type': 'application/ld+json'})
                page_data.schema_org = [tag.string for tag in schema_tags if tag.string]

            # Open Graph
            if self.config['check_social_tags']:
                for og in soup.find_all('meta', attrs={'property': re.compile('^og:')}):
                    page_data.open_graph[og['property']] = og.get('content', '')

            # Twitter Cards
            if self.config['check_social_tags']:
                for twitter in soup.find_all('meta', attrs={'name': re.compile('^twitter:')}):
                    page_data.twitter_cards[twitter['name']] = twitter.get('content', '')

            # Hreflang
            if self.config['check_hreflang']:
                for hreflang in soup.find_all('link', {'rel': 'alternate', 'hreflang': True}):
                    page_data.hreflang[hreflang['hreflang']] = hreflang['href']

            # Улучшенный сбор ссылок
            for link in soup.find_all('a', href=True):
                href = link['href'].strip()
                if not href or href.startswith(('#', 'mailto:', 'tel:', 'javascript:', 'data:')):
                    continue
                
                full_url = urljoin(url, href)
                normalized_url = self.normalize_url(full_url)
                
                # Проверяем, является ли ссылка внутренней
                if self.is_main_domain_only(normalized_url):
                    page_data.outlinks.append(normalized_url)
                else:
                    page_data.inlinks.append(normalized_url)

        except Exception as e:
            self.log_error(f"Ошибка при анализе {url}: {str(e)}")
            self.add_log(f"Ошибка при анализе {url}", "error")

        return page_data

    async def fetch_robots_txt(self, session):
        """Загрузка и парсинг robots.txt"""
        robots_url = urljoin(self.start_url, '/robots.txt')
        try:
            async with session.get(robots_url) as response:
                if response.status == 200:
                    content = await response.text()
                    self.robots_parser = RobotFileParser(robots_url)
                    self.robots_parser.set_url(robots_url)
                    self.robots_parser.parse(content.splitlines())
                    self.add_log("robots.txt загружен успешно", "success")
                else:
                    self.log_error(f"robots.txt не найден (статус {response.status})")
                    self.add_log("robots.txt не найден", "warning")
        except Exception as e:
            self.log_error(f"Ошибка при загрузке robots.txt: {e}")
            self.add_log("Ошибка при загрузке robots.txt", "warning")
            self.robots_parser = None

    def can_fetch(self, url: str) -> bool:
        """Проверка разрешения сканирования URL в robots.txt"""
        if not self.config['follow_robots_txt'] or not self.robots_parser:
            return True
        return self.robots_parser.can_fetch(self.headers['User-Agent'], url)

    def generate_seo_table(self) -> Table:
        """Создание таблицы с SEO-данными"""
        table = Table(box=box.ROUNDED, title="🔍 SEO Анализ последних страниц")
        table.add_column("URL", style="cyan", width=40)
        table.add_column("Заголовок", width=30)
        table.add_column("Статус", justify="center")
        table.add_column("H1", width=20)
        table.add_column("Описание", width=30)
        table.add_column("Проблемы", style="red")

        # Показываем последние 5 проанализированных страниц
        for url, data in list(self.pages_data.items())[-5:]:
            issues = []
            
            if not data.title:
                issues.append("Нет Title")
            elif len(data.title) > 60:
                issues.append("Длинный Title")
                
            if not data.meta_description:
                issues.append("Нет Meta")
            elif len(data.meta_description) > 160:
                issues.append("Длинное описание")
                
            if not data.h1:
                issues.append("Нет H1")
            elif len(data.h1) > 1:
                issues.append("Много H1")

            if data.duplicate_content:
                issues.append("Дубликат")

            if data.word_count < self.config['min_word_count']:
                issues.append("Мало текста")

            status_color = self.get_status_color(data.status_code)
            
            table.add_row(
                Text(self.get_short_url(url), overflow="ellipsis"),
                Text(data.title[:30] + "..." if data.title else "", overflow="ellipsis"),
                f"[{status_color}]{data.status_code}[/{status_color}]",
                Text(data.h1[0][:20] + "..." if data.h1 else "", overflow="ellipsis"),
                Text(data.meta_description[:30] + "..." if data.meta_description else "", overflow="ellipsis"),
                ", ".join(issues) if issues else "[green]OK[/green]"
            )
        return table

    def generate_stats_table(self) -> Table:
        """Создание таблицы статистики"""
        table = Table(box=box.ROUNDED, title="📊 Статистика сканирования")
        table.add_column("Метрика", style="cyan")
        table.add_column("Значение", justify="right")

        total_pages = len(self.pages_data)
        issues_count = sum(1 for data in self.pages_data.values() if not data.title or not data.meta_description or not data.h1)
        duplicate_count = sum(1 for data in self.pages_data.values() if data.duplicate_content)
        
        table.add_row("Всего страниц", str(total_pages))
        table.add_row("Основной домен", f"[blue]{self.main_domain}[/blue]")
        table.add_row("Страниц с ошибками", f"[red]{issues_count}[/red]")
        table.add_row("404 ошибки", f"[red]{len(self.not_found_urls)}[/red]")
        table.add_row("Редиректы", f"[yellow]{len(self.redirects)}[/yellow]")
        table.add_row("Дубликаты", f"[yellow]{duplicate_count}[/yellow]")
        
        # Статистика по кодам ответа
        for status, count in sorted(self.status_counts.items()):
            color = self.get_status_color(status)
            table.add_row(f"Статус {status}", f"[{color}]{count}[/{color}]")
        
        table.add_row("Средний размер", f"{sum(d.content_length for d in self.pages_data.values()) // (total_pages or 1)} бай")
        table.add_row("Среднее время ответа", f"{sum(d.response_time for d in self.pages_data.values()) / (total_pages or 1):.2f} сек")
        
        return table

    def generate_pagerank_table(self) -> Table:
        """Создание таблицы с топ-страницами по PageRank"""
        table = Table(box=box.ROUNDED, title="🏆 Топ-10 страниц по PageRank")
        table.add_column("Ранг", style="cyan", justify="center")
        table.add_column("URL", style="blue", width=40)
        table.add_column("PageRank", justify="right")
        table.add_column("Входящие", justify="center")
        table.add_column("Исходящие", justify="center")

        # Сортируем страницы по PageRank
        sorted_pages = sorted(
            self.pages_data.items(), 
            key=lambda x: x[1].page_rank, 
            reverse=True
        )[:10]

        for i, (url, data) in enumerate(sorted_pages, 1):
            short_url = self.get_short_url(url)
            
            table.add_row(
                str(i),
                Text(short_url, overflow="ellipsis"),
                f"{data.page_rank:.4f}",
                str(data.internal_links_count),
                str(len(data.outlinks))
            )
        
        return table

    def generate_display(self) -> Layout:
        """Создание основного интерфейса"""
        layout = Layout()
        
        layout.split_column(
            Layout(name="header", size=7),
            Layout(name="progress", size=4),
            Layout(name="main", size=18),
            Layout(name="footer", size=3),
            Layout(name="log", size=10)
        )

        # Заголовок с лягушкой
        self.current_frame = (self.current_frame + 1) % len(self.frog_frames)
        header_content = Panel(
            f"{self.frog_frames[self.current_frame]}\n"
            f"🌐 SEO Анализ сайта: {self.main_domain}\n"
            f"📑 Проанализировано страниц: {self.total_scanned}",
            title="SEO Frog Scanner",
            style="bold green",
            border_style="green"
        )
        layout["header"].update(header_content)

        # Основной контент
        main_layout = Layout()
        main_layout.split_row(
            Layout(
                Panel(
                    self.generate_stats_table(),
                    title="📊 Статистика",
                    border_style="blue"
                ),
                size=40
            ),
            Layout(
                Panel(
                    self.generate_seo_table(),
                    title="🔍 Последние страницы",
                    border_style="cyan"
                ),
                size=60
            )
        )
        
        # Добавляем таблицу PageRank, если есть данные
        if self.pages_data and any(data.page_rank > 0 for data in self.pages_data.values()):
            pagerank_layout = Layout()
            pagerank_layout.split_column(
                main_layout,
                Layout(
                    Panel(
                        self.generate_pagerank_table(),
                        title="🏆 PageRank Анализ",
                        border_style="green"
                    ),
                    size=12
                )
            )
            layout["main"].update(pagerank_layout)
        else:
            layout["main"].update(main_layout)

        # Прогресс бар
        if self.progress_data['start_time']:
            elapsed_time = time.time() - self.progress_data['start_time']
            if self.progress_data['scanned'] > 0:
                avg_time_per_url = elapsed_time / self.progress_data['scanned']
                remaining_urls = max(0, self.estimated_total_urls - self.progress_data['scanned'])
                estimated_remaining = remaining_urls * avg_time_per_url
                
                progress_percent = min(100, (self.progress_data['scanned'] / max(1, self.estimated_total_urls)) * 100)
                
                progress_content = Panel(
                    f"📊 Прогресс: {self.progress_data['scanned']}/{self.estimated_total_urls} ({progress_percent:.1f}%)\n"
                    f"⏱️ Прошло времени: {elapsed_time:.0f}с | "
                    f"⏳ Осталось: {estimated_remaining:.0f}с | "
                    f"📈 Найдено: {self.progress_data['found']} | "
                    f"❌ Ошибок: {self.progress_data['errors']}",
                    title="🔄 Статус сканирования",
                    border_style="green"
                )
            else:
                progress_content = Panel(
                    "🔄 Инициализация сканирования...",
                    title="🔄 Статус сканирования",
                    border_style="yellow"
                )
        else:
            progress_content = Panel(
                "⏳ Ожидание начала сканирования...",
                title="🔄 Статус сканирования",
                border_style="blue"
            )
        layout["progress"].update(progress_content)

        # Футер
        footer_content = Panel(
            f"🔍 Сканирование: {self.get_short_url(self.current_url) if self.current_url else 'Ожидание...'}",
            style="bold blue",
            border_style="blue"
        )
        layout["footer"].update(footer_content)

        # Логи
        recent_logs = self.get_recent_logs()
        log_content = Panel(
            "\n".join(recent_logs),
            title="📝 Последние действия",
            border_style="yellow"
        )
        layout["log"].update(log_content)

        return layout
    
    async def scan_site(self, session: aiohttp.ClientSession, live: Live):
        """Основной метод сканирования сайта"""
        # Инициализация прогресса
        self.progress_data['start_time'] = time.time()
        self.estimate_total_urls()
        
        async def process_url(url: str, depth: int = 0, source_url: str = None):
            await asyncio.sleep(0.3)  # Уменьшенная задержка
            
            if depth > self.config['max_depth'] or url in self.visited_urls:
                return

            # Нормализация URL
            normalized_url = self.normalize_url(url)
            
            # Проверяем принадлежность к основному домену
            if not self.is_main_domain_only(normalized_url):
                return
            
            if normalized_url in self.visited_urls:
                return

            self.current_url = normalized_url
            self.visited_urls.add(normalized_url)
            
            try:
                async with session.get(normalized_url, headers=self.headers, timeout=30, allow_redirects=True) as response:
                    self.status_counts[response.status] += 1
                    
                    # Обработка редиректов
                    if response.history:
                        redirect_chain = ' -> '.join([str(r.status) for r in response.history] + [str(response.status)])
                        self.add_log(f"Редирект: {self.get_short_url(normalized_url)} ({redirect_chain})", "warning")
                        self.redirects[normalized_url] = {
                            'from': normalized_url,
                            'to': str(response.url),
                            'chain': redirect_chain
                        }

                    # Обработка ошибок
                    if response.status == 404:
                        error_msg = f"404: {normalized_url} (источник: {source_url or 'Начальная страница'})"
                        self.log_error(error_msg)
                        self.add_log(f"404: {self.get_short_url(normalized_url)}", "error")
                        self.not_found_urls.append({'url': normalized_url, 'source': source_url or 'Начальная страница'})
                        self.error_sources[normalized_url].append(source_url or 'Начальная страница')
                        self.estimate_total_urls()  # Обновляем прогресс
                        return
                    elif response.status >= 400:
                        error_msg = f"Ошибка {response.status}: {normalized_url} (источник: {source_url or 'Начальная страница'})"
                        self.log_error(error_msg)
                        self.add_log(f"Ошибка {response.status}: {self.get_short_url(normalized_url)}", "error")
                        self.error_urls.append({
                            'url': normalized_url, 
                            'status': response.status, 
                            'source': source_url or 'Начальная страница'
                        })
                        self.error_sources[normalized_url].append(source_url or 'Начальная страница')
                        self.estimate_total_urls()  # Обновляем прогресс
                        return
                    else:
                        self.add_log(f"Сканируем: {self.get_short_url(normalized_url)}", "info")

                    # Проверяем content-type
                    content_type = response.headers.get('content-type', '').lower()
                    if 'text/html' not in content_type:
                        return

                    html = await response.text()
                    
                    # Анализируем страницу
                    page_data = await self.analyze_page(session, normalized_url, html, response)
                    self.pages_data[normalized_url] = page_data
                    self.total_scanned += 1
                    
                    # Обновляем граф внутренних ссылок для новой страницы
                    self.update_internal_links_for_page(normalized_url, page_data)
                    
                    # Обновляем прогресс и проверяем автосохранение
                    self.estimate_total_urls()
                    await self.auto_save_check()
                    
                    # Обновляем отображение
                    live.update(self.generate_display())
                    
                    # Собираем ссылки для дальнейшего сканирования
                    soup = BeautifulSoup(html, 'html.parser')
                    links = set()
                    
                    # Ищем все ссылки
                    for link in soup.find_all('a', href=True):
                        href = link.get('href', '').strip()
                        if href and not href.startswith(('#', 'mailto:', 'tel:', 'javascript:', 'data:')):
                            full_url = urljoin(normalized_url, href)
                            normalized_link = self.normalize_url(full_url)
                            if (self.is_main_domain_only(normalized_link) and 
                                self.can_fetch(normalized_link) and 
                                normalized_link not in self.visited_urls):
                                links.add(normalized_link)
                    
                    # Обрабатываем ссылки небольшими группами
                    tasks = []
                    for next_url in links:
                        tasks.append(process_url(next_url, depth + 1, normalized_url))
                    
                    if tasks:
                        # Ограничиваем количество одновременных запросов
                        for i in range(0, len(tasks), 3):
                            batch = tasks[i:i+3]
                            await asyncio.gather(*batch, return_exceptions=True)
                            
                            # Обновляем прогресс после каждой группы
                            self.estimate_total_urls()
                            live.update(self.generate_display())
                        
            except asyncio.TimeoutError:
                error_msg = f"Таймаут: {normalized_url}"
                self.log_error(error_msg)
                self.add_log(f"Таймаут: {self.get_short_url(normalized_url)}", "error")
                self.estimate_total_urls()  # Обновляем прогресс
            except Exception as e:
                error_msg = f"Ошибка при обработке {normalized_url}: {str(e)}"
                self.log_error(error_msg)
                self.add_log(f"Ошибка: {self.get_short_url(normalized_url)}", "error")
                self.estimate_total_urls()  # Обновляем прогресс
        
        # Начинаем сканирование с начального URL
        await process_url(self.start_url)

    async def export_results(self, is_autosave: bool = False):
        """Экспорт результатов в различные форматы"""
        if is_autosave:
            self.add_log(f"🔄 Автосохранение результатов ({len(self.pages_data)} страниц)...", "info")
        else:
            self.add_log("Экспортируем результаты...", "info")
        
        # Основной отчет
        main_data = []
        for url, data in self.pages_data.items():
            main_data.append({
                'URL': url,
                'Статус': data.status_code,
                'Заголовок': data.title,
                'Мета-описание': data.meta_description,
                'H1': ' | '.join(data.h1),
                'Количество слов': data.word_count,
                'Время ответа (сек)': f"{data.response_time:.2f}",
                'Размер страницы (байт)': data.content_length,
                'Дубликат': 'Да' if data.duplicate_content else 'Нет',
                'PageRank': f"{data.page_rank:.6f}",
                'Входящие внутренние ссылки': data.internal_links_count,
                'Исходящие внутренние ссылки': len(data.outlinks),
                'Внешние ссылки': len(data.inlinks),
                'Canonical': data.canonical,
                'Robots Meta': data.robots_meta,
                'Изображений': len(data.images),
                'Schema.org': len(data.schema_org),
                'Open Graph': len(data.open_graph),
                'Twitter Cards': len(data.twitter_cards),
                'Hreflang': len(data.hreflang),
                'Проблемы': self.get_page_issues(data)
            })

        if main_data:
            df_main = pd.DataFrame(main_data)
            
            # Для автосохранения используем временные файлы
            if is_autosave:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f'seo_отчет_основной_autosave_{timestamp}.xlsx'
            else:
                filename = 'seo_отчет_основной.xlsx'
            
            df_main.to_excel(filename, index=False)

        # Отчет по изображениям
        images_data = []
        for url, data in self.pages_data.items():
            for img in data.images:
                images_data.append({
                    'URL страницы': url,
                    'URL изображения': img['src'],
                    'Alt текст': img['alt'],
                    'Title': img['title'],
                    'Есть Alt': 'Да' if img['alt'] else 'Нет'
                })

        if images_data:
            df_images = pd.DataFrame(images_data)
            if is_autosave:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f'seo_отчет_изображения_autosave_{timestamp}.xlsx'
            else:
                filename = 'seo_отчет_изображения.xlsx'
            df_images.to_excel(filename, index=False)

        # Отчет по дубликатам
        duplicates_data = []
        duplicate_groups = {}
        group_id = 1
        
        for content_hash, urls in self.content_hashes.items():
            if len(urls) > 1:
                duplicate_groups[content_hash] = group_id
                for url in urls:
                    duplicates_data.append({
                        'URL': url,
                        'Группа дубликатов': group_id,
                        'Хеш контента': content_hash,
                        'Заголовок': self.pages_data[url].title if url in self.pages_data else '',
                        'Количество слов': self.pages_data[url].word_count if url in self.pages_data else 0,
                        'Всего в группе': len(urls)
                    })
                group_id += 1

        if duplicates_data:
            df_duplicates = pd.DataFrame(duplicates_data)
            df_duplicates = df_duplicates.sort_values(['Группа дубликатов', 'URL'])
            if is_autosave:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f'seo_отчет_дубликаты_autosave_{timestamp}.xlsx'
            else:
                filename = 'seo_отчет_дубликаты.xlsx'
            df_duplicates.to_excel(filename, index=False)

        # Отчет по PageRank
        if self.config['calculate_pagerank'] and self.pages_data:
            pagerank_data = []
            sorted_pages = sorted(
                self.pages_data.items(), 
                key=lambda x: x[1].page_rank, 
                reverse=True
            )
            
            for rank_position, (url, data) in enumerate(sorted_pages, 1):
                pagerank_data.append({
                    'Позиция': rank_position,
                    'URL': url,
                    'PageRank': data.page_rank,
                    'Входящие внутренние ссылки': data.internal_links_count,
                    'Исходящие внутренние ссылки': len(data.outlinks),
                    'Внешние ссылки': len(data.inlinks),
                    'Заголовок': data.title,
                    'Статус': data.status_code,
                    'Количество слов': data.word_count,
                    'Время ответа (сек)': f"{data.response_time:.2f}"
                })
            
            if pagerank_data:
                df_pagerank = pd.DataFrame(pagerank_data)
                if is_autosave:
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    filename = f'seo_отчет_pagerank_autosave_{timestamp}.xlsx'
                else:
                    filename = 'seo_отчет_pagerank.xlsx'
                df_pagerank.to_excel(filename, index=False)

        # Отчет по внутренним ссылкам
        internal_links_data = []
        for source_url, target_urls in self.internal_links_graph.items():
            for target_url in target_urls:
                internal_links_data.append({
                    'Источник': source_url,
                    'Цель': target_url,
                    'PageRank источника': self.pages_data[source_url].page_rank if source_url in self.pages_data else 0,
                    'PageRank цели': self.pages_data[target_url].page_rank if target_url in self.pages_data else 0,
                    'Заголовок источника': self.pages_data[source_url].title if source_url in self.pages_data else '',
                    'Заголовок цели': self.pages_data[target_url].title if target_url in self.pages_data else ''
                })

        if internal_links_data:
            df_internal_links = pd.DataFrame(internal_links_data)
            df_internal_links = df_internal_links.sort_values('PageRank цели', ascending=False)
            if is_autosave:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f'seo_отчет_внутренние_ссылки_autosave_{timestamp}.xlsx'
            else:
                filename = 'seo_отчет_внутренние_ссылки.xlsx'
            df_internal_links.to_excel(filename, index=False)

        # Отчет по редиректам
        if self.redirects:
            redirects_data = []
            for redirect_data in self.redirects.values():
                redirects_data.append({
                    'С URL': redirect_data['from'],
                    'На URL': redirect_data['to'],
                    'Цепочка редиректов': redirect_data['chain']
                })
            df_redirects = pd.DataFrame(redirects_data)
            if is_autosave:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f'seo_отчет_редиректы_autosave_{timestamp}.xlsx'
            else:
                filename = 'seo_отчет_редиректы.xlsx'
            df_redirects.to_excel(filename, index=False)

        # Отчет по ошибкам
        if self.error_urls or self.not_found_urls:
            errors_data = []
            
            # 404 ошибки
            for error in self.not_found_urls:
                sources = self.error_sources.get(error['url'], [])
                errors_data.append({
                    'URL': error['url'],
                    'Тип ошибки': '404 Не найдено',
                    'Основной источник': error['source'],
                    'Все источники': ' | '.join(set(sources)) if sources else error['source'],
                    'Количество источников': len(set(sources)) if sources else 1
                })
            
            # Другие ошибки
            for error in self.error_urls:
                sources = self.error_sources.get(error['url'], [])
                errors_data.append({
                    'URL': error['url'],
                    'Тип ошибки': f"Ошибка {error.get('status', 'неизвестно')}",
                    'Основной источник': error['source'],
                    'Все источники': ' | '.join(set(sources)) if sources else error['source'],
                    'Количество источников': len(set(sources)) if sources else 1
                })

            if errors_data:
                df_errors = pd.DataFrame(errors_data)
                df_errors = df_errors.sort_values('Количество источников', ascending=False)
                if is_autosave:
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    filename = f'seo_отчет_ошибки_autosave_{timestamp}.xlsx'
                else:
                    filename = 'seo_отчет_ошибки.xlsx'
                df_errors.to_excel(filename, index=False)

        # Экспорт в XML (Sitemap)
        if not is_autosave:
            self.export_to_xml()

        # Экспорт структуры сайта
        if not is_autosave:
            self.export_site_structure(is_autosave=False)

    def export_to_xml(self):
        """Экспорт в XML sitemap формат"""
        urlset = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
        
        # Сортируем по PageRank для приоритизации
        sorted_pages = sorted(
            self.pages_data.items(), 
            key=lambda x: x[1].page_rank, 
            reverse=True
        )
        
        for url, data in sorted_pages:
            if data.status_code == 200:  # Только успешные страницы
                url_elem = ET.SubElement(urlset, "url")
                ET.SubElement(url_elem, "loc").text = url
                
                # Приоритет на основе PageRank (нормализуем к диапазону 0.1-1.0)
                max_rank = max(d.page_rank for d in self.pages_data.values())
                priority = max(0.1, min(1.0, data.page_rank / max_rank))
                ET.SubElement(url_elem, "priority").text = f"{priority:.1f}"
                
                # Частота изменений на основе уровня вложенности
                depth = len([p for p in urlparse(url).path.split('/') if p])
                if depth <= 1:
                    changefreq = "daily"
                elif depth <= 2:
                    changefreq = "weekly"
                else:
                    changefreq = "monthly"
                ET.SubElement(url_elem, "changefreq").text = changefreq

        tree = ET.ElementTree(urlset)
        tree.write("sitemap.xml", encoding='utf-8', xml_declaration=True)

    def export_site_structure(self, is_autosave: bool = False):
        """Экспорт структуры сайта"""
        structure_data = []
        
        for url, data in self.pages_data.items():
            parsed = urlparse(url)
            path_parts = [p for p in parsed.path.split('/') if p]
            
            structure_data.append({
                'URL': url,
                'Уровень вложенности': len(path_parts),
                'Путь': parsed.path,
                'Родительская страница': '/'.join(parsed.path.split('/')[:-1]) if len(path_parts) > 0 else '/',
                'PageRank': data.page_rank,
                'Входящие ссылки': data.internal_links_count,
                'Заголовок': data.title,
                'Статус': data.status_code
            })
        
        if structure_data:
            df_structure = pd.DataFrame(structure_data)
            df_structure = df_structure.sort_values(['Уровень вложенности', 'PageRank'], ascending=[True, False])
            if is_autosave:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f'seo_отчет_структура_сайта_autosave_{timestamp}.xlsx'
            else:
                filename = 'seo_отчет_структура_сайта.xlsx'
            df_structure.to_excel(filename, index=False)

    def get_page_issues(self, data: PageSEOData) -> str:
        """Получение списка проблем страницы"""
        issues = []
        
        # SEO проблемы
        if not data.title:
            issues.append("Отсутствует Title")
        elif len(data.title) > 60:
            issues.append("Title слишком длинный (>60)")
        elif len(data.title) < 30:
            issues.append("Title слишком короткий (<30)")
        
        if not data.meta_description:
            issues.append("Отсутствует Meta Description")
        elif len(data.meta_description) > 160:
            issues.append("Meta Description слишком длинный (>160)")
        elif len(data.meta_description) < 120:
            issues.append("Meta Description слишком короткий (<120)")
        
        if not data.h1:
            issues.append("Отсутствует H1")
        elif len(data.h1) > 1:
            issues.append("Несколько H1 тегов")
        
        # Контентные проблемы
        if data.duplicate_content:
            issues.append("Дублированный контент")
        
        if data.word_count < self.config['min_word_count']:
            issues.append(f"Мало контента (<{self.config['min_word_count']} слов)")
        
        # Технические проблемы
        if data.response_time > self.config['max_response_time']:
            issues.append("Медленный ответ")
        
        if data.page_rank < 0.0001:  # Очень низкий PageRank
            issues.append("Низкий PageRank")
        
        # Проблемы с изображениями
        images_without_alt = sum(1 for img in data.images if not img.get('alt'))
        if images_without_alt > 0:
            issues.append(f"Изображения без Alt ({images_without_alt})")
        
        return " | ".join(issues) if issues else "Нет проблем"

    def get_status_color(self, status_code: int) -> str:
        """Возвращает цвет для статус кода"""
        if status_code < 300:
            return "green"
        elif status_code < 400:
            return "yellow"
        elif status_code < 500:
            return "red"
        else:
            return "red bold"

    def add_log(self, message: str, level: str = "info"):
        """Добавление записи в лог"""
        timestamp = time.strftime("%H:%M:%S")
        color = {
            "info": "blue",
            "warning": "yellow",
            "error": "red",
            "success": "green"
        }.get(level, "white")
        
        log_entry = f"[{color}]{timestamp} | {message}[/{color}]"
        self.logs.append(log_entry)
        
        if len(self.logs) > self.max_logs:
            self.logs.pop(0)

    def get_recent_logs(self) -> List[str]:
        """Получение последних логов"""
        return self.logs

    def log_error(self, message: str):
        """Записывает ошибку в лог-файл"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(self.error_log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {message}\n")

    async def auto_save_check(self):
        """Проверяет необходимость автосохранения"""
        if len(self.pages_data) - self.last_save_count >= self.save_interval:
            self.add_log(f"🔄 Автосохранение каждые {self.save_interval} страниц...", "info")
            await self.export_results(is_autosave=True)
            self.last_save_count = len(self.pages_data)
            self.add_log(f"✅ Автосохранение завершено ({len(self.pages_data)} страниц)", "success")
            
            # Очищаем старые автосохранения
            self.cleanup_old_autosaves()

    def estimate_total_urls(self):
        """Оценивает общее количество URL на основе найденных ссылок"""
        if not self.pages_data:
            self.estimated_total_urls = 100  # Базовая оценка
            return
        
        # Подсчитываем все уникальные ссылки из всех страниц
        all_links = set()
        for page_data in self.pages_data.values():
            all_links.update(page_data.outlinks)
        
        # Добавляем уже посещенные URL
        all_links.update(self.visited_urls)
        
        # Оценка: если мы нашли много ссылок, но посетили мало, значит их больше
        if len(all_links) > len(self.visited_urls) * 2:
            self.estimated_total_urls = max(self.estimated_total_urls, len(all_links) * 1.5)
        else:
            # Если ссылок мало, возможно мы близки к завершению
            self.estimated_total_urls = max(self.estimated_total_urls, len(all_links) * 1.2)
        
        # Обновляем прогресс
        self.progress_data['scanned'] = len(self.visited_urls)
        self.progress_data['found'] = len(self.pages_data)
        self.progress_data['errors'] = len(self.error_urls) + len(self.not_found_urls)

    def cleanup_old_autosaves(self):
        """Очищает старые файлы автосохранения, оставляя только последние 3"""
        import glob
        import os
        
        # Паттерны для поиска файлов автосохранения
        patterns = [
            'seo_отчет_основной_autosave_*.xlsx',
            'seo_отчет_изображения_autosave_*.xlsx',
            'seo_отчет_дубликаты_autosave_*.xlsx',
            'seo_отчет_pagerank_autosave_*.xlsx',
            'seo_отчет_внутренние_ссылки_autosave_*.xlsx',
            'seo_отчет_редиректы_autosave_*.xlsx',
            'seo_отчет_ошибки_autosave_*.xlsx',
            'seo_отчет_структура_сайта_autosave_*.xlsx'
        ]
        
        for pattern in patterns:
            files = glob.glob(pattern)
            if len(files) > 3:
                # Сортируем по времени создания и удаляем старые
                files.sort(key=os.path.getctime, reverse=True)
                for old_file in files[3:]:
                    try:
                        os.remove(old_file)
                        self.add_log(f"🗑️ Удален старый автосохраненный файл: {old_file}", "info")
                    except Exception as e:
                        self.add_log(f"❌ Ошибка при удалении {old_file}: {e}", "error")

    async def run(self):
        """Запуск сканирования"""
        self.console.clear()
        self.add_log(f"Начало сканирования домена: {self.main_domain}", "info")
        self.add_log(f"Режим: только основной домен {'✓' if self.config['main_domain_only'] else '✗'}", "info")
        
        timeout = aiohttp.ClientTimeout(total=60, connect=10)
        connector = aiohttp.TCPConnector(
            limit=10, 
            force_close=True, 
            enable_cleanup_closed=True,
            limit_per_host=5
        )
        
        try:
            with Live(self.generate_display(), refresh_per_second=2, screen=True) as live:
                async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                    # Загружаем robots.txt
                    await self.fetch_robots_txt(session)
                    
                    # Сканируем сайт
                    await self.scan_site(session, live)

                    # Рассчитываем PageRank после завершения сканирования
                    if self.config['calculate_pagerank'] and self.pages_data:
                        self.calculate_internal_pagerank()

                    # Экспортируем результаты
                    await self.export_results()
            
            # Финальные сообщения
            total_time = time.time() - self.progress_data['start_time'] if self.progress_data['start_time'] else 0
            self.console.print("\n[green]✅ Сканирование завершено успешно![/green]")
            self.console.print(f"[blue]📊 Проанализировано страниц: {self.total_scanned}[/blue]")
            self.console.print(f"[blue]🌐 Основной домен: {self.main_domain}[/blue]")
            self.console.print(f"[blue]⏱️ Общее время: {total_time:.0f} секунд[/blue]")
            self.console.print(f"[blue]📈 Средняя скорость: {self.total_scanned / max(1, total_time):.1f} страниц/сек[/blue]")
            
            if self.pages_data:
                avg_pagerank = sum(d.page_rank for d in self.pages_data.values()) / len(self.pages_data)
                max_pagerank = max(d.page_rank for d in self.pages_data.values())
                self.console.print(f"[blue]🏆 Средний PageRank: {avg_pagerank:.4f}, Максимальный: {max_pagerank:.4f}[/blue]")
            
            self.console.print("\n[blue]📁 Созданные отчеты:[/blue]")
            reports = [
                "seo_отчет_основной.xlsx",
                "seo_отчет_pagerank.xlsx", 
                "seo_отчет_структура_сайта.xlsx",
                "seo_отчет_внутренние_ссылки.xlsx",
                "sitemap.xml"
            ]
            
            # Показываем информацию об автосохранениях
            if self.last_save_count > 0:
                self.console.print(f"[yellow]💾 Автосохранения: {self.last_save_count // self.save_interval} раз (каждые {self.save_interval} страниц)[/yellow]")
            
            # Условные отчеты
            if any(len(data.images) > 0 for data in self.pages_data.values()):
                reports.append("seo_отчет_изображения.xlsx")
            
            if any(data.duplicate_content for data in self.pages_data.values()):
                reports.append("seo_отчет_дубликаты.xlsx")
            
            if self.redirects:
                reports.append("seo_отчет_редиректы.xlsx")
            
            if self.error_urls or self.not_found_urls:
                reports.append("seo_отчет_ошибки.xlsx")
            
            reports.append(self.error_log_file)
            
            for report in reports:
                self.console.print(f"  • {report}")
        
        except KeyboardInterrupt:
            self.console.print("\n[yellow]⚠️ Сканирование прервано пользователем[/yellow]")
            if self.pages_data:
                self.console.print("[blue]💾 Сохраняем частичные результаты...[/blue]")
                await self.export_results()
        except Exception as e:
            error_msg = f"Критическая ошибка: {str(e)}"
            self.log_error(error_msg)
            self.console.print(f"[red]❌ {error_msg}[/red]")
        finally:
            await connector.close()

# Пример использования
if __name__ == "__main__":
    website_url = input("Введите URL сайта для SEO анализа: ")
    scanner = SEOFrogScanner(website_url)
    
    # Можно настроить дополнительные параметры
    print(f"\n🔧 Текущие настройки:")
    print(f"  • Только основной домен: {scanner.config['main_domain_only']}")
    print(f"  • Расчет PageRank: {scanner.config['calculate_pagerank']}")
    print(f"  • Максимальная глубина: {scanner.config['max_depth']}")
    print(f"  • Минимум слов на странице: {scanner.config['min_word_count']}")
    
    # Запуск сканирования
    asyncio.run(scanner.run())