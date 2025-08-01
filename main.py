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
    page_rank: float = 1.0  # Добавляем поле для внутреннего PageRank
    
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
        
        # Нормализация домена (убираем www если есть)
        self.domain = urlparse(start_url).netloc.replace('www.', '')
        
        self.visited_urls: Set[str] = set()
        self.pages_data: Dict[str, PageSEOData] = {}
        self.console = Console()
        self.status_counts = defaultdict(int)
        self.current_url = ""
        self.total_scanned = 0
        self.content_hashes = defaultdict(list)
        self.robots_parser = None
        
        # Инициалиация анимации лягушки
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
            'max_response_time': 5,  # seconds
            'min_word_count': 300,
            'main_domain_only': True,  # Сканировать только основной домен (без поддоменов)
            'calculate_pagerank': True,  # Рассчитывать внутренний PageRank
            'pagerank_damping': 0.85,  # Коэффициент затухания для PageRank
            'pagerank_iterations': 10,  # Количество итераций для расчета PageRank
        }

        # Модифицируем структуру для хранения ошибок
        self.not_found_urls = []  # Для 404 ошибок
        self.error_urls = []      # Для других ошибок
        self.error_sources = defaultdict(list)  # Для хранения источников ошибок
        self.redirects = {}       # Для редиректов

        # Добавляем хранение логов
        self.logs = []
        self.max_logs = 8  # Максимальное количество отображаемых логов

        # Добавляем файл для логирования ошибок
        self.error_log_file = "seo_errors.log"
        # Очищаем файл логов при старте
        with open(self.error_log_file, 'w', encoding='utf-8') as f:
            f.write(f"SEO Frog Scanner Error Log - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("-" * 80 + "\n\n")

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

    def get_main_domain(self, url: str) -> str:
        """Извлекает основной домен из URL (без поддоменов)"""
        parsed = urlparse(url)
        domain_parts = parsed.netloc.replace('www.', '').split('.')
        if len(domain_parts) >= 2:
            # Берем последние две части домена (например, example.com из sub.example.com)
            return '.'.join(domain_parts[-2:])
        return parsed.netloc.replace('www.', '')

    def is_main_domain_only(self, url: str) -> bool:
        """Проверяет, является ли URL основным доменом (без поддоменов)"""
        if not self.config['main_domain_only']:
            return True
        
        parsed = urlparse(url)
        domain_parts = parsed.netloc.replace('www.', '').split('.')
        
        # Если домен имеет более 2 частей, это поддомен
        if len(domain_parts) > 2:
            return False
        
        # Проверяем, что это тот же основной домен
        main_domain = self.get_main_domain(url)
        return main_domain == self.get_main_domain(self.start_url)

    def calculate_internal_pagerank(self):
        """Рассчитывает внутренний PageRank для всех страниц"""
        if not self.config['calculate_pagerank'] or not self.pages_data:
            return
        
        self.add_log("Начинаем расчет внутреннего PageRank...", "info")
        
        # Инициализируем PageRank для всех страниц
        urls = list(self.pages_data.keys())
        pagerank = {url: 1.0 / len(urls) for url in urls}
        
        # Создаем матрицу переходов
        transition_matrix = {}
        for url in urls:
            page_data = self.pages_data[url]
            outlinks = [link for link in page_data.outlinks if link in self.pages_data]
            
            if outlinks:
                # Равномерно распределяем вес между исходящими ссылками
                weight_per_link = 1.0 / len(outlinks)
                transition_matrix[url] = {outlink: weight_per_link for outlink in outlinks}
            else:
                # Если нет исходящих ссылок, распределяем вес между всеми страницами
                transition_matrix[url] = {other_url: 1.0 / len(urls) for other_url in urls}
        
        # Итеративный расчет PageRank
        damping_factor = self.config['pagerank_damping']
        iterations = self.config['pagerank_iterations']
        
        for iteration in range(iterations):
            new_pagerank = {}
            
            for url in urls:
                # Формула PageRank: PR(p) = (1-d)/N + d * sum(PR(i)/C(i))
                # где d - коэффициент затухания, N - количество страниц, C(i) - количество исходящих ссылок
                
                # Базовая вероятность (случайный переход)
                base_prob = (1 - damping_factor) / len(urls)
                
                # Вероятность перехода по ссылкам
                link_prob = 0.0
                for source_url, transitions in transition_matrix.items():
                    if url in transitions:
                        link_prob += pagerank[source_url] * transitions[url]
                
                new_pagerank[url] = base_prob + damping_factor * link_prob
            
            # Нормализация
            total_rank = sum(new_pagerank.values())
            if total_rank > 0:
                for url in urls:
                    new_pagerank[url] /= total_rank
            
            pagerank = new_pagerank
            
            if (iteration + 1) % 5 == 0:
                self.add_log(f"PageRank итерация {iteration + 1}/{iterations}", "info")
        
        # Обновляем PageRank в данных страниц
        for url, rank in pagerank.items():
            self.pages_data[url].page_rank = rank
        
        # Сортируем страницы по PageRank для отображения топ-страниц
        sorted_pages = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)
        
        self.add_log(f"PageRank рассчитан! Топ-5 страниц:", "success")
        for i, (url, rank) in enumerate(sorted_pages[:5]):
            short_url = url.split('/')[-1] if url.split('/')[-1] else url.split('/')[-2]
            self.add_log(f"  {i+1}. {short_url}: {rank:.4f}", "info")
        
        return pagerank

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
            for tag in ['p', 'div', 'span', 'article']:
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

            # Сбор внутренних и внеших ссылок
            for link in soup.find_all('a', href=True):
                href = urljoin(url, link['href'])
                if urlparse(href).netloc == self.domain:
                    page_data.outlinks.append(href)
                else:
                    page_data.inlinks.append(href)

        except Exception as e:
            self.log_error(f"Ошибка при анализе {url}: {str(e)}")
            self.add_log(f"Ошибка при анализе {url}", "error")  # Краткое сообщение для интерфейса

        return page_data

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
                Text(url, overflow="ellipsis"),
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
        table.add_column("Входящие ссылки", justify="center")
        table.add_column("Исходящие ссылки", justify="center")

        # Сортируем страницы по PageRank
        sorted_pages = sorted(
            self.pages_data.items(), 
            key=lambda x: x[1].page_rank, 
            reverse=True
        )[:10]

        for i, (url, data) in enumerate(sorted_pages, 1):
            short_url = url.split('/')[-1] if url.split('/')[-1] else url.split('/')[-2]
            if not short_url:
                short_url = url.split('/')[-3] if len(url.split('/')) > 2 else url
            
            table.add_row(
                str(i),
                Text(short_url, overflow="ellipsis"),
                f"{data.page_rank:.4f}",
                str(len(data.inlinks)),
                str(len(data.outlinks))
            )
        
        return table

    def generate_display(self) -> Layout:
        """Создание основного интерфейса"""
        layout = Layout()
        
        # Создаем фиксированную высоту для каждой секции
        layout.split_column(
            Layout(name="header", size=7),
            Layout(name="main", size=20),
            Layout(name="footer", size=3),
            Layout(name="log", size=10)  # Новая секция для логов
        )

        # Заголовок с лягушкой и статистикой
        self.current_frame = (self.current_frame + 1) % len(self.frog_frames)
        header_content = Panel(
            f"{self.frog_frames[self.current_frame]}\n"
            f"🌐 SEO Анализ сайта: {self.domain}\n"
            f"📑 Проанализировано страниц: {self.total_scanned}",
            title="SEO Frog Scanner",
            style="bold green",
            border_style="green"
        )
        layout["header"].update(header_content)

        # Основной контент: статистика и последние страницы
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

        # Футер с текущим URL
        footer_content = Panel(
            f"🔍 Сканирование: {self.current_url}",
            style="bold blue",
            border_style="blue"
        )
        layout["footer"].update(footer_content)

        # Секция логов
        recent_logs = self.get_recent_logs()  # Новый метод для получения последних логов
        log_content = Panel(
            "\n".join(recent_logs),
            title="📝 Последние действия",
            border_style="yellow"
        )
        layout["log"].update(log_content)

        return layout
    
    async def scan_site(self, session: aiohttp.ClientSession, live: Live):
        """Основной метод сканирования сайта"""
        async def process_url(url: str, depth: int = 0, source_url: str = None):
            await asyncio.sleep(0.5)  # Задержка между запросами
            
            if depth > self.config['max_depth'] or url in self.visited_urls:
                return

            # Нормализация URL
            parsed_url = urlparse(url)
            if not parsed_url.scheme:
                url = f"https://{url}"
                parsed_url = urlparse(url)
            
            # Очищаем URL
            clean_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
            if parsed_url.query:
                clean_url += f"?{parsed_url.query}"
            
            # Убираем www и нормализуем домен
            netloc = parsed_url.netloc.replace('www.', '')
            if netloc != self.domain.replace('www.', ''):
                return

            # Проверяем, что это основной домен (без поддоменов)
            if not self.is_main_domain_only(clean_url):
                self.add_log(f"Пропускаем поддомен: {clean_url}", "warning")
                return
            
            if clean_url in self.visited_urls:
                return

            self.current_url = clean_url
            self.visited_urls.add(clean_url)
            
            try:
                async with session.get(clean_url, headers=self.headers, timeout=30, allow_redirects=True) as response:
                    self.status_counts[response.status] += 1
                    
                    # Обработка редиректов
                    if response.history:
                        redirect_chain = ' -> '.join([str(r.status) for r in response.history] + [str(response.status)])
                        self.add_log(f"Редирект: {clean_url} -> {response.url} ({redirect_chain})", "warning")

                    # Обработка ошибок с источниками
                    if response.status == 404:
                        error_msg = f"404: {clean_url} (источник: {source_url or 'Начальная страница'})"
                        self.log_error(error_msg)
                        self.add_log("404: " + clean_url[:50] + "...", "error")
                        self.not_found_urls.append({'url': clean_url, 'source': source_url or 'Начальная страница'})
                    elif response.status >= 400:
                        error_msg = f"Ошибка {response.status}: {clean_url} (источник: {source_url or 'Начальная страница'})"
                        self.log_error(error_msg)
                        self.add_log(f"Ошибка {response.status}: " + clean_url[:50] + "...", "error")
                    else:
                        self.add_log(f"Сканирование: {clean_url}", "info")

                    content_type = response.headers.get('content-type', '').lower()
                    if not content_type or 'text/html' not in content_type:
                        return

                    html = await response.text()
                    
                    # Анализируем страницу
                    page_data = await self.analyze_page(session, clean_url, html, response)
                    self.pages_data[clean_url] = page_data
                    self.total_scanned += 1
                    
                    # Обновляем отображение
                    live.update(self.generate_display())
                    
                    # Собираем все ссылки
                    soup = BeautifulSoup(html, 'html.parser')
                    links = set()  # Используем set для уникальных ссылок
                    
                    # Ищем ссылки во всех возможных местах
                    for tag_name in ['a', 'link', 'area', 'base']:
                        for link in soup.find_all(tag_name, href=True):
                            href = link.get('href', '').strip()
                            if href and not href.startswith(('#', 'mailto:', 'tel:', 'javascript:', 'data:')):
                                full_url = urljoin(clean_url, href)
                                links.add(full_url)
                    
                    # Фильтруем и обрабатываем ссылки
                    tasks = []
                    for next_url in links:
                        parsed_next = urlparse(next_url)
                        next_domain = parsed_next.netloc.replace('www.', '')
                        if (next_domain == self.domain.replace('www.', '') and 
                            self.can_fetch(next_url) and 
                            next_url not in self.visited_urls and
                            self.is_main_domain_only(next_url)):  # Добавляем проверку основного домена
                            tasks.append(process_url(next_url, depth + 1, clean_url))
                    
                    # Обрабатываем ссылки небольшими группами
                    if tasks:
                        for i in range(0, len(tasks), 5):
                            batch = tasks[i:i+5]
                            await asyncio.gather(*batch, return_exceptions=True)
                        
            except Exception as e:
                error_msg = f"Ошибка при обработке {clean_url}: {str(e)} (источник: {source_url or 'Начальная страница'})"
                self.log_error(error_msg)
                self.add_log(f"Ошибка при обработке: " + clean_url[:50] + "...", "error")
        
        # Начинаем с начального URL
        await process_url(self.start_url)

    async def export_results(self):
        """Экспорт результатов в различные форматы"""
        # Основной отчет
        main_data = []
        for url, data in self.pages_data.items():
            main_data.append({
                'URL': url,
                'Статус': data.status_code,
                'Заголовок': data.title,
                'Мет-описание': data.meta_description,
                'H1': ' | '.join(data.h1),
                'Количество слов': data.word_count,
                'Время ответа': f"{data.response_time:.2f}",
                'Дубликат': data.duplicate_content,
                'PageRank': f"{data.page_rank:.4f}",
                'Входящие ссылки': len(data.inlinks),
                'Исходящие ссылки': len(data.outlinks),
                'Проблемы': self.get_page_issues(data)
            })

        df_main = pd.DataFrame(main_data)
        df_main.to_excel('seo_отчет_основной.xlsx', index=False)

        # Отчет по изображениям
        images_data = []
        for url, data in self.pages_data.items():
            for img in data.images:
                images_data.append({
                    'URL страницы': url,
                    'URL изображения': img['src'],
                    'Alt текст': img['alt'],
                    'Заголовок': img['title']
                })

        df_images = pd.DataFrame(images_data)
        df_images.to_excel('seo_отчет_изображения.xlsx', index=False)

        # Отчет по дубликатам
        duplicates_data = []
        for content_hash, urls in self.content_hashes.items():
            if len(urls) > 1:
                duplicates_data.extend([{
                    'URL': url,
                    'Хеш': content_hash,
                    'Группа дубликатов': i + 1
                } for i, url in enumerate(urls)])

        if duplicates_data:
            df_duplicates = pd.DataFrame(duplicates_data)
            df_duplicates.to_excel('seo_отчет_дубликаты.xlsx', index=False)

        # Отчет по PageRank
        if self.config['calculate_pagerank'] and self.pages_data:
            pagerank_data = []
            sorted_pages = sorted(
                self.pages_data.items(), 
                key=lambda x: x[1].page_rank, 
                reverse=True
            )
            
            for url, data in sorted_pages:
                pagerank_data.append({
                    'URL': url,
                    'PageRank': data.page_rank,
                    'Входящие ссылки': len(data.inlinks),
                    'Исходящие ссылки': len(data.outlinks),
                    'Заголовок': data.title,
                    'Статус': data.status_code,
                    'Количество слов': data.word_count
                })
            
            df_pagerank = pd.DataFrame(pagerank_data)
            df_pagerank.to_excel('seo_отчет_pagerank.xlsx', index=False)

        # Отчет по редиректам
        if self.redirects:
            redirects_data = [
                {
                    'С URL': data['from'],
                    'На URL': data['to'],
                    'Цепочка редиректов': data['chain']
                }
                for data in self.redirects.values()
            ]
            df_redirects = pd.DataFrame(redirects_data)
            df_redirects.to_excel('seo_отчет_редиректы.xlsx', index=False)

        # Отчет по ошибкам с источниками
        if self.error_urls or self.not_found_urls:
            errors_data = []
            
            # Обработка 404 ошибок
            for error in self.not_found_urls:
                sources = self.error_sources.get(error['url'], [])
                errors_data.append({
                    'URL': error['url'],
                    'Тип ошибки': '404 Не найдено',
                    'Источник обнаружения': error['source'],
                    'Все источники': ' | '.join(sources) if sources else error['source'],
                    'Количество источников': len(sources) if sources else 1
                })
            
            # Обработка других ошибок
            for error in self.error_urls:
                sources = self.error_sources.get(error['url'], [])
                errors_data.append({
                    'URL': error['url'],
                    'Тип ошибки': f"Ошибка {error.get('status', 'неизвестно')}",
                    'Источник обнаружения': error['source'],
                    'Все источники': ' | '.join(sources) if sources else error['source'],
                    'Количество источников': len(sources) if sources else 1
                })

            df_errors = pd.DataFrame(errors_data)
            # Сортируем по количеству источников (приоритезация ошибок)
            df_errors = df_errors.sort_values('Количество источников', ascending=False)
            df_errors.to_excel('seo_отчет_ошибки.xlsx', index=False)

        # Экспорт в XML
        self.export_to_xml()

    def export_to_xml(self):
        """Экспорт страниц, соответствующих фильтру, в XML файл в формате sitemap"""
        urlset = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
        
        for url, data in self.pages_data.items():
            # Check if the URL is a filter page
            if self.is_filter_page(url):
                url_elem = ET.SubElement(urlset, "url")
                ET.SubElement(url_elem, "loc").text = url
                # Optionally add more elements like lastmod, changefreq, priority
                # ET.SubElement(url_elem, "lastmod").text = "2023-10-01"
                # ET.SubElement(url_elem, "changefreq").text = "monthly"
                # ET.SubElement(url_elem, "priority").text = "0.8"

        tree = ET.ElementTree(urlset)
        tree.write("sitemap.xml", encoding='utf-8', xml_declaration=True)

    def is_filter_page(self, url: str) -> bool:
        """Проверяет, является ли URL страницей фильтра"""
        # Example pattern check for filter pages
        # Adjust the pattern to match your specific filter page URLs
        return "/catalog/pamyatniki/" in url and "dvoynoy" in url

    def get_page_issues(self, data: PageSEOData) -> str:
        """Получение списка проблем страницы"""
        issues = []
        if not data.title:
            issues.append("Отсутствует Title")
        elif len(data.title) > 60:
            issues.append("Title слишком длинный")
        
        if not data.meta_description:
            issues.append("Отсутствует Meta Description")
        elif len(data.meta_description) > 160:
            issues.append("Meta Description слишком длинный")
        
        if not data.h1:
            issues.append("Отсутствует H1")
        elif len(data.h1) > 1:
            issues.append("Несколько H1 тегов")
        
        if data.duplicate_content:
            issues.append("Дублированный контент")
        
        if data.word_count < self.config['min_word_count']:
            issues.append("Мало контента")
        
        if data.response_time > self.config['max_response_time']:
            issues.append("Медленный ответ")
        
        return " | ".join(issues)

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
        
        # Ограничиваем количество хранимых логов
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

    async def run(self):
        """Запуск сканирования"""
        self.console.clear()
        self.add_log(f"Начало сканирования сайта: {self.domain}", "info")
        
        timeout = aiohttp.ClientTimeout(total=60, connect=10)
        connector = aiohttp.TCPConnector(limit=10, force_close=True, enable_cleanup_closed=True)
        
        try:
            with Live(self.generate_display(), refresh_per_second=2, screen=True) as live:
                async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                    await self.fetch_robots_txt(session)
                    await self.scan_site(session, live)

                    # Рассчитываем внутренний PageRank после завершения сканирования
                    if self.config['calculate_pagerank']:
                        self.calculate_internal_pagerank()

                    await self.export_results()
            
            self.add_log("Сканирование завершено!", "success")
            self.add_log(f"Проанализировано страниц: {self.total_scanned}", "success")
            self.console.print("\n[green]Сканирование завершено![/green]")
            self.console.print(f"[blue]Проанализировано страниц: {self.total_scanned}[/blue]")
            self.console.print("\n[blue]Отчеты сохранены в файлы:[/blue]")
            for report in [
                "seo_отчет_основной.xlsx",
                "seo_отчет_изображения.xlsx",
                "seo_отчет_дубликаты.xlsx",
                "seo_отчет_редиректы.xlsx",
                "seo_отчет_ошибки.xlsx",
                "sitemap.xml"  # Added sitemap XML report
            ]:
                self.console.print(f"- {report}")
            
            # Добавляем отчет PageRank, если он был создан
            if self.config['calculate_pagerank'] and self.pages_data:
                self.console.print("- seo_отчет_pagerank.xlsx")
            
            self.console.print(f"- {self.error_log_file} (лог ошибок)")
        
        except Exception as e:
            error_msg = f"Критическая ошибка: {str(e)}"
            self.log_error(error_msg)
            self.add_log("Критическая ошибка при сканировании", "error")
            self.console.print(f"[red]{error_msg}[/red]")
        finally:
            await connector.close()




if __name__ == "__main__":
    website_url = input("Введите URL сайта для SEO анализа: ")
    scanner = SEOFrogScanner(website_url)
    asyncio.run(scanner.run())