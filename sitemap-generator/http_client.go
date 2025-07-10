package main

import (
	"context"
	"fmt"
	"net/http"
	"net/url"
	"time"
)

// HTTPClient HTTP клиент с настройками
type HTTPClient struct {
	client  *http.Client
	headers map[string]string
	logger  *Logger
	proxy   string
}

// NewHTTPClient создает новый HTTP клиент
func NewHTTPClient(timeout int, headers map[string]string, logger *Logger, proxyURL string) *HTTPClient {
	client := &http.Client{
		Timeout: time.Duration(timeout) * time.Second,
	}
	
	// Настраиваем прокси если указан
	if proxyURL != "" {
		proxyURLParsed, err := url.Parse(proxyURL)
		if err != nil {
			logger.Error("Ошибка парсинга прокси URL: %v", err)
		} else {
			client.Transport = &http.Transport{
				Proxy: http.ProxyURL(proxyURLParsed),
			}
		}
	}
	
	return &HTTPClient{
		client:  client,
		headers: headers,
		logger:  logger,
		proxy:   proxyURL,
	}
}

// CheckURL проверяет доступность URL
func (c *HTTPClient) CheckURL(ctx context.Context, url string, maxRetries int) (bool, error) {
	for attempt := 0; attempt < maxRetries; attempt++ {
		select {
		case <-ctx.Done():
			return false, ctx.Err()
		default:
		}
		
		// Добавляем случайную задержку для избежания блокировки
		if attempt > 0 {
			delay := time.Duration(500+attempt*200) * time.Millisecond
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
		
		// Добавляем случайный User-Agent
		userAgents := []string{
			"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
			"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
			"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
		}
		req.Header.Set("User-Agent", userAgents[attempt%len(userAgents)])
		
		resp, err := c.client.Do(req)
		if err != nil {
			c.logger.Debug("Попытка %d для %s: %v", attempt+1, url, err)
			if attempt == maxRetries-1 {
				return false, err
			}
			time.Sleep(time.Duration(attempt+1) * 500 * time.Millisecond)
			continue
		}
		defer resp.Body.Close()
		
		if resp.StatusCode == 200 {
			return true, nil
		}
		
		c.logger.Debug("URL %s вернул статус %d", url, resp.StatusCode)
		return false, nil
	}
	
	return false, fmt.Errorf("превышено количество попыток")
}