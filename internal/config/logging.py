"""
Configuración de logging para el proxy server
"""
import logging

def setup_logging():
    """Configurar logging para reducir ruido del WebDriver Manager"""
    
    # Configuración principal
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Silenciar logs molestos del WebDriver Manager
    logging.getLogger('WDM').setLevel(logging.WARNING)
    logging.getLogger('selenium.webdriver.remote.remote_connection').setLevel(logging.WARNING)
    logging.getLogger('selenium.webdriver.common.selenium_manager').setLevel(logging.WARNING)
    logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)
    
    # Configurar nuestros loggers
    proxy_logger = logging.getLogger('internal.proxy')
    proxy_logger.setLevel(logging.INFO)
    
    scraper_logger = logging.getLogger('internal.scraper')
    scraper_logger.setLevel(logging.INFO)
    
    api_logger = logging.getLogger('api')
    api_logger.setLevel(logging.INFO)
    
    return logging.getLogger(__name__)