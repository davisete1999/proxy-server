"""
Pool de drivers de Selenium para reutilización con rotación de proxies
"""
import logging
import threading
import time
from queue import Queue, Empty
from typing import Optional, Dict
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)

# Cache global del path de ChromeDriver para evitar descargas repetidas
_CHROME_DRIVER_PATH = None
_CHROME_DRIVER_LOCK = threading.Lock()

def get_chrome_driver_path():
    """Obtener path del ChromeDriver, descargándolo solo una vez"""
    global _CHROME_DRIVER_PATH
    if _CHROME_DRIVER_PATH is None:
        with _CHROME_DRIVER_LOCK:
            if _CHROME_DRIVER_PATH is None:
                logger.info("Inicializando ChromeDriver por primera vez...")
                _CHROME_DRIVER_PATH = ChromeDriverManager().install()
                logger.info(f"ChromeDriver listo en: {_CHROME_DRIVER_PATH}")
    return _CHROME_DRIVER_PATH

class DriverInstance:
    """Representa una instancia de driver con su proxy asociado"""
    def __init__(self, driver: webdriver.Chrome, proxy_addr: Optional[str] = None):
        self.driver = driver
        self.current_proxy = proxy_addr
        self.last_used = time.time()
        self.in_use = False
        self.error_count = 0

class DriverPool:
    """Pool de drivers de Selenium para reutilización"""
    
    def __init__(self, max_drivers: int = 10, idle_timeout: int = 300):
        self.max_drivers = max_drivers
        self.idle_timeout = idle_timeout  # segundos
        self.available_drivers = Queue()
        self.active_drivers: Dict[str, DriverInstance] = {}
        self._lock = threading.RLock()
        self._cleanup_thread = None
        self._start_cleanup_thread()
    
    def _get_chrome_options(self, proxy_addr: Optional[str] = None) -> Options:
        """Configurar opciones de Chrome"""
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-logging')
        options.add_argument('--disable-extensions')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--no-first-run')
        options.add_argument('--disable-default-apps')
        options.add_argument('--disable-popup-blocking')
        
        if proxy_addr:
            options.add_argument(f'--proxy-server=http://{proxy_addr}')
        
        return options
    
    def _create_driver(self, proxy_addr: Optional[str] = None) -> Optional[webdriver.Chrome]:
        """Crear un nuevo driver"""
        try:
            options = self._get_chrome_options(proxy_addr)
            service = Service(get_chrome_driver_path())
            driver = webdriver.Chrome(service=service, options=options)
            driver.set_page_load_timeout(10)
            
            proxy_info = f"con proxy {proxy_addr}" if proxy_addr else "sin proxy"
            logger.info(f"Driver creado exitosamente {proxy_info}")
            return driver
        except Exception as e:
            logger.error(f"Error creando driver: {e}")
            return None
    
    def _can_reuse_driver(self, driver_instance: DriverInstance, target_proxy: Optional[str]) -> bool:
        """Verificar si un driver puede ser reutilizado para el proxy objetivo"""
        # Si ambos son None (sin proxy) o son el mismo proxy, se puede reutilizar
        return driver_instance.current_proxy == target_proxy and driver_instance.error_count < 3
    
    def _reconfigure_driver_proxy(self, driver_instance: DriverInstance, new_proxy: Optional[str]) -> bool:
        """
        Intentar reconfigurar el proxy de un driver existente.
        Nota: Chrome no permite cambiar proxy en runtime, necesitamos recrear.
        """
        try:
            # Cerrar el driver actual
            driver_instance.driver.quit()
            
            # Crear uno nuevo con el nuevo proxy
            new_driver = self._create_driver(new_proxy)
            if new_driver:
                driver_instance.driver = new_driver
                driver_instance.current_proxy = new_proxy
                driver_instance.error_count = 0
                return True
            return False
        except Exception as e:
            logger.error(f"Error reconfigurando proxy del driver: {e}")
            return False
    
    def get_driver(self, proxy_addr: Optional[str] = None, timeout: int = 5) -> Optional[DriverInstance]:
        """Obtener un driver del pool"""
        with self._lock:
            # Primero buscar un driver disponible que ya tenga el proxy correcto
            temp_queue = Queue()
            best_match = None
            
            while not self.available_drivers.empty():
                try:
                    driver_instance = self.available_drivers.get_nowait()
                    
                    # Verificar si el driver sigue siendo válido
                    try:
                        # Test rápido para verificar que el driver funciona
                        driver_instance.driver.current_url
                        
                        if self._can_reuse_driver(driver_instance, proxy_addr):
                            best_match = driver_instance
                            break
                        else:
                            temp_queue.put(driver_instance)
                    except WebDriverException:
                        # Driver no válido, cerrarlo
                        try:
                            driver_instance.driver.quit()
                        except:
                            pass
                        
                except Empty:
                    break
            
            # Devolver los drivers que no se usaron al pool
            while not temp_queue.empty():
                self.available_drivers.put(temp_queue.get())
            
            if best_match:
                best_match.in_use = True
                best_match.last_used = time.time()
                driver_id = id(best_match)
                self.active_drivers[str(driver_id)] = best_match
                logger.debug(f"Reutilizando driver para proxy: {proxy_addr}")
                return best_match
            
            # Si no hay match exacto, intentar reconfigurar un driver disponible
            if not self.available_drivers.empty() and len(self.active_drivers) >= self.max_drivers:
                try:
                    driver_instance = self.available_drivers.get_nowait()
                    if self._reconfigure_driver_proxy(driver_instance, proxy_addr):
                        driver_instance.in_use = True
                        driver_instance.last_used = time.time()
                        driver_id = id(driver_instance)
                        self.active_drivers[str(driver_id)] = driver_instance
                        logger.debug(f"Reconfigurado driver para proxy: {proxy_addr}")
                        return driver_instance
                    else:
                        # Si falla la reconfiguración, cerrar el driver
                        try:
                            driver_instance.driver.quit()
                        except:
                            pass
                except Empty:
                    pass
            
            # Si no hay drivers disponibles y estamos bajo el límite, crear uno nuevo
            if len(self.active_drivers) < self.max_drivers:
                new_driver = self._create_driver(proxy_addr)
                if new_driver:
                    driver_instance = DriverInstance(new_driver, proxy_addr)
                    driver_instance.in_use = True
                    driver_instance.last_used = time.time()
                    driver_id = id(driver_instance)
                    self.active_drivers[str(driver_id)] = driver_instance
                    logger.debug(f"Creado nuevo driver para proxy: {proxy_addr}")
                    return driver_instance
            
            logger.warning(f"No se pudo obtener driver para proxy: {proxy_addr}")
            return None
    
    def return_driver(self, driver_instance: DriverInstance, had_error: bool = False):
        """Devolver un driver al pool"""
        with self._lock:
            driver_id = str(id(driver_instance))
            
            if driver_id in self.active_drivers:
                del self.active_drivers[driver_id]
            
            driver_instance.in_use = False
            driver_instance.last_used = time.time()
            
            if had_error:
                driver_instance.error_count += 1
            
            # Si el driver ha tenido muchos errores, cerrarlo
            if driver_instance.error_count >= 3:
                try:
                    driver_instance.driver.quit()
                    logger.debug("Driver cerrado por exceso de errores")
                except:
                    pass
                return
            
            # Verificar que el driver sigue funcionando
            try:
                driver_instance.driver.current_url
                self.available_drivers.put(driver_instance)
                logger.debug("Driver devuelto al pool")
            except WebDriverException:
                # Driver no válido, cerrarlo
                try:
                    driver_instance.driver.quit()
                    logger.debug("Driver cerrado por no estar válido")
                except:
                    pass
    
    def _start_cleanup_thread(self):
        """Iniciar hilo de limpieza para drivers inactivos"""
        def cleanup_inactive_drivers():
            while True:
                try:
                    time.sleep(60)  # Ejecutar cada minuto
                    self._cleanup_inactive_drivers()
                except Exception as e:
                    logger.error(f"Error en cleanup de drivers: {e}")
        
        self._cleanup_thread = threading.Thread(target=cleanup_inactive_drivers, daemon=True)
        self._cleanup_thread.start()
    
    def _cleanup_inactive_drivers(self):
        """Limpiar drivers que han estado inactivos por mucho tiempo"""
        current_time = time.time()
        drivers_to_close = []
        
        with self._lock:
            # Buscar drivers inactivos en la cola disponible
            temp_queue = Queue()
            
            while not self.available_drivers.empty():
                try:
                    driver_instance = self.available_drivers.get_nowait()
                    
                    if current_time - driver_instance.last_used > self.idle_timeout:
                        drivers_to_close.append(driver_instance)
                    else:
                        temp_queue.put(driver_instance)
                except Empty:
                    break
            
            # Devolver drivers activos al pool
            while not temp_queue.empty():
                self.available_drivers.put(temp_queue.get())
        
        # Cerrar drivers inactivos fuera del lock
        for driver_instance in drivers_to_close:
            try:
                driver_instance.driver.quit()
                logger.debug("Driver cerrado por inactividad")
            except:
                pass
    
    def close_all(self):
        """Cerrar todos los drivers del pool"""
        with self._lock:
            # Cerrar drivers activos
            for driver_instance in self.active_drivers.values():
                try:
                    driver_instance.driver.quit()
                except:
                    pass
            self.active_drivers.clear()
            
            # Cerrar drivers disponibles
            while not self.available_drivers.empty():
                try:
                    driver_instance = self.available_drivers.get_nowait()
                    driver_instance.driver.quit()
                except:
                    pass
        
        logger.info("Todos los drivers del pool han sido cerrados")
    
    def get_stats(self) -> Dict:
        """Obtener estadísticas del pool"""
        with self._lock:
            return {
                "active_drivers": len(self.active_drivers),
                "available_drivers": self.available_drivers.qsize(),
                "max_drivers": self.max_drivers
            }