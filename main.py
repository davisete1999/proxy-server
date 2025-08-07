"""
Punto de entrada principal del proxy server
"""
import asyncio
import logging
import threading
import time
from api.server import start_grpc_server
from internal.proxy.proxy import ProxyValidator
from internal.config.config import UPDATE_TIME_MINUTES

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def reload_proxies_background():
    """Función para recargar proxies en segundo plano"""
    proxy_validator = ProxyValidator()
    
    while True:
        try:
            time.sleep(UPDATE_TIME_MINUTES * 60)
            logger.info("Iniciando recarga de proxies...")
            
            new_proxy_map = proxy_validator.get_valid_proxies()
            total_proxies = sum(len(proxies) for proxies in new_proxy_map.values())
            
            logger.info(f"Proxies válidos refrescados: {total_proxies}")
            
        except Exception as e:
            logger.error(f"Error recargando proxies: {e}")

def main():
    """Función principal"""
    logger.info("Iniciando Proxy Server Python con Selenium")
    
    # Iniciar el servidor gRPC en un hilo separado
    grpc_thread = threading.Thread(target=start_grpc_server, daemon=True)
    grpc_thread.start()
    
    # Iniciar la recarga de proxies en segundo plano
    reload_thread = threading.Thread(target=reload_proxies_background, daemon=True)
    reload_thread.start()
    
    try:
        # Mantener la aplicación en ejecución
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Cerrando servidor...")

if __name__ == "__main__":
    main()