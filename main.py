"""
Punto de entrada principal del proxy server con pool de drivers
ACTUALIZADO: Límites de mensaje gRPC aumentados
"""
import logging
import threading
import time
import signal
import sys
from api.server import start_grpc_server, GRPC_OPTIONS, MAX_MESSAGE_SIZE
from internal.proxy.proxy import ProxyValidator
from internal.config.config import UPDATE_TIME_MINUTES

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Variable global para el servidor
current_servicer = None

def signal_handler(signum, frame):
    """Manejo de señales para cierre limpio"""
    logger.info("Señal de cierre recibida. Cerrando pools de drivers...")
    if current_servicer:
        current_servicer.close_pools()
    sys.exit(0)

def reload_proxies_background():
    """Función para recargar proxies en segundo plano"""
    proxy_validator = ProxyValidator(max_drivers=5)  # Menos drivers para background
    
    while True:
        try:
            time.sleep(UPDATE_TIME_MINUTES * 60)
            logger.info("Iniciando recarga de proxies...")
            
            new_proxy_map = proxy_validator.get_valid_proxies()
            total_proxies = sum(len(proxies) for proxies in new_proxy_map.values())
            
            logger.info(f"Proxies válidos refrescados: {total_proxies}")
            
            # Mostrar estadísticas del pool
            try:
                pool_stats = proxy_validator.driver_pool.get_stats()
                logger.info(f"Estadísticas del pool de validación: {pool_stats}")
            except AttributeError:
                logger.debug("Driver pool stats no disponibles")
            
        except Exception as e:
            logger.error(f"Error recargando proxies: {e}")
        finally:
            # Cerrar pool de validación para liberar recursos
            proxy_validator.close_driver_pool()

def start_grpc_server_wrapper():
    """Wrapper para el servidor gRPC que permite acceso al servicer con límites aumentados"""
    global current_servicer
    
    logger.info("Iniciando servidor gRPC en puerto 5000")
    
    from api.server import ProxyServicer
    import proxy_pb2_grpc
    import grpc
    from concurrent import futures
    
    current_servicer = ProxyServicer(max_drivers=10)
    
    # Crear servidor con opciones de límite de mensaje
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10),
        options=GRPC_OPTIONS  # Límites de mensaje aumentados
    )
    
    proxy_pb2_grpc.add_ProxyServiceServicer_to_server(current_servicer, server)
    
    listen_addr = '[::]:5000'
    server.add_insecure_port(listen_addr)
    
    server.start()
    logger.info(f"Servidor gRPC iniciado en {listen_addr}")
    logger.info(f"Límite de mensaje configurado: {MAX_MESSAGE_SIZE/1024/1024:.0f}MB")
    
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Cerrando servidor gRPC...")
        current_servicer.close_pools()
        server.stop(0)

def main():
    """Función principal"""
    logger.info("Iniciando Proxy Server Python con Pool de Drivers")
    logger.info(f"Límite de mensaje gRPC: {MAX_MESSAGE_SIZE/1024/1024:.0f}MB")
    
    # Configurar manejo de señales
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Iniciar el servidor gRPC en un hilo separado
    grpc_thread = threading.Thread(target=start_grpc_server_wrapper, daemon=True)
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
        if current_servicer:
            current_servicer.close_pools()

if __name__ == "__main__":
    main()