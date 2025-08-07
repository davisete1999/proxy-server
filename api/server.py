"""
Servidor gRPC para el proxy service
"""
import grpc
from concurrent import futures
import logging
import random
import requests
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

import proxy_pb2
import proxy_pb2_grpc
from internal.config.sessions import PROXY_SESSIONS
from internal.proxy.proxy import ProxyValidator
from internal.scraper.scraper import scrape_user_agents

logger = logging.getLogger(__name__)

class ProxyServicer(proxy_pb2_grpc.ProxyServiceServicer):
    def __init__(self):
        self.proxy_validator = ProxyValidator()
        self.valid_proxies = {}
        self.successful_proxies = {}
        self.user_agents = []
        self._initialize()
    
    def _initialize(self):
        """Inicializar el servidor con proxies y user agents"""
        logger.info("Inicializando servidor...")
        self.valid_proxies = self.proxy_validator.get_valid_proxies()
        self.user_agents = scrape_user_agents()
        logger.info(f"Servidor inicializado con {len(self.user_agents)} user agents")
    
    def _get_chrome_options(self, proxy_addr=None):
        """Configurar opciones de Chrome con proxy opcional"""
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        
        if proxy_addr:
            options.add_argument(f'--proxy-server=http://{proxy_addr}')
        
        return options
    
    def _create_driver(self, proxy_addr=None, timeout=10):
        """Crear driver de Selenium con configuración específica"""
        options = self._get_chrome_options(proxy_addr)
        
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            driver.set_page_load_timeout(timeout)
            return driver
        except Exception as e:
            logger.error(f"Error creando driver: {e}")
            return None
    
    def _fetch_with_selenium(self, url, session_name, proxy_addr=None, user_agent=None):
        """Obtener contenido usando Selenium"""
        session_config = PROXY_SESSIONS.get(session_name)
        if not session_config:
            raise ValueError(f"Sesión '{session_name}' no encontrada")
        
        timeout = session_config.timeout / 1000  # Convertir a segundos
        driver = None
        
        try:
            driver = self._create_driver(proxy_addr, timeout)
            if not driver:
                raise Exception("No se pudo crear el driver")
            
            # Configurar user agent si se proporciona
            if user_agent:
                driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                    "userAgent": user_agent
                })
            
            # Configurar headers adicionales
            if session_config.headers:
                for header, value in session_config.headers.items():
                    driver.execute_cdp_cmd('Network.setRequestInterception', {
                        'patterns': [{'urlPattern': '*'}]
                    })
            
            # Navegar a la URL
            driver.get(url)
            
            # Esperar a que la página cargue
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Obtener el contenido
            content = driver.page_source.encode('utf-8')
            
            if proxy_addr:
                logger.info(f"Selenium - Proxy: {proxy_addr}, URL: {url}, Content length: {len(content)}")
            else:
                logger.info(f"Selenium - Direct, URL: {url}, Content length: {len(content)}")
            
            return content
            
        except TimeoutException:
            raise Exception("Timeout esperando a que cargue la página")
        except WebDriverException as e:
            raise Exception(f"Error de WebDriver: {str(e)}")
        except Exception as e:
            raise Exception(f"Error en Selenium: {str(e)}")
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
    
    def _fetch_with_requests(self, url, session_name, proxy_addr=None, user_agent=None):
        """Obtener contenido usando requests como fallback"""
        session_config = PROXY_SESSIONS.get(session_name)
        if not session_config:
            raise ValueError(f"Sesión '{session_name}' no encontrada")
        
        headers = session_config.headers.copy()
        if user_agent:
            headers['User-Agent'] = user_agent
        
        proxies = None
        if proxy_addr:
            proxies = {
                'http': f'http://{proxy_addr}',
                'https': f'http://{proxy_addr}'
            }
        
        timeout = session_config.timeout / 1000
        
        response = requests.get(
            url,
            headers=headers,
            proxies=proxies,
            timeout=timeout,
            allow_redirects=True
        )
        
        response.raise_for_status()
        return response.content
    
    def FetchContent(self, request, context):
        """Implementación del método FetchContent"""
        try:
            if not request.session or request.session not in PROXY_SESSIONS:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details("Sesión inválida")
                return proxy_pb2.Response()
            
            # Seleccionar user agent aleatorio
            user_agent = None
            if self.user_agents:
                user_agent = random.choice(self.user_agents)
            
            if request.proxy and request.session in self.valid_proxies:
                # Intentar con proxies válidos
                proxies = self.valid_proxies[request.session]
                if proxies:
                    proxy_addr = random.choice(proxies)
                    try:
                        content = self._fetch_with_selenium(
                            request.url, 
                            request.session, 
                            proxy_addr, 
                            user_agent
                        )
                        return proxy_pb2.Response(content=content)
                    except Exception as e:
                        logger.warning(f"Error con proxy {proxy_addr}: {e}")
                        # Fallback a requests
                        try:
                            content = self._fetch_with_requests(
                                request.url, 
                                request.session, 
                                proxy_addr, 
                                user_agent
                            )
                            return proxy_pb2.Response(content=content)
                        except:
                            pass
            
            # Fallback: sin proxy
            try:
                content = self._fetch_with_selenium(
                    request.url, 
                    request.session, 
                    None, 
                    user_agent
                )
                return proxy_pb2.Response(content=content)
            except Exception as e:
                logger.warning(f"Error con Selenium directo: {e}")
                # Fallback final a requests
                content = self._fetch_with_requests(
                    request.url, 
                    request.session, 
                    None, 
                    user_agent
                )
                return proxy_pb2.Response(content=content)
                
        except Exception as e:
            logger.error(f"Error en FetchContent: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return proxy_pb2.Response()
    
    def GetRandomProxy(self, request, context):
        """Obtener un proxy aleatorio de una sesión específica"""
        try:
            if not request.session:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details("La sesión no puede estar vacía")
                return proxy_pb2.ProxyResponse()
            
            if request.session not in PROXY_SESSIONS:
                return proxy_pb2.ProxyResponse(
                    proxy="",
                    success=False,
                    message=f"Sesión '{request.session}' no encontrada en configuración"
                )
            
            proxies = self.valid_proxies.get(request.session, [])
            if not proxies:
                return proxy_pb2.ProxyResponse(
                    proxy="",
                    success=False,
                    message=f"No hay proxies válidos disponibles para la sesión '{request.session}'"
                )
            
            selected_proxy = random.choice(proxies)
            logger.info(f"Proxy aleatorio seleccionado para sesión '{request.session}': {selected_proxy}")
            
            return proxy_pb2.ProxyResponse(
                proxy=selected_proxy,
                success=True,
                message=f"Proxy seleccionado exitosamente para la sesión '{request.session}'"
            )
            
        except Exception as e:
            logger.error(f"Error en GetRandomProxy: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return proxy_pb2.ProxyResponse()
    
    def GetProxyStats(self, request, context):
        """Obtener estadísticas de proxies por sesión"""
        try:
            stats = {}
            total_proxies = 0
            
            for session, proxies in self.valid_proxies.items():
                count = len(proxies)
                stats[session] = count
                total_proxies += count
            
            return proxy_pb2.StatsResponse(
                proxy_count_by_session=stats,
                total_valid_proxies=total_proxies
            )
            
        except Exception as e:
            logger.error(f"Error en GetProxyStats: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return proxy_pb2.StatsResponse()

def start_grpc_server():
    """Iniciar el servidor gRPC"""
    logger.info("Iniciando servidor gRPC en puerto 5000")
    
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    proxy_pb2_grpc.add_ProxyServiceServicer_to_server(ProxyServicer(), server)
    
    listen_addr = '[::]:5000'
    server.add_insecure_port(listen_addr)
    
    server.start()
    logger.info(f"Servidor gRPC iniciado en {listen_addr}")
    
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Cerrando servidor gRPC...")
        server.stop(0)