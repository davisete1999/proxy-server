# Instrucciones Avanzadas para el Uso del Proyecto Proxy-API

## Montaje de la Imagen Docker en Segundo Plano

Además del uso de `docker-compose`, puedes construir y ejecutar la imagen Docker manualmente.

### Construir la Imagen con Docker Build

1. **Construye la imagen Docker:**
   ```sh
   docker build -t proxy-api .
   ```

   Esto creará una imagen Docker llamada `proxy-api` utilizando el `Dockerfile` presente en el proyecto.

2. **Ejecutar la imagen en segundo plano:**
   ```sh
   docker run -d -p 5000:5000 --name proxy_server proxy-api
   ```

   Este comando ejecutará un contenedor basado en la imagen `proxy-api`, exponiendo el puerto 5000 y ejecutándose en segundo plano.

## Uso de los Archivos Proto en Otros Proyectos

Para generar los archivos necesarios para utilizar el servicio gRPC en otros proyectos:

1. **Ejecuta el script `generateProxyProto.sh`:**
   ```sh
   ./generateProxyProto.sh
   ```

   Esto generará los archivos necesarios en los lenguajes especificados (por ejemplo, Go, Python, etc.) a partir del archivo `proto`.

2. **Importa los archivos generados en tu proyecto cliente:**
   Utiliza estos archivos en tu proyecto cliente para interactuar con el servicio gRPC del Proxy-API.

## Sesiones y su Uso

Las sesiones en `config.ProxySessions` permiten especificar configuraciones particulares para diferentes destinos web. Cada sesión define un conjunto de encabezados HTTP, una URL y un tiempo de espera. Estas sesiones permiten adaptar las solicitudes a las particularidades de cada recurso web, como diferentes mecanismos de autenticación o requerimientos de encabezados específicos.

### Ejemplo de Sesiones

```go
var ProxySessions = map[string]ProxySession{
	"GoogleTranslateAPI": {
		Name:    "GoogleTranslateAPI",
		URL:     "https://translate.googleapis.com/translate_a/single...",
		Headers: map[string]string{},
		Timeout: DefaultSessionTimeout,
	},
	"GoogleTranslateClient": {
		Name:    "GoogleTranslateClient",
		URL:     "https://clients5.google.com/translate_a/t...",
		Headers: map[string]string{},
		Timeout: DefaultSessionTimeout,
	},
}
```

### Uso en el Servicio gRPC

Al realizar una solicitud a través del servicio `FetchContent` de gRPC, puedes especificar una de estas sesiones. El servidor Proxy-API utilizará la configuración de la sesión elegida para personalizar la solicitud HTTP.

#### Ejemplo de Uso de Sesiones en una Solicitud gRPC

```proto
message Request {
    string url = 1; // URL a acceder
    string session = 2; // Nombre de la sesión a utilizar
    bool proxy = 3; // Indica si se debe usar un proxy
    bool redirect = 4; // Permite o impide redirecciones automáticas
}
```

En el campo `session`, incluye el nombre de la sesión deseada, como `GoogleTranslateAPI` o `GoogleTranslateClient`. Esto permitirá que el servicio Proxy-API use las configuraciones específicas de esa sesión al realizar la solicitud.

## Conclusión

Con estas instrucciones avanzadas, deberías ser capaz de construir y ejecutar el servicio Proxy-API, tanto directamente como a través de Docker, y utilizar sus capacidades en otros proyectos mediante los archivos generados por `generateProxyProto.sh`. Además, puedes aprovechar las sesiones para realizar solicitudes personalizadas a diferentes servicios web.