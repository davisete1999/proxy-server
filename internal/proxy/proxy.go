package proxy

import (
	"log"
	"net/http"
	"net/url"
	"proxy-api/internal/config"
	"proxy-api/internal/scraper"
	"sync"
	"time"
)

// Tamaño del chunk, idealmente esto debería venir de un archivo de configuración
const ChunkSize = config.DefaultChunkSize

// ValidProxies almacena los proxies válidos, con locking para acceso seguro
var (
	ValidProxies = make(map[string][]string)
	mutex        = &sync.Mutex{}
)

// Procesar un solo test de proxy
func RunProxyTest(cfg config.ProxySession, proxy string) {
	proxyURL, err := url.Parse("http://" + proxy)
	if err != nil {
		log.Printf("Error al parsear el proxy %s: %v", proxy, err)
		return
	}

	httpClient := &http.Client{
		Transport: &http.Transport{
			Proxy: http.ProxyURL(proxyURL),
		},
		Timeout: time.Duration(cfg.Timeout) * time.Millisecond,
	}

	request, err := http.NewRequest("GET", cfg.URL, nil)
	if err != nil {
		log.Printf("Error al crear la solicitud: %v", err)
		return
	}

	for headerName, headerValue := range cfg.Headers {
		request.Header.Set(headerName, headerValue)
	}

	request.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36")

	resp, err := httpClient.Do(request)
	if err != nil || (resp != nil && resp.StatusCode != 200) {
		log.Printf("Proxy %s no válido para %s", proxy, cfg.Name)
		if resp != nil {
			resp.Body.Close()
		}
		return
	}

	mutex.Lock()
	ValidProxies[cfg.Name] = append(ValidProxies[cfg.Name], proxy)
	mutex.Unlock()

	if resp != nil {
		resp.Body.Close()
	}
}

// Procesar todos los tests en un proxy
func runAllTests(proxy string) {
	var wg sync.WaitGroup
	wg.Add(len(config.ProxySessions))

	for _, test := range config.ProxySessions {
		go func(test config.ProxySession) {
			defer wg.Done()
			RunProxyTest(test, proxy)
		}(test)
	}

	wg.Wait()
}

// Divide los proxies en chunks más manejables
func chunkProxies(proxies []string) [][]string {
	var chunks [][]string
	for i := 0; i < len(proxies); i += ChunkSize {
		end := i + ChunkSize
		if end > len(proxies) {
			end = len(proxies)
		}
		chunks = append(chunks, proxies[i:end])
	}
	return chunks
}

// ValidateProxies realiza la validación de la lista de proxies
func GetValidProxies() map[string][]string {
	proxies := scraper.ScrapeProxies()
	chunks := chunkProxies(proxies)
	var wg sync.WaitGroup
	var progressMutex sync.Mutex
	chunksProcessed := 0

	for _, chunk := range chunks {
		wg.Add(1)
		go func(chunk []string) {
			defer wg.Done()
			for _, proxy := range chunk {
				runAllTests(proxy)
			}

			progressMutex.Lock()
			chunksProcessed++
			log.Printf("Progreso: %d/%d chunks procesados.", chunksProcessed, len(chunks))
			progressMutex.Unlock()

		}(chunk)
	}

	wg.Wait()

	mutex.Lock()
	defer mutex.Unlock()
	for site, proxies := range ValidProxies {
		log.Printf("Sitio web: %s | Proxies: %v", site, len(proxies))
	}

	return ValidProxies
}
