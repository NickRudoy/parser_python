package main

import (
	"encoding/xml"
	"fmt"
	"os"
	"time"
)

// CacheToSitemap создает sitemap из существующего кэша
func CacheToSitemap(cacheFile, outputFile string) error {
	// Загружаем кэш
	cache := NewCache(cacheFile, 24*time.Hour, NewLogger(false))
	if err := cache.Load(); err != nil {
		return fmt.Errorf("ошибка загрузки кэша: %w", err)
	}

	// Собираем валидные URL
	var validURLs []string
	for url, entry := range cache.Entries {
		if entry.Valid {
			validURLs = append(validURLs, url)
		}
	}

	fmt.Printf("Найдено %d валидных URL в кэше\n", len(validURLs))

	// Создаем sitemap
	if err := createSitemapFromURLs(validURLs, outputFile); err != nil {
		return fmt.Errorf("ошибка создания sitemap: %w", err)
	}

	fmt.Printf("Sitemap создан: %s\n", outputFile)
	return nil
}

// createSitemapFromURLs создает sitemap из списка URL
func createSitemapFromURLs(urls []string, outputFile string) error {
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
		if url == "https://obelisk.ru/catalog/pamyatniki" {
			priority = "1.0"
		}

		urlset.URLs = append(urlset.URLs, URL{
			Loc:      url,
			Lastmod:  now,
			Priority: priority,
		})
	}

	// Создаем файл
	file, err := os.Create(outputFile)
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

	return nil
} 