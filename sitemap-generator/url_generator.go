package main

import (
	"fmt"
	"strings"
)

// URLGenerator генератор URL
type URLGenerator struct {
	config     *Config
	validator  *URLValidator
	translit   *Transliterator
}

// NewURLGenerator создает новый генератор URL
func NewURLGenerator(config *Config) *URLGenerator {
	return &URLGenerator{
		config:    config,
		validator: NewURLValidator(),
		translit:  NewTransliterator(),
	}
}

// GenerateURLs генерирует URL на основе фильтров
func (g *URLGenerator) GenerateURLs(filters map[string][]string) []string {
	urls := make(map[string]bool)
	urls[g.config.BaseURL] = true

	// Очищаем и нормализуем фильтры
	cleanFilters := g.cleanFilters(filters)

	// Генерируем комбинации
	combinations := g.generateCombinations(cleanFilters)

	// Создаем URL
	for _, combo := range combinations {
		url := fmt.Sprintf("%s/%s/", g.config.BaseURL, strings.Join(combo, "/"))
		if g.validator.IsValid(url) {
			urls[url] = true
		}
	}

	// Конвертируем в слайс
	result := make([]string, 0, len(urls))
	for url := range urls {
		result = append(result, url)
	}

	return result
}

// cleanFilters очищает и нормализует фильтры
func (g *URLGenerator) cleanFilters(filters map[string][]string) map[string][]string {
	clean := make(map[string][]string)
	
	for key, values := range filters {
		var cleanValues []string
		for _, value := range values {
			if value == "" {
				continue
			}
			
			// Транслитерируем значение
			translitValue := g.translit.Translit(value)
			
			// Проверяем, не нужно ли пропустить
			if !g.validator.ShouldSkip(translitValue) {
				cleanValues = append(cleanValues, translitValue)
			}
		}
		
		if len(cleanValues) > 0 {
			clean[key] = cleanValues
		}
	}
	
	return clean
}

// generateCombinations генерирует комбинации фильтров
func (g *URLGenerator) generateCombinations(filters map[string][]string) [][]string {
	var combinations [][]string
	
	// Генерируем комбинации разной длины (как в Python версии)
	for r := 1; r <= len(filters); r++ {
		keys := g.getCombinations(keys(filters), r)
		for _, keyCombo := range keys {
			valuesList := make([][]string, len(keyCombo))
			for i, key := range keyCombo {
				valuesList[i] = filters[key]
			}
			
			product := g.cartesianProduct(valuesList)
			combinations = append(combinations, product...)
		}
	}
	
	return combinations
}

// keys возвращает ключи map
func keys(m map[string][]string) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	return keys
}

// getCombinations возвращает комбинации элементов
func (g *URLGenerator) getCombinations(elements []string, r int) [][]string {
	if r == 0 {
		return [][]string{{}}
	}
	if len(elements) == 0 {
		return [][]string{}
	}
	
	var result [][]string
	for i := 0; i <= len(elements)-r; i++ {
		subCombos := g.getCombinations(elements[i+1:], r-1)
		for _, subCombo := range subCombos {
			combo := append([]string{elements[i]}, subCombo...)
			result = append(result, combo)
		}
	}
	
	return result
}

// cartesianProduct возвращает декартово произведение
func (g *URLGenerator) cartesianProduct(arrays [][]string) [][]string {
	if len(arrays) == 0 {
		return [][]string{}
	}
	if len(arrays) == 1 {
		result := make([][]string, len(arrays[0]))
		for i, item := range arrays[0] {
			result[i] = []string{item}
		}
		return result
	}
	
	subProduct := g.cartesianProduct(arrays[1:])
	var result [][]string
	
	for _, item := range arrays[0] {
		for _, subCombo := range subProduct {
			combo := append([]string{item}, subCombo...)
			result = append(result, combo)
		}
	}
	
	return result
}