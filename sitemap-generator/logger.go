package main

import (
	"log"
	"os"
)

// Logger структура для логирования
type Logger struct {
	verbose bool
	logger  *log.Logger
}

// NewLogger создает новый логгер
func NewLogger(verbose bool) *Logger {
	return &Logger{
		verbose: verbose,
		logger:  log.New(os.Stdout, "", log.LstdFlags),
	}
}

// Info логирует информационное сообщение
func (l *Logger) Info(format string, args ...interface{}) {
	l.logger.Printf("[INFO] "+format, args...)
}

// Error логирует ошибку
func (l *Logger) Error(format string, args ...interface{}) {
	l.logger.Printf("[ERROR] "+format, args...)
}

// Debug логирует отладочное сообщение
func (l *Logger) Debug(format string, args ...interface{}) {
	if l.verbose {
		l.logger.Printf("[DEBUG] "+format, args...)
	}
}

// Progress логирует прогресс
func (l *Logger) Progress(current, total int, message string) {
	percentage := float64(current) / float64(total) * 100
	l.Info("%s: %d/%d (%.1f%%)", message, current, total, percentage)
}