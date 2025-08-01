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
		maxWorkers    = flag.Int("workers", 20, "Maximum number of concurrent workers")  // Уменьшено с 100 до 20
		timeout       = flag.Int("timeout", 5, "Request timeout in seconds")  // Увеличено с 2 до 5 секунд  
		batchSize     = flag.Int("batch", 50, "Batch size for URL processing")  // Уменьшено с 200 до 50
		maxRetries    = flag.Int("retries", 5, "Maximum number of retries")  // Увеличено с 3 до 5
		outputFile    = flag.String("output", "sitemap_filters.xml", "Output sitemap file")
		cacheFile     = flag.String("cache", "sitemap_cache.json", "Cache file path")
		verbose       = flag.Bool("verbose", false, "Enable verbose logging")
		semaphoreLimit = flag.Int("semaphore", 10, "Maximum concurrent requests (semaphore limit)")  // Новый параметр
		minDelay      = flag.Int("min-delay", 200, "Minimum delay between requests in milliseconds")  // Новый параметр
		maxDelay      = flag.Int("max-delay", 1000, "Maximum delay between requests in milliseconds")  // Новый параметр
		ignoreCache   = flag.Bool("ignore-cache", false, "Ignore cache and recheck all URLs")  // Новый параметр
	)
	flag.Parse()

	// Настройка логирования
	logger := NewLogger(*verbose)

	// Создание конфигурации
	config := &Config{
		BaseURL:        *baseURL,
		MaxWorkers:     *maxWorkers,
		Timeout:        *timeout,
		BatchSize:      *batchSize,
		MaxRetries:     *maxRetries,
		OutputFile:     *outputFile,
		CacheFile:      *cacheFile,
		Logger:         logger,
		SemaphoreLimit: *semaphoreLimit,  // Новое поле
		MinDelay:       *minDelay,        // Новое поле
		MaxDelay:       *maxDelay,        // Новое поле
		IgnoreCache:    *ignoreCache,     // Новое поле
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