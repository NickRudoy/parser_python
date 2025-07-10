package main

import (
	"context"
	"encoding/xml"
	"fmt"
	"os"
	"sync"
	"time"
)

// SitemapGenerator основной генератор sitemap
type SitemapGenerator struct {
	config      *Config
	cache       *Cache
	generator   *URLGenerator
	client      *HTTPClient
	metrics     *Metrics
	validator   *URLValidator
	filterParser *FilterParser
}

// NewSitemapGenerator создает новый генератор sitemap
func NewSitemapGenerator(config *Config) *SitemapGenerator {
	client := NewHTTPClient(config.Timeout, DefaultHeaders, config.Logger)
	translit := NewTransliterator()
	
	return &SitemapGenerator{
		config:       config,
		cache:        NewCache(config.CacheFile, 24*time.Hour, config.Logger),
		generator:    NewURLGenerator(config),
		client:       client,
		metrics:      NewMetrics(),
		validator:    NewURLValidator(),
		filterParser: NewFilterParser(client, translit),
	}
}

// Generate генерирует sitemap
func (s *SitemapGenerator) Generate(ctx context.Context) error {
	s.config.Logger.Info("Начало генерации sitemap")
	
	// Загружаем кэш
	if err := s.cache.Load(); err != nil {
		s.config.Logger.Error("Ошибка загрузки кэша: %v", err)
	}
	
	// Получаем фильтры
	filters, err := s.getFilters(ctx)
	if err != nil {
		s.config.Logger.Error("Ошибка получения фильтров: %v", err)
		// Используем тестовые данные
		filters = map[string][]string{
			"material": {"kapustinskiy", "granit", "mramor"},
			"type":     {"derevo", "krest", "plita"},
			"color":    {"chernyy", "krasnyy", "seryy"},
		}
	}
	
	// Генерируем URL
	urlsToCheck := s.generator.GenerateURLs(filters)
	s.metrics.SetTotal(len(urlsToCheck))
	s.config.Logger.Info("Сгенерировано URL для проверки: %d", len(urlsToCheck))
	
	// Проверяем URL
	validURLs, err := s.checkURLs(ctx, urlsToCheck)
	if err != nil {
		return fmt.Errorf("ошибка проверки URL: %w", err)
	}
	
	// Создаем sitemap
	if err := s.createSitemap(validURLs); err != nil {
		return fmt.Errorf("ошибка создания sitemap: %w", err)
	}
	
	// Сохраняем кэш
	if err := s.cache.Save(); err != nil {
		s.config.Logger.Error("Ошибка сохранения кэша: %v", err)
	}
	
	// Выводим метрики
	s.printMetrics()
	
	return nil
}

// getFilters получает фильтры с сайта
func (s *SitemapGenerator) getFilters(ctx context.Context) (map[string][]string, error) {
	filters, err := s.filterParser.GetFilters(ctx, s.config.BaseURL)
	if err != nil {
		s.config.Logger.Error("Ошибка получения фильтров с сайта: %v", err)
		s.config.Logger.Info("Используем тестовые данные для фильтров")
		// Возвращаем тестовые данные в случае ошибки
		return map[string][]string{
			"material": {"kapustinskiy", "granit", "mramor"},
			"type":     {"derevo", "krest", "plita"},
			"color":    {"chernyy", "krasnyy", "seryy"},
		}, nil
	}
	
	s.config.Logger.Info("Найденные фильтры: %v", filters)
	return filters, nil
}

// checkURLs проверяет URL асинхронно
func (s *SitemapGenerator) checkURLs(ctx context.Context, urls []string) ([]string, error) {
	var validURLs []string
	
	// Создаем каналы для работы
	urlChan := make(chan string, s.config.BatchSize)
	resultChan := make(chan string, s.config.BatchSize)
	
	// Запускаем воркеры
	var wg sync.WaitGroup
	for i := 0; i < s.config.MaxWorkers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for url := range urlChan {
				select {
				case <-ctx.Done():
					return
				default:
				}
				
				// Проверяем кэш
				if entry, exists := s.cache.Get(url); exists {
					if entry.Valid {
						resultChan <- url
					}
					continue
				}
				
				// Проверяем URL
				valid, err := s.client.CheckURL(ctx, url, s.config.MaxRetries)
				if err != nil {
					s.config.Logger.Debug("Ошибка проверки %s: %v", url, err)
				}
				
				// Сохраняем в кэш
				s.cache.Set(url, valid)
				
				if valid {
					resultChan <- url
					s.metrics.IncrementValid()
				} else {
					s.metrics.IncrementFailed()
				}
				
				// Добавляем небольшую задержку между запросами
				time.Sleep(50 * time.Millisecond)
			}
		}()
	}
	
	// Отправляем URL в канал
	go func() {
		defer close(urlChan)
		for _, url := range urls {
			select {
			case <-ctx.Done():
				return
			case urlChan <- url:
			}
		}
	}()
	
	// Собираем результаты
	go func() {
		wg.Wait()
		close(resultChan)
	}()
	
	// Собираем валидные URL
	for url := range resultChan {
		validURLs = append(validURLs, url)
	}
	
	return validURLs, nil
}

// createSitemap создает sitemap файл
func (s *SitemapGenerator) createSitemap(urls []string) error {
	// Структуры для XML
	type URL struct {
		Loc      string `xml:"loc"`
		Lastmod  string `xml:"lastmod"`
		Priority string `xml:"priority"`
	}
	
	type URLSet struct {
		XMLName string `xml:"urlset"`
		XMLNS   string `xml:"xmlns,attr"`
		URLs    []URL  `xml:"url"`
	}
	
	urlset := URLSet{
		XMLNS: "http://www.sitemaps.org/schemas/sitemap/0.9",
		URLs:  make([]URL, 0, len(urls)),
	}
	
	now := time.Now().Format("2006-01-02")
	
	for _, url := range urls {
		priority := "0.8"
		if url == s.config.BaseURL {
			priority = "1.0"
		}
		
		urlset.URLs = append(urlset.URLs, URL{
			Loc:      url,
			Lastmod:  now,
			Priority: priority,
		})
	}
	
	// Создаем файл
	file, err := os.Create(s.config.OutputFile)
	if err != nil {
		return fmt.Errorf("ошибка создания файла: %w", err)
	}
	defer file.Close()
	
	// Записываем XML
	encoder := xml.NewEncoder(file)
	encoder.Indent("", "    ")
	if err := encoder.Encode(urlset); err != nil {
		return fmt.Errorf("ошибка кодирования XML: %w", err)
	}
	
	s.config.Logger.Info("Sitemap сохранен: %s", s.config.OutputFile)
	return nil
}

// printMetrics выводит метрики
func (s *SitemapGenerator) printMetrics() {
	summary := s.metrics.GetSummary()
	s.config.Logger.Info("=== МЕТРИКИ ===")
	s.config.Logger.Info("Всего URL: %d", summary["total_urls"])
	s.config.Logger.Info("Валидных URL: %d", summary["valid_urls"])
	s.config.Logger.Info("Неудачных URL: %d", summary["failed_urls"])
	s.config.Logger.Info("Процент успеха: %.2f%%", summary["success_rate"].(float64)*100)
	s.config.Logger.Info("Время выполнения: %v", summary["elapsed_time"])
	s.config.Logger.Info("URL в секунду: %.2f", summary["urls_per_second"])
	s.config.Logger.Info("Среднее время ответа: %v", summary["avg_response_time"])
}