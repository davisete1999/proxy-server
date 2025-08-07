"""
Configuración optimizada para validación rápida de proxies
"""

# Tamaño de chunk más pequeño para mejor paralelización
DEFAULT_CHUNK_SIZE = 10

# Timeout reducido para validación rápida (en milisegundos)
DEFAULT_SESSION_TIMEOUT = 1500
VALIDATION_TIMEOUT = 800  # Timeout específico para validación

# Tiempo de actualización más frecuente
UPDATE_TIME_MINUTES = 15

# Configuración de Selenium optimizada
SELENIUM_TIMEOUT = 3  # Reducido de 10 a 3 segundos
SELENIUM_RETRIES = 1  # Reducido de 3 a 1

# Pool de drivers optimizado
MAX_VALIDATION_DRIVERS = 25  # Aumentado para mayor concurrencia
MAX_CONCURRENT_TESTS = 15    # Más tests concurrentes
MAX_CHUNK_WORKERS = 8        # Más workers por chunk

# User agents optimizados (solo desktop rápidos)
DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
]
