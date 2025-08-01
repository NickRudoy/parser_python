package main

import (
	"context"
	"fmt"
	"math/rand"
	"net/http"
	"time"
)

// HTTPClient HTTP клиент с настройками
type HTTPClient struct {
	client  *http.Client
	headers map[string]string
	logger  *Logger
}

// NewHTTPClient создает новый HTTP клиент
func NewHTTPClient(timeout int, headers map[string]string, logger *Logger) *HTTPClient {
	return &HTTPClient{
		client: &http.Client{
			Timeout: time.Duration(timeout) * time.Second,
			Transport: &http.Transport{
				MaxIdleConns:          100,
				MaxIdleConnsPerHost:   20,
				IdleConnTimeout:       90 * time.Second,
				TLSHandshakeTimeout:   10 * time.Second,
				ExpectContinueTimeout: 1 * time.Second,
			},
		},
		headers: headers,
		logger:  logger,
	}
}

// CheckURL проверяет доступность URL
func (c *HTTPClient) CheckURL(ctx context.Context, url string, maxRetries int, minDelay, maxDelay int) (bool, error) {
	userAgents := []string{
		"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
		"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
		"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
		"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
		"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
	}
	
	for attempt := 0; attempt < maxRetries; attempt++ {
		select {
		case <-ctx.Done():
			return false, ctx.Err()
		default:
		}
		
		// Экспоненциальный backoff с джиттером как в Python версии
		if attempt > 0 {
			baseDelay := time.Duration(100*(attempt+1)) * time.Millisecond
			jitter := time.Duration(rand.Intn(200)) * time.Millisecond
			delay := baseDelay + jitter
			
			c.logger.Debug("Retry %d для %s, задержка: %v", attempt+1, url, delay)
			time.Sleep(delay)
		}
		
		req, err := http.NewRequestWithContext(ctx, "HEAD", url, nil)
		if err != nil {
			return false, fmt.Errorf("ошибка создания запроса: %w", err)
		}
		
		// Добавляем заголовки
		for key, value := range c.headers {
			req.Header.Set(key, value)
		}
		
		// Случайный User-Agent
		req.Header.Set("User-Agent", userAgents[rand.Intn(len(userAgents))])
		
		// Дополнительные заголовки для имитации браузера
		req.Header.Set("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8")
		req.Header.Set("Accept-Language", "ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3")
		req.Header.Set("Accept-Encoding", "gzip, deflate")
		req.Header.Set("Connection", "keep-alive")
		req.Header.Set("Upgrade-Insecure-Requests", "1")
		req.Header.Set("Cache-Control", "no-cache")
		req.Header.Set("Pragma", "no-cache")
		
		resp, err := c.client.Do(req)
		if err != nil {
			c.logger.Debug("Попытка %d для %s: %v", attempt+1, url, err)
			if attempt == maxRetries-1 {
				return false, err
			}
			continue
		}
		defer resp.Body.Close()
		
		if resp.StatusCode == 200 {
			return true, nil
		} else if resp.StatusCode == 429 || resp.StatusCode >= 500 {
			// Для этих статусов стоит повторить попытку
			c.logger.Debug("URL %s вернул статус %d, повторяем", url, resp.StatusCode)
			if attempt == maxRetries-1 {
				return false, nil
			}
			continue
		}
		
		c.logger.Debug("URL %s вернул статус %d", url, resp.StatusCode)
		return false, nil
	}
	
	return false, fmt.Errorf("превышено количество попыток")
}