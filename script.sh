#!/usr/bin/env bash

# Nombre del archivo de salida
OUTPUT="esquema.txt"

# Patrones a excluir (incluye el propio OUTPUT)
EXCLUDE_PATTERNS=(
  "$OUTPUT"        # No incluir el archivo de salida
  ".git"           # Control de versiones
  "node_modules"   # Dependencias de Node.js
  ".DS_Store"      # Metadatos en macOS
  "Thumbs.db"      # Metadatos en Windows
  "__pycache__"    # Cachés de Python
  "*.pyc"          # Archivos compilados de Python
  "*.o"            # Objetos compilados (C/C++)
  "*.so"           # Librerías compartidas
  "venv"           # Entorno virtual de Python
  "dist"           # Carpeta de distribución
  "proxyserver"      # Archivos de caché de fetch
  "fetch"         # Archivos de caché de fetch
  ".gitignore"    # Ignorar archivos de configuración de git
  "main"          # Archivos de caché de fetch
  "requirements.txt" # Archivo de dependencias
  "input"         # Archivo de entrada para SCM
)

# 1) Truncar o crear el archivo de salida sin preguntar
: > "$OUTPUT"

# 2) Construir la expresión de prune para find
prune_args=()
for pat in "${EXCLUDE_PATTERNS[@]}"; do
  prune_args+=( -name "$pat" -o )
done
# Eliminar el último '-o'
unset 'prune_args[${#prune_args[@]}-1]'

# 3) Estructura de directorios y archivos
echo "=== Estructura de directorios y archivos ===" >> "$OUTPUT"
find . -mindepth 1 \( "${prune_args[@]}" \) -prune -o -print | \
  sed \
    -e 's|[^/]*/|│   |g' \
    -e 's|│   \([^│]\)|├── \1|' \
  >> "$OUTPUT"
echo >> "$OUTPUT"

# 4) Contenido de cada archivo
echo "=== Contenido de archivos ===" >> "$OUTPUT"
find . -mindepth 1 \( "${prune_args[@]}" \) -prune -o \( -type f ! -name "$OUTPUT" -print \) | sort | \
while IFS= read -r file; do
  rel="${file#./}"
  echo "----- [Archivo: $rel] -----" >> "$OUTPUT"
  if [ -r "$file" ] && [ ! -d "$file" ]; then
    cat "$file" >> "$OUTPUT"
  else
    echo "[No se puede leer: $rel]" >> "$OUTPUT"
  fi
  echo >> "$OUTPUT"
done
