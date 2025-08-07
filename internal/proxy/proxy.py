"""
Validación optimizada de proxies con pool de drivers mejorado
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

from ..config.config import (
    DEFAULT_CHUNK_SIZE, VALIDATION_TIMEOUT, MAX_VALIDATION_DRIVERS,
    MAX_CONCURRENT_TESTS, MAX_CHUNK_WORKERS
)
from ..config.sessions import PROXY_SESSIONS
from ..scraper.scraper import scrape_proxies
from .driver_pool import DriverPool

logger = logging.getLogger(__name__)

class ProxyValidator:
    def __init__(self, chunk_size: int = DEFAULT_CHUNK_SIZE, max_drivers: int = MAX_VALIDATION_DRIVERS):
        self.chunk_size = chunk_size
        self.max_drivers = max_drivers
        self.valid_proxies: Dict[str, List[str]] = {}
        self._lock = threading.RLock()
        self.driver_pool = DriverPool(max_drivers=max_drivers, idle_timeout=60)  # Timeout reducido
        
        # Cache de proxies fallidos para evitar re-testing
        self.failed_proxies = set()
        self.last_validation_time = 0
    
    def _quick_proxy_test(self, proxy_addr: str, session_name: str, session_config) -> bool:
        """Test rápido de proxy con timeout agresivo"""
        driver_instance = None
        had_error = False
        
        try:
            # Obtener driver del pool con timeout
            driver_instance = self.driver_pool.get_driver(proxy_addr, timeout=2)
            if not driver_instance:
                return False
            
            driver = driver_instance.driver
            
            # Test ultra-rápido: solo verificar que el proxy responde
            start_time = time.time()
            driver.set_page_load_timeout(VALIDATION_TIMEOUT / 1000)
            
            # Usar una URL simple para test rápido
            test_url = "http://httpbin.org/ip" if session_config.url.startswith('https') else session_config.url
            driver.get(test_url)
            
            # Verificación mínima: solo que cargue algo
            try:
                WebDriverWait(driver, 2).until(
                    lambda d: len(d.page_source) > 50
                )
                
                elapsed = time.time() - start_time
                if elapsed < 5:  # Solo aceptar proxies rápidos
                    logger.debug(f"✓ Proxy rápido: {proxy_addr} ({elapsed:.2f}s)")
                    return True
                
            except TimeoutException:
                pass
                
            return False
                
        except Exception:
            had_error = True
            return False
        finally:
            if driver_instance:
                self.driver_pool.return_driver(driver_instance, had_error)
    
    def _test_proxy_batch(self, proxy_batch: List[str], session_name: str) -> List[str]:
        """Probar un lote de proxies en paralelo"""
        session_config = PROXY_SESSIONS[session_name]
        valid_batch = []
        
        # Filtrar proxies que ya fallaron recientemente
        fresh_proxies = [p for p in proxy_batch if p not in self.failed_proxies]
        
        if not fresh_proxies:
            return valid_batch
        
        # Test en paralelo con ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_TESTS) as executor:
            # Crear futures para cada proxy
            future_to_proxy = {
                executor.submit(self._quick_proxy_test, proxy, session_name, session_config): proxy 
                for proxy in fresh_proxies
            }
            
            # Recoger resultados conforme van completando
            for future in as_completed(future_to_proxy, timeout=30):
                proxy = future_to_proxy[future]
                try:
                    if future.result():
                        valid_batch.append(proxy)
                        logger.info(f"✓ Proxy validado: {proxy}")
                    else:
                        self.failed_proxies.add(proxy)
                except Exception as e:
                    logger.debug(f"Error testing {proxy}: {e}")
                    self.failed_proxies.add(proxy)
        
        return valid_batch
    
    def get_valid_proxies(self) -> Dict[str, List[str]]:
        """Validación optimizada de proxies"""
        logger.info("Iniciando validación optimizada de proxies...")
        
        # Limpiar cache de fallidos si es muy viejo
        current_time = time.time()
        if current_time - self.last_validation_time > 1800:  # 30 minutos
            self.failed_proxies.clear()
            logger.info("Cache de proxies fallidos limpiado")
        
        self.last_validation_time = current_time
        
        with self._lock:
            self.valid_proxies.clear()
        
        # Obtener proxies
        proxies = scrape_proxies()
        if not proxies:
            logger.warning("No se obtuvieron proxies")
            return {}
        
        logger.info(f"Validando {len(proxies)} proxies con {self.max_drivers} drivers...")
        
        # Procesar por sesión en paralelo
        session_futures = {}
        with ThreadPoolExecutor(max_workers=len(PROXY_SESSIONS)) as session_executor:
            for session_name in PROXY_SESSIONS.keys():
                future = session_executor.submit(self._validate_session, proxies, session_name)
                session_futures[session_name] = future
            
            # Recoger resultados
            for session_name, future in session_futures.items():
                try:
                    valid_proxies = future.result(timeout=120)  # 2 minutos max por sesión
                    if valid_proxies:
                        with self._lock:
                            self.valid_proxies[session_name] = valid_proxies
                except Exception as e:
                    logger.error(f"Error validando sesión {session_name}: {e}")
        
        # Estadísticas
        total_valid = sum(len(proxies) for proxies in self.valid_proxies.values())
        logger.info(f"Validación completada en {time.time() - current_time:.2f}s")
        logger.info(f"Proxies válidos: {total_valid}/{len(proxies)} ({total_valid/len(proxies)*100:.1f}%)")
        
        return self.valid_proxies.copy()
    
    def _validate_session(self, proxies: List[str], session_name: str) -> List[str]:
        """Validar proxies para una sesión específica, deteniendo en 20 válidos"""
        logger.info(f"Validando {len(proxies)} proxies para sesión {session_name}")

        # Dividir en lotes pequeños
        batch_size = 5  # Lotes pequeños para mejor paralelización
        batches = [proxies[i:i+batch_size] for i in range(0, len(proxies), batch_size)]
        all_valid: List[str] = []

        # Procesar lote a lote y detener al llegar a 20
        for i, batch in enumerate(batches):
            valid_batch = self._test_proxy_batch(batch, session_name)
            all_valid.extend(valid_batch)
            logger.debug(
                f"Lote {i+1}/{len(batches)} completado: "
                f"{len(valid_batch)} válidos, totales {len(all_valid)}"
            )

            if len(all_valid) >= 20:
                logger.info(
                    f"Alcanzados 20 proxies válidos para sesión {session_name}, deteniendo validación"
                )
                break

        # Devolver sólo los primeros 20
        return all_valid[:20]
    
    def close_driver_pool(self):
        """Cerrar pool optimizado"""
        logger.info("Cerrando pool de drivers optimizado...")
        self.driver_pool.close_all()