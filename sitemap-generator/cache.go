package main

import (
	"encoding/json"
	"fmt"
	"os"
	"sync"
	"time"
)

// CacheEntry представляет запись в кэше
type CacheEntry struct {
	URL       string    `json:"url"`
	Valid     bool      `json:"valid"`
	Timestamp time.Time `json:"timestamp"`
}

// Cache структура кэша
type Cache struct {
	Entries map[string]CacheEntry `json:"entries"`
	TTL     time.Duration         `json:"ttl"`
	file    string
	logger  *Logger
	mutex   sync.RWMutex
}

// NewCache создает новый кэш
func NewCache(file string, ttl time.Duration, logger *Logger) *Cache {
	return &Cache{
		Entries: make(map[string]CacheEntry),
		TTL:     ttl,
		file:    file,
		logger:  logger,
	}
}

// Load загружает кэш из файла
func (c *Cache) Load() error {
	file, err := os.Open(c.file)
	if err != nil {
		if os.IsNotExist(err) {
			c.logger.Info("Кэш не найден, создаем новый")
			return nil
		}
		return fmt.Errorf("ошибка открытия кэша: %w", err)
	}
	defer file.Close()

	var data struct {
		Entries map[string]CacheEntry `json:"entries"`
		TTL     time.Duration         `json:"ttl"`
	}

	if err := json.NewDecoder(file).Decode(&data); err != nil {
		return fmt.Errorf("ошибка декодирования кэша: %w", err)
	}

	// Проверяем TTL
	now := time.Now()
	validEntries := make(map[string]CacheEntry)
	for url, entry := range data.Entries {
		if now.Sub(entry.Timestamp) < c.TTL {
			validEntries[url] = entry
		}
	}

	c.Entries = validEntries
	c.logger.Info("Загружен кэш: %d записей", len(c.Entries))
	return nil
}

// Save сохраняет кэш в файл
func (c *Cache) Save() error {
	file, err := os.Create(c.file)
	if err != nil {
		return fmt.Errorf("ошибка создания файла кэша: %w", err)
	}
	defer file.Close()

	data := struct {
		Entries map[string]CacheEntry `json:"entries"`
		TTL     time.Duration         `json:"ttl"`
		Count   int                   `json:"count"`
	}{
		Entries: c.Entries,
		TTL:     c.TTL,
		Count:   len(c.Entries),
	}

	if err := json.NewEncoder(file).Encode(data); err != nil {
		return fmt.Errorf("ошибка кодирования кэша: %w", err)
	}

	c.logger.Info("Кэш сохранен: %d записей", len(c.Entries))
	return nil
}

// Get получает запись из кэша
func (c *Cache) Get(url string) (CacheEntry, bool) {
	c.mutex.RLock()
	defer c.mutex.RUnlock()
	entry, exists := c.Entries[url]
	return entry, exists
}

// Set устанавливает запись в кэш
func (c *Cache) Set(url string, valid bool) {
	c.mutex.Lock()
	defer c.mutex.Unlock()
	c.Entries[url] = CacheEntry{
		URL:       url,
		Valid:     valid,
		Timestamp: time.Now(),
	}
}