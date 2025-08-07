"""
Validación y gestión de proxies usando Selenium con pool de drivers
"""
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from ..config.config import DEFAULT_CHUNK_SIZE, SELENIUM_TIMEOUT
from ..config.sessions import PROXY_SESSIONS
from ..scraper.scraper import scrape_proxies
from .driver_pool import DriverPool

logger = logging.getLogger(__name__)

class ProxyValidator:
    def __init__(self, chunk_size: int = DEFAULT_CHUNK_SIZE, max_drivers: int = 20):
        self.chunk_size = chunk_size
        self.max_drivers = max_drivers
        self.valid_proxies: Dict[str, List[str]] = {}
        self._lock = threading.RLock()
        self.driver_pool = DriverPool(max_drivers=max_drivers)
    
    def _test_proxy_with_session(self, proxy_addr: str, session_name: str, session_config) -> bool:
        """Probar un proxy específico con una sesión específica usando el pool de drivers"""
        driver_instance = None
        had_error = False
        
        try:
            # Obtener driver del pool
            driver_instance = self.driver_pool.get_driver(proxy_addr)
            if not driver_instance:
                return False
            
            driver = driver_instance.driver
            
            # Navegar a la URL de prueba
            driver.get(session_config.url)
            
            # Esperar a que la página cargue
            WebDriverWait(driver, SELENIUM_TIMEOUT).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Verificar que el contenido es válido
            page_source = driver.page_source
            if len(page_source) > 100 and "error" not in page_source.lower():
                logger.info(f"✓ Proxy válido: {proxy_addr} para {session_name}")
                return True
            else:
                return False
                
        except TimeoutException:
            had_error = True
            return False
        except WebDriverException as e:
            had_error = True
            return False
        except Exception as e:
            had_error = True
            return False
        finally:
            if driver_instance:
                # Devolver driver al pool en lugar de cerrarlo
                self.driver_pool.return_driver(driver_instance, had_error)
    
    def _test_proxy_all_sessions(self, proxy_addr: str) -> None:
        """Probar un proxy con todas las sesiones configuradas"""
        for session_name, session_config in PROXY_SESSIONS.items():
            if self._test_proxy_with_session(proxy_addr, session_name, session_config):
                with self._lock:
                    if session_name not in self.valid_proxies:
                        self.valid_proxies[session_name] = []
                    self.valid_proxies[session_name].append(proxy_addr)
    
    def _chunk_proxies(self, proxies: List[str]) -> List[List[str]]:
        """Dividir lista de proxies en chunks más manejables"""
        chunks = []
        for i in range(0, len(proxies), self.chunk_size):
            end = i + self.chunk_size
            if end > len(proxies):
                end = len(proxies)
            chunks.append(proxies[i:end])
        return chunks
    
    def get_valid_proxies(self) -> Dict[str, List[str]]:
        """Obtener y validar proxies usando el pool de drivers"""
        logger.info("Iniciando validación de proxies con pool de drivers...")
        
        # Limpiar proxies válidos anteriores
        with self._lock:
            self.valid_proxies.clear()
        
        # Obtener lista de proxies
        proxies = scrape_proxies()
        if not proxies:
            logger.warning("No se obtuvieron proxies para validar")
            return {}
        
        logger.info(f"Validando {len(proxies)} proxies con pool de {self.max_drivers} drivers...")
        
        # Dividir en chunks para procesamiento
        chunks = self._chunk_proxies(proxies)
        
        # Procesar chunks con ThreadPoolExecutor
        # Reducir workers para no sobrecargar el pool de drivers
        max_workers = min(5, self.max_drivers)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            chunk_futures = []
            
            for chunk_idx, chunk in enumerate(chunks):
                future = executor.submit(self._process_chunk, chunk, chunk_idx, len(chunks))
                chunk_futures.append(future)
            
            # Esperar a que terminen todos los chunks
            for future in as_completed(chunk_futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error procesando chunk: {e}")
        
        # Mostrar estadísticas finales
        with self._lock:
            total_valid = sum(len(proxies) for proxies in self.valid_proxies.values())
            pool_stats = self.driver_pool.get_stats()
            
            logger.info(f"Validación completada. Total de proxies válidos: {total_valid}")
            logger.info(f"Estadísticas del pool: {pool_stats}")
            
            for session, proxy_list in self.valid_proxies.items():
                logger.info(f"Sesión {session}: {len(proxy_list)} proxies válidos")
            
            return self.valid_proxies.copy()
    
    def _process_chunk(self, chunk: List[str], chunk_idx: int, total_chunks: int) -> None:
        """Procesar un chunk de proxies"""
        logger.info(f"Procesando chunk {chunk_idx + 1}/{total_chunks} ({len(chunk)} proxies)")
        
        # Procesar proxies del chunk con ThreadPoolExecutor más pequeño
        # Limitar concurrencia para no agotar el pool de drivers
        max_workers = min(3, len(chunk))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            proxy_futures = []
            
            for proxy in chunk:
                future = executor.submit(self._test_proxy_all_sessions, proxy)
                proxy_futures.append(future)
            
            # Esperar a que terminen todos los proxies del chunk
            for future in as_completed(proxy_futures):
                try:
                    future.result()
                except Exception as e:
                    logger.debug(f"Error validando proxy: {e}")
        
        logger.info(f"Chunk {chunk_idx + 1}/{total_chunks} completado")
    
    def get_driver_pool_stats(self) -> Dict:
        """Obtener estadísticas del pool de drivers"""
        return self.driver_pool.get_stats()
    
    def close_driver_pool(self):
        """Cerrar el pool de drivers"""
        logger.info("Cerrando pool de drivers...")
        self.driver_pool.close_all()