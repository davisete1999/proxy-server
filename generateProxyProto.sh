#!/usr/bin/env bash

# Script para generar archivos gRPC desde el archivo proto
# Asegúrate de tener instalados:
# - protoc (Protocol Buffers compiler)
# - protoc-gen-go (Go plugin para protoc)
# - protoc-gen-go-grpc (gRPC Go plugin)

set -e

echo "=== Generando archivos gRPC desde proxy_service.proto ==="

# Directorio donde está el archivo proto
PROTO_DIR="fetch/"
# Directorio de salida para los archivos generados
OUT_DIR="fetch/"

# Crear directorio de salida si no existe
mkdir -p "$OUT_DIR"

# Verificar que existe el archivo proto
if [ ! -f "$PROTO_DIR/proxy_service.proto" ]; then
    echo "Error: No se encontró el archivo proxy_service.proto en $PROTO_DIR"
    echo "Por favor asegúrate de que el archivo proto existe."
    exit 1
fi

# Verificar que protoc está instalado
if ! command -v protoc &> /dev/null; then
    echo "Error: protoc no está instalado."
    echo "Instálalo desde: https://grpc.io/docs/protoc-installation/"
    exit 1
fi

# Verificar que los plugins de Go están instalados
if ! command -v protoc-gen-go &> /dev/null; then
    echo "Error: protoc-gen-go no está instalado."
    echo "Instálalo con: go install google.golang.org/protobuf/cmd/protoc-gen-go@latest"
    exit 1
fi

if ! command -v protoc-gen-go-grpc &> /dev/null; then
    echo "Error: protoc-gen-go-grpc no está instalado."
    echo "Instálalo con: go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest"
    exit 1
fi

echo "Generando archivos Go desde proxy_service.proto..."

# Generar archivos Go
protoc \
    --proto_path="$PROTO_DIR" \
    --go_out="$OUT_DIR" \
    --go_opt=paths=source_relative \
    --go-grpc_out="$OUT_DIR" \
    --go-grpc_opt=paths=source_relative \
    "$PROTO_DIR/proxy_service.proto"

echo "✅ Archivos Go generados exitosamente en $OUT_DIR"

# Opcional: Generar para otros lenguajes
read -p "¿Quieres generar también archivos para Python? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    PYTHON_OUT="./generated/python"
    mkdir -p "$PYTHON_OUT"
    
    if command -v python3 &> /dev/null && python3 -c "import grpc_tools" &> /dev/null; then
        echo "Generando archivos Python..."
        python3 -m grpc_tools.protoc \
            --proto_path="$PROTO_DIR" \
            --python_out="$PYTHON_OUT" \
            --grpc_python_out="$PYTHON_OUT" \
            "$PROTO_DIR/proxy_service.proto"
        echo "✅ Archivos Python generados en $PYTHON_OUT"
    else
        echo "❌ Python3 o grpc_tools no están disponibles"
        echo "Instala con: pip install grpcio-tools"
    fi
fi

read -p "¿Quieres generar también archivos para JavaScript/TypeScript? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    JS_OUT="./generated/javascript"
    mkdir -p "$JS_OUT"
    
    if command -v npm &> /dev/null; then
        echo "Generando archivos JavaScript..."
        protoc \
            --proto_path="$PROTO_DIR" \
            --js_out=import_style=commonjs,binary:"$JS_OUT" \
            --grpc-web_out=import_style=commonjs,mode=grpcwebtext:"$JS_OUT" \
            "$PROTO_DIR/proxy_service.proto"
        echo "✅ Archivos JavaScript generados en $JS_OUT"
    else
        echo "❌ npm no está disponible"
    fi
fi

echo ""
echo "=== Generación completada ==="
echo "Archivos principales generados:"
echo "  - $OUT_DIR/proxy.pb.go (mensajes Protocol Buffers)"
echo "  - $OUT_DIR/proxy_grpc.pb.go (servicio gRPC)"
echo ""
echo "Para usar estos archivos en tu proyecto Go:"
echo "  import fetch \"proxy-api/fetch\""
echo ""
echo "Para recompilar el proyecto:"
echo "  go build ./cmd/main.go"