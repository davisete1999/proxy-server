"""
Configuración general del sistema
"""

# Tamaño del chunk de proxies para procesamiento
DEFAULT_CHUNK_SIZE = 20

# Timeout por defecto para sesiones (en milisegundos)
DEFAULT_SESSION_TIMEOUT = 2000

# Tiempo de actualización de proxies (en minutos)
UPDATE_TIME_MINUTES = 30

# Configuración de Selenium
SELENIUM_TIMEOUT = 10  # segundos
SELENIUM_RETRIES = 3

# User agents por defecto
DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]