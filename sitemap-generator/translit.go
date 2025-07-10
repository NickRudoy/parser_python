package main

import (
	"strings"
	"sync"
)

// Transliterator транслитератор с кэшированием
type Transliterator struct {
	cache map[string]string
	mutex sync.RWMutex
}

// NewTransliterator создает новый транслитератор
func NewTransliterator() *Transliterator {
	return &Transliterator{
		cache: make(map[string]string),
	}
}

// Translit транслитерирует текст с кэшированием
func (t *Transliterator) Translit(text string) string {
	// Проверяем кэш
	t.mutex.RLock()
	if result, exists := t.cache[text]; exists {
		t.mutex.RUnlock()
		return result
	}
	t.mutex.RUnlock()

	// Транслитерируем
	result := t.translitText(text)

	// Сохраняем в кэш
	t.mutex.Lock()
	t.cache[text] = result
	t.mutex.Unlock()

	return result
}

// translitText выполняет транслитерацию
func (t *Transliterator) translitText(text string) string {
	translitMap := map[rune]string{
		'а': "a", 'б': "b", 'в': "v", 'г': "g", 'д': "d", 'е': "e", 'ё': "e",
		'ж': "zh", 'з': "z", 'и': "i", 'й': "y", 'к': "k", 'л': "l", 'м': "m",
		'н': "n", 'о': "o", 'п': "p", 'р': "r", 'с': "s", 'т': "t", 'у': "u",
		'ф': "f", 'х': "h", 'ц': "ts", 'ч': "ch", 'ш': "sh", 'щ': "sch",
		'ъ': "", 'ы': "y", 'ь': "", 'э': "e", 'ю': "yu", 'я': "ya",
		' ': "-", ',': "", '.': "", '(': "", ')': "", '"': "", '\'': "",
	}

	var result strings.Builder
	for _, char := range strings.ToLower(text) {
		if translit, exists := translitMap[char]; exists {
			result.WriteString(translit)
		} else {
			result.WriteRune(char)
		}
	}

	return result.String()
}