// api/server.go
package api

import (
	"context"
	"fmt"
	"io"
	"log"
	"math/rand"
	"net"
	"net/http"
	"net/url"
	pb "proxy-api/fetch"
	"proxy-api/internal/config"
	"proxy-api/internal/proxy"
	"proxy-api/internal/scraper"
	"strings"
	"sync"
	"time"

	"google.golang.org/grpc"
)

var (
	validProxies map[string][]string
	userAgents   []string
)

type server struct {
	pb.UnimplementedProxyServiceServer
	successfulProxies map[string]*http.Client
	mtx               sync.RWMutex
}

var errorMap = map[string]struct{}{
	"context deadline exceeded (Client.Timeout or context cancellation while reading body)": {},
	"EOF":                       {},
	"read tcp":                  {},
	"connection":                {},
	"Timeout":                   {},
	"Forbidden":                 {},
	"(Client.Timeout":           {},
	"Internal Server Error":     {},
	"Bad Gateway":               {},
	"Service Unavailable":       {},
	"Gateway Timeout":           {},
	"Too many open connections": {},
	"unconfigured cipher suite": {},
	"ClientConn.Close":          {},
	"GOAWAY":                    {},
	"proxyconnect tcp:":         {},
	"Temporary Redirect":        {},
	"Internal Privoxy Error":    {},
	"certificate":               {},
	"bad record MAC":            {},
	"lookup":                    {},
}

func isTimeoutError(err error) bool {
	if urlErr, ok := err.(*url.Error); ok && urlErr.Timeout() {
		return true
	}

	for errMsg := range errorMap {
		if strings.Contains(err.Error(), errMsg) || err.Error() == errMsg {
			return true
		}
	}

	return false
}

var nilMap = map[string]struct{}{
	"<strong>Error:</strong>": {},
	"Marshal":                 {},
	"error while marshaling: proto: Marshal called with nilh": {},
	"Servicio no": {},
	"GOAWAY":      {},
	`http2: server sent GOAWAY and closed the connection;`:                      {},
	`{"code":110,"message":"Sport API error","name":"ServiceUnavailableError"}`: {},
	"http2:":          {},
	"temporary error": {},
}

func IsNilContent(content string) bool {
	for errMsg := range nilMap {
		if strings.Contains(content, errMsg) || content == errMsg {
			return true
		}
	}

	return false
}

func (s *server) getHTTPClient(proxyAddr string, redirect bool, session string) (*http.Client, error) {
	s.mtx.RLock()
	client, ok := s.successfulProxies[proxyAddr]
	s.mtx.RUnlock()

	if ok {
		return client, nil
	}

	if proxyAddr == "default" {
		return http.DefaultClient, nil
	}

	proxyURL, _ := url.Parse(proxyAddr)
	client = &http.Client{
		Transport: &http.Transport{
			Proxy: http.ProxyURL(proxyURL),
		},
		Timeout: time.Duration(config.ProxySessions[session].Timeout) * time.Millisecond,
	}

	if !redirect {
		client.CheckRedirect = func(req *http.Request, via []*http.Request) error {
			return http.ErrUseLastResponse
		}
	} else {
		client.CheckRedirect = func(req *http.Request, via []*http.Request) error {
			return nil
		}
	}

	s.mtx.Lock()
	s.successfulProxies[proxyAddr] = client
	s.mtx.Unlock()

	return client, nil
}

func (s *server) removeSuccesfulProxy(proxyAddr string) {
	s.mtx.Lock()
	delete(s.successfulProxies, proxyAddr)
	s.mtx.Unlock()
}

// WITHOUT PROXIES
func (s *server) Fetch(ctx context.Context, req *pb.Request, userAgent string, redirect bool) (*pb.Response, error) {
	client, err := s.getHTTPClient("default", redirect, req.Session)
	if err != nil {
		return nil, err
	}

	reqObj, err := http.NewRequestWithContext(ctx, "GET", req.Url, nil)
	if err != nil {
		return nil, err
	}

	reqObj.Header.Set("User-Agent", userAgent)
	for k, v := range config.GetHeadersFromSession(req.Session) {
		reqObj.Header.Set(k, v)
	}

	resp, err := client.Do(reqObj)
	if err != nil {
		// Retry if there is a timeout error.
		if ctx.Err() == context.DeadlineExceeded || isTimeoutError(err) {
			log.Println("Retry due to", err)
			return s.Fetch(ctx, req, userAgent, redirect)
		}

		return nil, err
	}
	defer resp.Body.Close()

	bodyBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	log.Printf("User-Agent: %s, Status: %d, URL: %s\n", userAgent, resp.StatusCode, req.Url)
	return &pb.Response{Content: bodyBytes}, nil
}

func (s *server) useProxyToFetch(ctx context.Context, req *pb.Request, proxyAddr string, userAgent string, redirect bool, contentChan chan []byte, errorChan chan error) {
	client, err := s.getHTTPClient(proxyAddr, redirect, req.Session)
	if err != nil {
		errorChan <- err
		return
	}

	reqObj, err := http.NewRequestWithContext(ctx, "GET", req.Url, nil)
	if err != nil {
		errorChan <- err
		return
	}

	reqObj.Header.Set("User-Agent", userAgent)
	for k, v := range config.GetHeadersFromSession(req.Session) {
		reqObj.Header.Set(k, v)
	}

	resp, err := client.Do(reqObj)
	if err != nil {
		s.removeSuccesfulProxy(proxyAddr) // remove the proxy from successfulProxies
		errorChan <- err
		return
	}
	defer resp.Body.Close()

	bodyBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		errorChan <- err
		return
	}

	log.Printf("Proxy: %s, User-Agent: %s, Status: %d, URL: %s", proxyAddr, userAgent, resp.StatusCode, req.Url)
	contentChan <- bodyBytes
}

func (s *server) FetchContent(ctx context.Context, req *pb.Request) (*pb.Response, error) {
	if req.Session == "" || validProxies[req.Session] == nil {
		return nil, fmt.Errorf("invalid session")
	}

	var redirect bool
	if req.Redirect {
		redirect = req.Redirect
	} else {
		redirect = false
	}

	selectedUserAgent := userAgents[rand.Intn(len(userAgents))]

	if req.Proxy {
		contentChan := make(chan []byte)
		errorChan := make(chan error)

		// Primero se utilizan los successfulProxies
		s.mtx.RLock()
		for proxyAddr := range s.successfulProxies {
			go s.useProxyToFetch(ctx, req, "http://"+proxyAddr, selectedUserAgent, redirect, contentChan, errorChan)
		}
		s.mtx.RUnlock()

		// Si falla, utiliza los validProxies
		if len(contentChan) == 0 {
			for _, proxyAddr := range validProxies[req.Session] {
				go s.useProxyToFetch(ctx, req, "http://"+proxyAddr, selectedUserAgent, redirect, contentChan, errorChan)
			}
		}

		for range validProxies[req.Session] {
			select {
			case content := <-contentChan:
				return &pb.Response{Content: content}, nil
			case <-errorChan:
				continue
			}
		}

		return s.Fetch(ctx, req, selectedUserAgent, redirect)
	}

	return s.Fetch(ctx, req, selectedUserAgent, redirect)
}

func UpdateValidProxies(proxies map[string][]string) {
	validProxies = proxies
}

func StartGRPCServer() {
	validProxies = proxy.GetValidProxies()
	userAgents = scraper.ScrapeUserAgents()

	log.Println("Iniciando servidor gRPC")
	lis, err := net.Listen("tcp", ":5000")
	if err != nil {
		log.Fatalf("failed to listen: %v", err)
	}

	maxSize := 5 * 1024 * 1024
	grpcServer := grpc.NewServer(
		grpc.MaxRecvMsgSize(maxSize), // Tamaño máximo de mensaje recibido.
		grpc.MaxSendMsgSize(maxSize), // Tamaño máximo de mensaje enviado.
	)
	pb.RegisterProxyServiceServer(grpcServer, &server{successfulProxies: make(map[string]*http.Client)})
	if err := grpcServer.Serve(lis); err != nil {
		log.Fatalf("failed to serve: %v", err)
	}

}
