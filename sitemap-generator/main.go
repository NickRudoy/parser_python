package main

import (
	"context"
	"flag"
	"os"
	"os/signal"
	"syscall"
)

func main() {
	// Парсинг флагов командной строки
	var (
		baseURL       = flag.String("url", "https://obelisk.ru/catalog/pamyatniki", "Base URL for sitemap generation")
		maxWorkers    = flag.Int("workers", 100, "Maximum number of concurrent workers")
		timeout       = flag.Int("timeout", 2, "Request timeout in seconds")
		batchSize     = flag.Int("batch", 200, "Batch size for URL processing")
		maxRetries    = flag.Int("retries", 3, "Maximum number of retries")
		outputFile    = flag.String("output", "sitemap_filters.xml", "Output sitemap file")
		cacheFile     = flag.String("cache", "sitemap_cache.json", "Cache file path")
		proxyURL      = flag.String("proxy", "", "Proxy URL (e.g., http://proxy:port)")
		verbose       = flag.Bool("verbose", false, "Enable verbose logging")
		fromCache     = flag.Bool("from-cache", false, "Create sitemap from existing cache only")
	)
	flag.Parse()

	// Настройка логирования
	logger := NewLogger(*verbose)

	// Создание конфигурации
	config := &Config{
		BaseURL:    *baseURL,
		MaxWorkers: *maxWorkers,
		Timeout:    *timeout,
		BatchSize:  *batchSize,
		MaxRetries: *maxRetries,
		OutputFile: *outputFile,
		CacheFile:  *cacheFile,
		ProxyURL:   *proxyURL,
		Logger:     logger,
	}

	// Проверяем, нужно ли создать sitemap только из кэша
	if *fromCache {
		logger.Info("Создание sitemap из существующего кэша...")
		if err := CacheToSitemap(*cacheFile, *outputFile); err != nil {
			logger.Error("Ошибка создания sitemap из кэша: %v", err)
			os.Exit(1)
		}
		logger.Info("Sitemap успешно создан из кэша!")
		return
	}

	// Создание генератора
	generator := NewSitemapGenerator(config)

	// Обработка сигналов для graceful shutdown
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		<-sigChan
		logger.Info("Получен сигнал завершения, останавливаем генерацию...")
		cancel()
	}()

	// Запуск генерации
	if err := generator.Generate(ctx); err != nil {
		logger.Error("Ошибка генерации sitemap: %v", err)
		os.Exit(1)
	}

	logger.Info("Sitemap успешно сгенерирован!")
}