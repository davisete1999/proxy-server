"""
Validación y gestión de proxies usando Selenium
"""
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

from ..config.config import DEFAULT_CHUNK_SIZE, SELENIUM_TIMEOUT
from ..config.sessions import PROXY_SESSIONS
from ..scraper.scraper import scrape_proxies

logger = logging.getLogger(__name__)

class ProxyValidator:
    def __init__(self, chunk_size: int = DEFAULT_CHUNK_SIZE):
        self.chunk_size = chunk_size
        self.valid_proxies: Dict[str, List[str]] = {}
        self._lock = threading.RLock()
    
    def _get_chrome_options(self, proxy_addr: str) -> Options:
        """Configurar opciones de Chrome para validación de proxies"""
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-logging')
        options.add_argument('--disable-extensions')
        options.add_argument('--window-size=1920,1080')
        options.add_argument(f'--proxy-server=http://{proxy_addr}')
        
        # Configuraciones adicionales para mayor estabilidad
        options.add_argument('--no-first-run')
        options.add_argument('--disable-default-apps')
        options.add_argument('--disable-popup-blocking')
        
        return options
    
    def _create_driver(self, proxy_addr: str) -> webdriver.Chrome:
        """Crear driver de Chrome configurado con proxy"""
        options = self._get_chrome_options(proxy_addr)
        
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            driver.set_page_load_timeout(SELENIUM_TIMEOUT)
            return driver
        except Exception as e:
            logger.debug(f"Error creando driver para proxy {proxy_addr}: {e}")
            raise
    
    def _test_proxy_with_session(self, proxy_addr: str, session_name: str, session_config) -> bool:
        """Probar un proxy específico con una sesión específica usando Selenium"""
        driver = None
        try:
            driver = self._create_driver(proxy_addr)
            
            # Navegar a la URL de prueba
            driver.get(session_config.url)
            
            # Esperar a que la página cargue
            WebDriverWait(driver, SELENIUM_TIMEOUT).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Verificar que el contenido es válido
            page_source = driver.page_source
            if len(page_source) > 100 and "error" not in page_source.lower():
                logger.debug(f"Proxy {proxy_addr} válido para {session_name}")
                return True
            else:
                logger.debug(f"Proxy {proxy_addr} contenido inválido para {session_name}")
                return False
                
        except TimeoutException:
            logger.debug(f"Timeout con proxy {proxy_addr} para {session_name}")
            return False
        except WebDriverException as e:
            logger.debug(f"WebDriver error con proxy {proxy_addr} para {session_name}: {e}")
            return False
        except Exception as e:
            logger.debug(f"Error con proxy {proxy_addr} para {session_name}: {e}")
            return False
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
    
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
        """Obtener y validar proxies usando Selenium"""
        logger.info("Iniciando validación de proxies con Selenium...")
        
        # Limpiar proxies válidos anteriores
        with self._lock:
            self.valid_proxies.clear()
        
        # Obtener lista de proxies
        proxies = scrape_proxies()
        if not proxies:
            logger.warning("No se obtuvieron proxies para validar")
            return {}
        
        logger.info(f"Validando {len(proxies)} proxies...")
        
        # Dividir en chunks para procesamiento
        chunks = self._chunk_proxies(proxies)
        
        # Procesar chunks con ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=5) as executor:
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
            logger.info(f"Validación completada. Total de proxies válidos: {total_valid}")
            
            for session, proxy_list in self.valid_proxies.items():
                logger.info(f"Sesión {session}: {len(proxy_list)} proxies válidos")
            
            return self.valid_proxies.copy()
    
    def _process_chunk(self, chunk: List[str], chunk_idx: int, total_chunks: int) -> None:
        """Procesar un chunk de proxies"""
        logger.info(f"Procesando chunk {chunk_idx + 1}/{total_chunks} ({len(chunk)} proxies)")
        
        # Procesar proxies del chunk con ThreadPoolExecutor más pequeño
        with ThreadPoolExecutor(max_workers=3) as executor:
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