package main



// Config содержит конфигурацию генератора sitemap
type Config struct {
	BaseURL    string
	MaxWorkers int
	Timeout    int
	BatchSize  int
	MaxRetries int
	OutputFile string
	CacheFile  string
	ProxyURL   string
	Logger     *Logger
}

// Headers для HTTP запросов
var DefaultHeaders = map[string]string{
	"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
}

// FilterMapping маппинг русских названий фильтров на английские
var FilterMapping = map[string]string{
	"по материалу": "material",
	"по форме":     "type",
	"по цвету":     "color",
	"кому":         "for",
}