## README.md
# Proxy Server Python con Selenium

Un servidor proxy HTTP/HTTPS implementado en Python que utiliza Selenium para validación de proxies y obtención de contenido web. Este proyecto es una implementación equivalente del proxy server original en Go, pero aprovechando las capacidades de Selenium para mayor compatibilidad con sitios web modernos.

## Características

- **Servidor gRPC** con múltiples métodos de servicio
- **Validación de proxies con Selenium** para mayor precisión
- **Sistema de sesiones** configurables por sitio web
- **Scraping automático** de proxies y user agents
- **Fallback inteligente** entre Selenium y requests
- **Contenedorización con Docker**
- **Actualización automática** de proxies en segundo plano

## Estructura del Proyecto

```
proxy-server-python/
├── requirements.txt          # Dependencias Python
├── docker-compose.yml        # Configuración Docker Compose
├── Dockerfile               # Imagen Docker
├── main.py                  # Punto de entrada principal
├── protos/
│   └── proxy.proto          # Definición del servicio gRPC
├── api/
│   └── server.py            # Implementación del servidor gRPC
├── internal/
│   ├── config/
│   │   ├── config.py        # Configuración general
│   │   └── sessions.py      # Configuración de sesiones
│   ├── proxy/
│   │   └── proxy.py         # Validación de proxies con Selenium
│   └── scraper/
│       └── scraper.py       # Scraping de proxies y user agents
└── scripts/
    ├── generate_proto.sh    # Script para generar archivos proto
    └── test_client.py       # Cliente de prueba
```

## Instalación y Uso

### Método 1: Docker Compose (Recomendado)

```bash
# Clonar y entrar al directorio
git clone <repository>
cd proxy-server-python

# Ejecutar con Docker Compose
docker-compose up --build
```

### Método 2: Instalación Local

```bash
# Instalar dependencias
pip install -r requirements.txt

# Generar archivos gRPC
chmod +x scripts/generate_proto.sh
./scripts/generate_proto.sh

# Ejecutar servidor
python main.py
```

### Método 3: Docker Manual

```bash
# Construir imagen
docker build -t proxy-server-python .

# Ejecutar contenedor
docker run -d -p 5000:5000 --name proxy_server proxy-server-python
```

## Uso del Cliente

```python
import grpc
import proxy_pb2
import proxy_pb2_grpc

# Conectar al servidor
channel = grpc.insecure_channel('localhost:5000')
stub = proxy_pb2_grpc.ProxyServiceStub(channel)

# Obtener contenido con proxy
request = proxy_pb2.Request(
    url="https://httpbin.org/ip",
    session="TestSession",
    proxy=True,
    redirect=True
)
response = stub.FetchContent(request)
print(response.content.decode())

# Obtener proxy aleatorio
proxy_request = proxy_pb2.ProxyRequest(session="TestSession")
proxy_response = stub.GetRandomProxy(proxy_request)
print(f"Proxy: {proxy_response.proxy}")

# Obtener estadísticas
stats_request = proxy_pb2.StatsRequest()
stats_response = stub.GetProxyStats(stats_request)
print(f"Total proxies: {stats_response.total_valid_proxies}")
```

## Configuración de Sesiones

Las sesiones permiten configurar diferentes parámetros para distintos sitios web:

```python
PROXY_SESSIONS = {
    "MiSitio": ProxySession(
        name="MiSitio",
        url="https://ejemplo.com/api",
        headers={
            "Authorization": "Bearer token",
            "Accept": "application/json",
        },
        timeout=5000,  # milisegundos
    )
}
```

## API gRPC

### Métodos Disponibles

1. **FetchContent**: Obtiene contenido de una URL usando proxies
2. **GetRandomProxy**: Obtiene un proxy aleatorio válido para una sesión
3. **GetProxyStats**: Obtiene estadísticas de proxies por sesión

### Mensajes

- `Request`: URL, sesión, usar proxy, permitir redirects
- `Response`: Contenido en bytes
- `ProxyRequest`: Sesión
- `ProxyResponse`: Proxy, éxito, mensaje
- `StatsRequest`: Vacío
- `StatsResponse`: Estadísticas por sesión

## Diferencias con la Versión Go

### Ventajas de la Versión Python

- **Selenium WebDriver**: Mejor manejo de JavaScript y sitios modernos
- **Flexibilidad**: Más fácil de modificar y extender
- **Ecosistema Python**: Acceso a librerías especializadas
- **Debugging**: Herramientas de debugging más avanzadas

### Consideraciones de Rendimiento

- **Memoria**: Selenium consume más memoria que requests simples
- **Velocidad**: Selenium es más lento pero más preciso
- **Fallback**: Sistema de fallback a requests para mejor rendimiento

## Monitoreo y Logs

El servidor proporciona logs detallados:

```
2024-01-15 10:30:00 - INFO - Iniciando Proxy Server Python con Selenium
2024-01-15 10:30:01 - INFO - Servidor gRPC iniciado en [::]:5000
2024-01-15 10:30:05 - INFO - Validando 150 proxies...
2024-01-15 10:32:10 - INFO - Validación completada. Total de proxies válidos: 25
```

## Troubleshooting

### Chrome/ChromeDriver Issues

```bash
# Instalar Chrome manualmente
wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list
apt-get update && apt-get install -y google-chrome-stable
```

### Memoria Insuficiente

```bash
# Aumentar memoria compartida en Docker
docker run --shm-size=2g -p 5000:5000 proxy-server-python
```

### Permisos

```bash
# Dar permisos a scripts
chmod +x scripts/*.sh
```

## Contribuir

1. Fork el proyecto
2. Crear rama feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -am 'Agregar nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

## Licencia

MIT License - ver archivo LICENSE para detalles.