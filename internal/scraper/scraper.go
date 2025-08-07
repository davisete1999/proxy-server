package scraper

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

type Scraper struct {
	urls     []string
	dataType string
}

func NewScraper(urls []string, dataType string) *Scraper {
	return &Scraper{
		urls:     urls,
		dataType: dataType,
	}
}

func (s *Scraper) Scrape(ctx context.Context) []string {
	resultChan := make(chan []string)
	errChan := make(chan error)

	for _, url := range s.urls {
		go s.fetchData(ctx, url, resultChan, errChan)
	}

	timeout := time.After(25 * time.Second)
	var results []string
	for i := 0; i < len(s.urls); i++ {
		select {
		case res := <-resultChan:
			results = append(results, res...)
		case err := <-errChan:
			fmt.Printf("Error scraping %s data: %s\n", s.dataType, err)
		case <-timeout:
			fmt.Println("Scraping timed out.")
			return results
		}
	}
	return results
}

func (s *Scraper) fetchData(ctx context.Context, url string, resultChan chan []string, errChan chan error) {
	fmt.Printf("Obteniendo %s de %s...\n", s.dataType, url)

	req, _ := http.NewRequest(http.MethodGet, url, nil)
	resp, err := http.DefaultClient.Do(req.WithContext(ctx))
	if err != nil {
		errChan <- err
		return
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		errChan <- err
		return
	}

	lines := strings.Split(string(body), "\n")
	var validLines []string
	for _, line := range lines {
		trimmed := strings.TrimSpace(line)
		if strings.Count(trimmed, ":") > 1 {
			trimmed = strings.Split(trimmed, ":")[0] + ":" + strings.Split(trimmed, ":")[1]
		}
		if trimmed != "" || (strings.Contains(url, "user-agents") && (!strings.Contains(trimmed, "Android") &&
			!strings.Contains(trimmed, "iPhone") &&
			!strings.Contains(trimmed, "iPad") &&
			!strings.Contains(trimmed, "compatible;"))) {

			validLines = append(validLines, trimmed)
		}
	}
	resultChan <- validLines
}

func ScrapeProxies() []string {
	urls := []string{
		// "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",
		// "https://raw.githubusercontent.com/proxifly/free-proxy-list/refs/heads/main/proxies/all/data.txt",
		"https://raw.githubusercontent.com/officialputuid/KangProxy/refs/heads/KangProxy/https/https.txt",
		"https://raw.githubusercontent.com/vakhov/fresh-proxy-list/refs/heads/master/https.txt",
		// "https://raw.githubusercontent.com/prxchk/proxy-list/main/http.txt",
		// "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",
		// "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/http.txt",
		// "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/http.txt",
		// "https://raw.githubusercontent.com/ProxyScraper/ProxyScraper/main/http.txt",
	}
	scraper := NewScraper(urls, "proxies")
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	return scraper.Scrape(ctx)
}

func ScrapeUserAgents() []string {
	urls := []string{
		"https://gist.githubusercontent.com/pzb/b4b6f57144aea7827ae4/raw/cf847b76a142955b1410c8bcef3aabe221a63db1/user-agents.txt",
	}
	scraper := NewScraper(urls, "user-agents")
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	// Número máximo de intentos
	maxRetries := 3

	for attempt := 1; attempt <= maxRetries; attempt++ {
		result := scraper.Scrape(ctx)
		if len(result) > 0 {
			// Si la operación tiene éxito, retornar los datos
			return result
		}

		// Si la operación falla, esperar un momento antes de volver a intentar
		fmt.Printf("Intento %d fallido. Reintentando...\n", attempt)
		scraper = NewScraper(urls, "user-agents")
		time.Sleep(2 * time.Second)
	}

	// Si todos los intentos fallan, retornar una lista vacía o manejar el error de otra manera.
	return []string{}
}
