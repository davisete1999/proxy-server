package main

import (
	"fmt"
	"proxy-api/api"
	"proxy-api/internal/config"
	"proxy-api/internal/proxy"
	"time"
)

func main() {
	// Iniciar el servidor gRPC
	go api.StartGRPCServer()

	// Refrescar proxies al inicio
	go reloadProxiesInBackground()

	// Mantener la aplicación en ejecución
	select {}
}

func reloadProxiesInBackground() {
	for {
		time.Sleep(config.UpdateTime * time.Minute)

		newProxyMap := proxy.GetValidProxies()
		fmt.Printf("Proxies válidos refrescados: %d\n", len(newProxyMap))

		// Update the valid proxies in the server
		api.UpdateValidProxies(newProxyMap)
	}
}
