package config

type ProxySession struct {
	Name    string
	URL     string
	Headers map[string]string
	Timeout int
}

var ProxySessions = map[string]ProxySession{
	/*"FlashScore": {
		Name: "FlashScore",
		URL:  "https://local-global.flashscore.ninja/2/x/feed/r_1_1",
		Headers: map[string]string{
			"Accept-Encoding":    "gzip, deflate, br",
			"Accept-Language":    "es-ES,es;q=0.9,en;q=0.8,zh-TW;q=0.7,zh;q=0.6,ja;q=0.5,zh-CN;q=0.4",
			"Origin":             "https://www.flashscore.es",
			"Referer":            "https://www.flashscore.es/",
			"Sec-Ch-Ua":          "'Google Chrome';v='117', 'Not;A=Brand';v='8', 'Chromium';v='117'",
			"Sec-Ch-Ua-Mobile":   "?0",
			"Sec-Ch-Ua-Platform": "'Windows'",
			"Sec-Fetch-Dest":     "empty",
			"Sec-Fetch-Mode":     "cors",
			"Sec-Fetch-Site":     "cross-site",
			"X-Fsign":            "SW9D1eZo",
		},
		Timeout: DefaultSessionTimeout,
	}, */
	"CoinMarketCap": {
		Name:    "CoinMarketCap",
		URL:     "https://coinmarketcap.com/es/",
		Headers: map[string]string{},
		Timeout: DefaultSessionTimeout,
	},
}

func GetHeadersFromSession(session string) map[string]string {
	return ProxySessions[session].Headers
}
