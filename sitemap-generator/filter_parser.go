package main

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"strings"
	"golang.org/x/net/html"
)

// FilterParser парсер фильтров с сайта
type FilterParser struct {
	client *HTTPClient
	translit *Transliterator
}

// NewFilterParser создает новый парсер фильтров
func NewFilterParser(client *HTTPClient, translit *Transliterator) *FilterParser {
	return &FilterParser{
		client: client,
		translit: translit,
	}
}

// GetFilters получает фильтры с сайта
func (fp *FilterParser) GetFilters(ctx context.Context, baseURL string) (map[string][]string, error) {
	// Создаем HTTP запрос с увеличенным таймаутом
	req, err := http.NewRequestWithContext(ctx, "GET", baseURL, nil)
	if err != nil {
		return nil, fmt.Errorf("ошибка создания запроса: %w", err)
	}

	// Добавляем заголовки
	for key, value := range DefaultHeaders {
		req.Header.Set(key, value)
	}

	// Добавляем дополнительные заголовки для избежания блокировки
	req.Header.Set("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8")
	req.Header.Set("Accept-Language", "ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3")
	req.Header.Set("Accept-Encoding", "gzip, deflate")
	req.Header.Set("Connection", "keep-alive")
	req.Header.Set("Upgrade-Insecure-Requests", "1")

	// Выполняем запрос
	resp, err := fp.client.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("ошибка выполнения запроса: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("неверный статус ответа: %d", resp.StatusCode)
	}

	// Читаем тело ответа
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("ошибка чтения ответа: %w", err)
	}

	// Парсим HTML
	return fp.parseHTML(string(body))
}

// parseHTML парсит HTML и извлекает фильтры
func (fp *FilterParser) parseHTML(htmlContent string) (map[string][]string, error) {
	doc, err := html.Parse(strings.NewReader(htmlContent))
	if err != nil {
		return nil, fmt.Errorf("ошибка парсинга HTML: %w", err)
	}

	filters := make(map[string][]string)
	
	// Ищем форму фильтра
	form := fp.findForm(doc)
	if form == nil {
		return nil, fmt.Errorf("форма фильтра не найдена")
	}

	// Ищем панели фильтров
	panels := fp.findFilterPanels(form)
	
	// Маппинг русских названий на английские
	filterMapping := map[string]string{
		"по материалу": "material",
		"по форме":     "type", 
		"по цвету":     "color",
		"кому":         "for",
		"гравировка  (оформление)": "engraving",
	}

	for _, panel := range panels {
		filterName, values := fp.parseFilterPanel(panel, filterMapping)
		if filterName != "" && len(values) > 0 {
			filters[filterName] = values
		}
	}

	return filters, nil
}

// findForm ищет форму фильтра
func (fp *FilterParser) findForm(n *html.Node) *html.Node {
	var form *html.Node
	var findForm func(*html.Node)
	
	findForm = func(n *html.Node) {
		if n.Type == html.ElementNode && n.Data == "form" {
			for _, attr := range n.Attr {
				if attr.Key == "name" && attr.Val == "arrFilter_form" {
					form = n
					return
				}
			}
		}
		for c := n.FirstChild; c != nil; c = c.NextSibling {
			findForm(c)
		}
	}
	
	findForm(n)
	return form
}

// findFilterPanels ищет панели фильтров
func (fp *FilterParser) findFilterPanels(form *html.Node) []*html.Node {
	var panels []*html.Node
	var findPanels func(*html.Node)
	
	findPanels = func(n *html.Node) {
		if n.Type == html.ElementNode && n.Data == "div" {
			for _, attr := range n.Attr {
				if attr.Key == "class" && strings.Contains(attr.Val, "zcatalogDetail__filter_panel") {
					panels = append(panels, n)
					return
				}
			}
		}
		for c := n.FirstChild; c != nil; c = c.NextSibling {
			findPanels(c)
		}
	}
	
	findPanels(form)
	return panels
}

// parseFilterPanel парсит панель фильтра
func (fp *FilterParser) parseFilterPanel(panel *html.Node, mapping map[string]string) (string, []string) {
	var filterName string
	var values []string
	
	// Ищем название фильтра
	var findName func(*html.Node)
	findName = func(n *html.Node) {
		if n.Type == html.ElementNode && n.Data == "span" {
			for _, attr := range n.Attr {
				if attr.Key == "class" && strings.Contains(attr.Val, "zcatalogDetail__filter_name") {
					filterName = fp.getTextContent(n)
					filterName = strings.ToLower(strings.TrimSpace(filterName))
					filterName = mapping[filterName]
					return
				}
			}
		}
		for c := n.FirstChild; c != nil; c = c.NextSibling {
			findName(c)
		}
	}
	findName(panel)
	
	// Ищем значения фильтра
	var findValues func(*html.Node)
	findValues = func(n *html.Node) {
		if n.Type == html.ElementNode && n.Data == "label" {
			for _, attr := range n.Attr {
				if attr.Key == "class" && strings.Contains(attr.Val, "label-text") {
					text := fp.getTextContent(n)
					text = strings.TrimSpace(text)
					if text != "" {
						translitText := fp.translit.Translit(text)
						values = append(values, translitText)
					}
					return
				}
			}
		}
		for c := n.FirstChild; c != nil; c = c.NextSibling {
			findValues(c)
		}
	}
	findValues(panel)
	
	return filterName, values
}

// getTextContent извлекает текстовое содержимое узла
func (fp *FilterParser) getTextContent(n *html.Node) string {
	var text strings.Builder
	var extractText func(*html.Node)
	
	extractText = func(n *html.Node) {
		if n.Type == html.TextNode {
			text.WriteString(n.Data)
		}
		for c := n.FirstChild; c != nil; c = c.NextSibling {
			extractText(c)
		}
	}
	
	extractText(n)
	return text.String()
} 