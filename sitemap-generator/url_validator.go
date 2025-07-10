package main

import (
	"net/url"
	"regexp"
	"strings"
)

// URLValidator валидатор URL
type URLValidator struct {
	skipPatterns []*regexp.Regexp
}

// NewURLValidator создает новый валидатор URL
func NewURLValidator() *URLValidator {
	patterns := []string{
		`\.(pdf|doc|docx|xls|xlsx|zip|rar)$`,
		`#.*$`,
		`\?.*$`,
		`/admin/`,
		`/api/`,
	}

	skipPatterns := make([]*regexp.Regexp, len(patterns))
	for i, pattern := range patterns {
		skipPatterns[i] = regexp.MustCompile(pattern)
	}

	return &URLValidator{
		skipPatterns: skipPatterns,
	}
}

// IsValid проверяет валидность URL
func (v *URLValidator) IsValid(urlStr string) bool {
	parsed, err := url.Parse(urlStr)
	if err != nil {
		return false
	}
	return parsed.Scheme != "" && parsed.Host != ""
}

// Normalize нормализует URL
func (v *URLValidator) Normalize(urlStr string) string {
	if !strings.HasSuffix(urlStr, "/") {
		urlStr += "/"
	}
	return urlStr
}

// ShouldSkip проверяет, нужно ли пропустить URL
func (v *URLValidator) ShouldSkip(urlStr string) bool {
	for _, pattern := range v.skipPatterns {
		if pattern.MatchString(urlStr) {
			return true
		}
	}
	return false
}