"""
Punto de entrada principal del proxy server con pool de drivers
ACTUALIZADO: Auto-reinicio cada 3 horas y límites de mensaje gRPC aumentados
"""
import logging
import threading
import time
import signal
import sys
import os
from datetime import datetime, timedelta
from api.server import start_grpc_server, GRPC_OPTIONS, MAX_MESSAGE_SIZE
from internal.proxy.proxy import ProxyValidator
from internal.config.config import UPDATE_TIME_MINUTES

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Variables globales
current_servicer = None
server_start_time = None
restart_interval_hours = int(os.getenv('RESTART_INTERVAL_HOURS', '3'))
shutdown_requested = False

def signal_handler(signum, frame):
    """Manejo de señales para cierre limpio"""
    global shutdown_requested
    shutdown_requested = True
    logger.info("Señal de cierre recibida. Cerrando pools de drivers...")
    if current_servicer:
        current_servicer.close_pools()
    sys.exit(0)

def should_restart():
    """Verificar si es hora de reiniciar el servidor"""
    global server_start_time, restart_interval_hours
    
    if server_start_time is None:
        return False
    
    elapsed_time = datetime.now() - server_start_time
    restart_threshold = timedelta(hours=restart_interval_hours)
    
    return elapsed_time >= restart_threshold

def restart_server():
    """Reiniciar el servidor de forma controlada"""
    global shutdown_requested, current_servicer
    
    logger.info(f"Iniciando reinicio programado después de {restart_interval_hours} horas")
    
    # Cerrar pools y recursos
    if current_servicer:
        logger.info("Cerrando pools de drivers antes del reinicio...")
        current_servicer.close_pools()
    
    # Marcar que se solicitó el cierre
    shutdown_requested = True
    
    # Esperar un momento para que las conexiones se cierren
    time.sleep(5)
    
    logger.info("Reinicio programado completado. El proceso se cerrará y Docker lo reiniciará automáticamente.")
    
    # Salir del proceso - Docker restart: always lo reiniciará
    os._exit(0)

def auto_restart_monitor():
    """Monitor que controla el reinicio automático"""
    global shutdown_requested
    
    logger.info(f"Monitor de auto-reinicio iniciado. Reinicio cada {restart_interval_hours} horas.")
    
    while not shutdown_requested:
        try:
            # Verificar cada minuto si es hora de reiniciar
            time.sleep(60)
            
            if should_restart():
                logger.info("Tiempo de reinicio alcanzado. Iniciando proceso de reinicio...")
                restart_server()
                break
                
        except Exception as e:
            logger.error(f"Error en monitor de auto-reinicio: {e}")
            time.sleep(60)

def reload_proxies_background():
    """Función para recargar proxies en segundo plano"""
    global shutdown_requested
    proxy_validator = ProxyValidator(max_drivers=5)  # Menos drivers para background
    
    while not shutdown_requested:
        try:
            time.sleep(UPDATE_TIME_MINUTES * 60)
            
            if shutdown_requested:
                break
                
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
            
            # Verificar memoria y recursos
            if hasattr(proxy_validator, 'driver_pool'):
                active_drivers = proxy_validator.driver_pool.get_stats().get('active_drivers', 0)
                if active_drivers > 10:
                    logger.warning(f"Alto número de drivers activos: {active_drivers}")
            
        except Exception as e:
            logger.error(f"Error recargando proxies: {e}")
        finally:
            # Cerrar pool de validación para liberar recursos
            if not shutdown_requested:
                try:
                    proxy_validator.close_driver_pool()
                except:
                    pass

def start_grpc_server_wrapper():
    """Wrapper para el servidor gRPC que permite acceso al servicer con límites aumentados"""
    global current_servicer, shutdown_requested
    
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
    logger.info(f"Auto-reinicio configurado cada {restart_interval_hours} horas")
    
    try:
        while not shutdown_requested:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Interrupción de teclado recibida")
    finally:
        logger.info("Cerrando servidor gRPC...")
        current_servicer.close_pools()
        server.stop(0)

def log_system_info():
    """Registrar información del sistema y configuración"""
    logger.info("=== INFORMACIÓN DEL SISTEMA ===")
    logger.info(f"Hora de inicio: {datetime.now()}")
    logger.info(f"Intervalo de reinicio: {restart_interval_hours} horas")
    logger.info(f"Próximo reinicio programado: {datetime.now() + timedelta(hours=restart_interval_hours)}")
    logger.info(f"Límite de mensaje gRPC: {MAX_MESSAGE_SIZE/1024/1024:.0f}MB")
    logger.info(f"Actualización de proxies cada: {UPDATE_TIME_MINUTES} minutos")
    
    # Variables de entorno relevantes
    env_vars = ['DISPLAY', 'RESTART_INTERVAL_HOURS', 'PROXY_SERVER_HOST', 'PROXY_SERVER_PORT']
    for var in env_vars:
        value = os.getenv(var, 'No definida')
        logger.info(f"ENV {var}: {value}")
    
    logger.info("=== FIN INFORMACIÓN DEL SISTEMA ===")

def main():
    """Función principal con auto-reinicio"""
    global server_start_time, shutdown_requested
    
    # Registrar hora de inicio
    server_start_time = datetime.now()
    
    logger.info("Iniciando Proxy Server Python con Pool de Drivers y Auto-Reinicio")
    log_system_info()
    
    # Configurar manejo de señales
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Iniciar el monitor de auto-reinicio en un hilo separado
        restart_monitor_thread = threading.Thread(target=auto_restart_monitor, daemon=True)
        restart_monitor_thread.start()
        
        # Iniciar el servidor gRPC en un hilo separado
        grpc_thread = threading.Thread(target=start_grpc_server_wrapper, daemon=True)
        grpc_thread.start()
        
        # Iniciar la recarga de proxies en segundo plano
        reload_thread = threading.Thread(target=reload_proxies_background, daemon=True)
        reload_thread.start()
        
        # Mantener la aplicación en ejecución
        logger.info("Todos los servicios iniciados. Manteniendo aplicación en ejecución...")
        
        while not shutdown_requested:
            time.sleep(1)
            
            # Verificar si los hilos críticos están vivos
            if not grpc_thread.is_alive() and not shutdown_requested:
                logger.error("Hilo del servidor gRPC ha terminado inesperadamente")
                break
                
    except KeyboardInterrupt:
        logger.info("Interrupción de teclado recibida")
    except Exception as e:
        logger.error(f"Error crítico en main: {e}")
    finally:
        shutdown_requested = True
        logger.info("Cerrando servidor...")
        if current_servicer:
            current_servicer.close_pools()

if __name__ == "__main__":
    main()