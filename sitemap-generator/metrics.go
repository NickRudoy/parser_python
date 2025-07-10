package main

import (
	"sync"
	"time"
)

// Metrics метрики производительности
type Metrics struct {
	startTime      time.Time
	totalURLs      int
	validURLs      int
	failedURLs     int
	responseTimes  map[string][]time.Duration
	statusCodes    map[int]int
	mutex          sync.RWMutex
}

// NewMetrics создает новые метрики
func NewMetrics() *Metrics {
	return &Metrics{
		startTime:     time.Now(),
		responseTimes: make(map[string][]time.Duration),
		statusCodes:   make(map[int]int),
	}
}

// AddResponseTime добавляет время ответа
func (m *Metrics) AddResponseTime(url string, duration time.Duration) {
	m.mutex.Lock()
	defer m.mutex.Unlock()
	
	domain := extractDomain(url)
	m.responseTimes[domain] = append(m.responseTimes[domain], duration)
}

// AddStatusCode добавляет статус код
func (m *Metrics) AddStatusCode(statusCode int) {
	m.mutex.Lock()
	defer m.mutex.Unlock()
	m.statusCodes[statusCode]++
}

// IncrementValid увеличивает счетчик валидных URL
func (m *Metrics) IncrementValid() {
	m.mutex.Lock()
	defer m.mutex.Unlock()
	m.validURLs++
}

// IncrementFailed увеличивает счетчик неудачных URL
func (m *Metrics) IncrementFailed() {
	m.mutex.Lock()
	defer m.mutex.Unlock()
	m.failedURLs++
}

// SetTotal устанавливает общее количество URL
func (m *Metrics) SetTotal(total int) {
	m.mutex.Lock()
	defer m.mutex.Unlock()
	m.totalURLs = total
}

// GetSummary возвращает сводку метрик
func (m *Metrics) GetSummary() map[string]interface{} {
	m.mutex.RLock()
	defer m.mutex.RUnlock()
	
	elapsed := time.Since(m.startTime)
	
	// Вычисляем среднее время ответа
	var totalDuration time.Duration
	var totalCount int
	for _, times := range m.responseTimes {
		for _, duration := range times {
			totalDuration += duration
			totalCount++
		}
	}
	
	var avgResponseTime time.Duration
	if totalCount > 0 {
		avgResponseTime = totalDuration / time.Duration(totalCount)
	}
	
	successRate := 0.0
	if m.totalURLs > 0 {
		successRate = float64(m.validURLs) / float64(m.totalURLs)
	}
	
	urlsPerSecond := 0.0
	if elapsed.Seconds() > 0 {
		urlsPerSecond = float64(m.totalURLs) / elapsed.Seconds()
	}
	
	return map[string]interface{}{
		"total_urls":        m.totalURLs,
		"valid_urls":        m.validURLs,
		"failed_urls":       m.failedURLs,
		"success_rate":      successRate,
		"elapsed_time":      elapsed,
		"urls_per_second":   urlsPerSecond,
		"avg_response_time": avgResponseTime,
		"status_codes":      m.statusCodes,
	}
}

// extractDomain извлекает домен из URL
func extractDomain(url string) string {
	// Упрощенная реализация
	if len(url) > 8 && url[:8] == "https://" {
		url = url[8:]
	} else if len(url) > 7 && url[:7] == "http://" {
		url = url[7:]
	}
	
	for i, char := range url {
		if char == '/' {
			return url[:i]
		}
	}
	return url
}