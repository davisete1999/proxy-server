#!/usr/bin/env bash
set -euo pipefail

# Nos movemos al directorio raíz (uno arriba de scripts/)
cd "$(dirname "${BASH_SOURCE[0]}")/.."

PROTO_DIR="protos"
OUT_DIR="."

# Verificar que exista el .proto
if [ ! -f "${PROTO_DIR}/proxy.proto" ]; then
  echo "Error: No se encontró ${PROTO_DIR}/proxy.proto"
  exit 1
fi

# Generar los bindings de Python
python -m grpc_tools.protoc \
  --proto_path="${PROTO_DIR}" \
  --python_out="${OUT_DIR}" \
  --grpc_python_out="${OUT_DIR}" \
  "${PROTO_DIR}/proxy.proto"

echo "✅ Archivos Python generados en ${OUT_DIR}:"
echo "   - proxy_pb2.py"
echo "   - proxy_pb2_grpc.py"
