#!/usr/bin/env bash

# Script para resolver problemas de compatibilidad con gRPC
set -e

echo "=== Solucionando problemas de compatibilidad gRPC ==="

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Función para imprimir mensajes coloreados
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 1. Verificar que Go está instalado
if ! command -v go &> /dev/null; then
    print_error "Go no está instalado. Por favor instálalo desde https://golang.org/"
    exit 1
fi

print_status "Go versión: $(go version)"

# 2. Limpiar módulos y caché
print_status "Limpiando caché de módulos Go..."
go clean -modcache
go mod tidy

# 3. Actualizar dependencias
print_status "Actualizando dependencias..."
go get -u google.golang.org/grpc@latest
go get -u google.golang.org/protobuf@latest
go mod tidy

# 4. Instalar/actualizar herramientas de protoc
print_status "Instalando herramientas de Protocol Buffers..."

# Verificar si protoc está instalado
if ! command -v protoc &> /dev/null; then
    print_error "protoc no está instalado."
    echo "Por favor instálalo:"
    echo "  - Ubuntu/Debian: sudo apt install protobuf-compiler"
    echo "  - macOS: brew install protobuf"
    echo "  - Windows: Descarga desde https://github.com/protocolbuffers/protobuf/releases"
    exit 1
fi

print_status "protoc versión: $(protoc --version)"

# Instalar plugins de Go para protoc
print_status "Instalando plugins de protoc para Go..."
go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest

# Verificar que los plugins están en el PATH
if ! command -v protoc-gen-go &> /dev/null; then
    print_warning "protoc-gen-go no está en el PATH"
    echo "Asegúrate de que \$GOPATH/bin está en tu PATH:"
    echo "export PATH=\$PATH:\$(go env GOPATH)/bin"
fi

if ! command -v protoc-gen-go-grpc &> /dev/null; then
    print_warning "protoc-gen-go-grpc no está en el PATH"
    echo "Asegúrate de que \$GOPATH/bin está en tu PATH:"
    echo "export PATH=\$PATH:\$(go env GOPATH)/bin"
fi

# 5. Crear directorio fetch si no existe
mkdir -p fetch

# 6. Crear archivo proto actualizado
print_status "Creando archivo proto actualizado..."
cat > fetch/proxy.proto << 'EOF'
syntax = "proto3";

package fetch;

option go_package = "proxy-api/fetch";

// Servicio principal de proxy
service ProxyService {
    // Método existente para obtener contenido
    rpc FetchContent(Request) returns (Response);
    
    // Nuevo método para obtener un proxy aleatorio
    rpc GetRandomProxy(ProxyRequest) returns (ProxyResponse);
    
    // Método adicional para obtener estadísticas de proxies
    rpc GetProxyStats(StatsRequest) returns (StatsResponse);
}

// Mensaje de solicitud existente
message Request {
    string url = 1;
    string session = 2;
    bool proxy = 3;
    bool redirect = 4;
}

// Mensaje de respuesta existente
message Response {
    bytes content = 1;
}

// Nuevo mensaje para solicitar un proxy aleatorio
message ProxyRequest {
    string session = 1; // Sesión para la cual obtener el proxy
}

// Nuevo mensaje de respuesta para proxy aleatorio
message ProxyResponse {
    string proxy = 1;   // Dirección del proxy (ip:port)
    bool success = 2;   // Indica si la operación fue exitosa
    string message = 3; // Mensaje descriptivo del resultado
}

// Mensaje para solicitar estadísticas
message StatsRequest {
    // Vacío por ahora, podría expandirse en el futuro
}

// Mensaje de respuesta con estadísticas
message StatsResponse {
    map<string, int32> proxy_count_by_session = 1; // Cantidad de proxies por sesión
    int32 total_valid_proxies = 2;                 // Total de proxies válidos
}
EOF

# 7. Eliminar archivos proto generados anteriormente
print_status "Eliminando archivos proto generados anteriormente..."
rm -f fetch/*.pb.go

# 8. Generar nuevos archivos proto
print_status "Generando archivos proto..."
protoc \
    --proto_path=fetch \
    --go_out=fetch \
    --go_opt=paths=source_relative \
    --go-grpc_out=fetch \
    --go-grpc_opt=paths=source_relative \
    fetch/proxy.proto

# 9. Verificar que los archivos se generaron correctamente
if [ -f "fetch/proxy.pb.go" ] && [ -f "fetch/proxy_grpc.pb.go" ]; then
    print_status "✅ Archivos proto generados exitosamente"
else
    print_error "❌ Error generando archivos proto"
    exit 1
fi

# 10. Intentar compilar el proyecto
print_status "Verificando compilación del proyecto..."
if go build ./cmd/main.go; then
    print_status "✅ Proyecto compilado exitosamente"
    rm -f main # Limpiar binario de prueba
else
    print_error "❌ Error compilando el proyecto"
    echo "Revisa los errores anteriores e intenta de nuevo"
    exit 1
fi

# 11. Mostrar información de las dependencias
print_status "Información de dependencias actuales:"
go list -m all | grep -E "(grpc|protobuf)"

echo ""
print_status "🎉 ¡Problema resuelto! El proyecto debería compilar correctamente ahora."
echo ""
echo "Próximos pasos:"
echo "1. go build ./cmd/main.go"
echo "2. ./main"
echo "3. go run client/main.go (en otra terminal)"