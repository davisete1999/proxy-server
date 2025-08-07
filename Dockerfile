# Usa una imagen de Go como base
FROM golang AS builder

# Configura las variables de entorno
ENV GO111MODULE=on \
    CGO_ENABLED=0 \
    GOOS=linux \
    GOARCH=amd64

# Crea un directorio de trabajo dentro del contenedor
WORKDIR /build

# Copia los archivos del proyecto al directorio de trabajo
COPY . .

# Compila la aplicación
RUN go build -o main ./cmd/main.go

# Empieza a construir la imagen final
FROM alpine:latest

# Instala las dependencias necesarias
RUN apk --no-cache add ca-certificates

# Copia el binario compilado desde la etapa anterior
COPY --from=builder /build/main /app/main

# Establece el directorio de trabajo
WORKDIR /app

# Expone el puerto en el que la aplicación escucha
EXPOSE 5000

# Ejecuta la aplicación cuando el contenedor se inicia
CMD ["./main"]