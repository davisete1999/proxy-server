package main

import (
	"bytes"
	"compress/gzip"
	"context"
	"fmt"
	"io"
	"log"
	fetch "proxy-api/fetch"
	"sync"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

func createClient() (fetch.ProxyServiceClient, *grpc.ClientConn) {
	conn, err := grpc.Dial(":5000", grpc.WithTransportCredentials(insecure.NewCredentials())) // Conexión sin cifrado para propósitos de ejemplo
	if err != nil {
		log.Fatalf("Did not connect: %s", err)
	}
	return fetch.NewProxyServiceClient(conn), conn
}

func DecompressAndConvertToString(data []byte) (string, error) {
	reader, err := gzip.NewReader(bytes.NewReader(data))
	if err != nil {
		return "", err
	}
	defer reader.Close()

	decompressedData, err := io.ReadAll(reader)
	if err != nil {
		return "", err
	}

	return string(decompressedData), nil
}

func main() {

	const numRequests = 500
	var wg sync.WaitGroup
	wg.Add(numRequests)

	successfulRequests := 0
	mutex := &sync.Mutex{}

	startTime := time.Now()

	client, conn := createClient() // Crear un nuevo cliente para cada solicitud

	defer conn.Close()
	fmt.Println("e")
	for i := 0; i < numRequests; i++ {
		go func() {
			defer wg.Done()

			//var retries int

			var response *fetch.Response
			var err error

			//for {
			//response, err = client.FetchContent(context.Background(), &fetch.Request{
			//	Url:      "https://translate.googleapis.com/translate_a/single?client=gtx&sl=es&tl=en&dt=q&q=Hello",
			//	Session:  "GoogleTranslate",
			//	Proxy:    true,
			//	Redirect: false,
			//})
			response, err = client.FetchContent(context.Background(), &fetch.Request{
				Url:      "https://local-global.flashscore.ninja/2/x/feed/r_1_1",
				Session:  "FlashScore",
				Proxy:    false,
				Redirect: false,
			})

			/*html, err := DecompressAndConvertToString(response.Content)
			if err != nil {
				fmt.Printf("Error: %s\n", err)
			}*/

			if err == nil && response != nil {
				fmt.Println(response.Content)
				mutex.Lock()
				successfulRequests++
				mutex.Unlock()
			} else {
				fmt.Printf("Error: %s\n", err)
			}
		}()
	}

	wg.Wait()
	elapsedTime := time.Since(startTime)

	fmt.Printf("Total time for %d requests: %s\n", numRequests, elapsedTime)
	fmt.Printf("Successful requests: %d\n", successfulRequests)
	fmt.Printf("Failed requests: %d\n", numRequests-successfulRequests)
}
