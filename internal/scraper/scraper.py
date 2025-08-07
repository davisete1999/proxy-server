"""
Scraping de proxies y user agents
"""
import logging
import requests
from typing import List
import time

logger = logging.getLogger(__name__)

def scrape_proxies() -> List[str]:
    """Scraping de proxies desde fuentes públicas"""
    proxy_urls = [
        "https://raw.githubusercontent.com/officialputuid/KangProxy/refs/heads/KangProxy/https/https.txt",
        "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/refs/heads/master/https.txt",
        # Comentadas las fuentes menos confiables
        # "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",
        # "https://raw.githubusercontent.com/proxifly/free-proxy-list/refs/heads/main/proxies/all/data.txt",
    ]
    
    all_proxies = []
    
    for url in proxy_urls:
        try:
            logger.info(f"Obteniendo proxies de {url}")
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            lines = response.text.strip().split('\n')
            valid_proxies = []
            
            for line in lines:
                line = line.strip()
                if line and ':' in line:
                    # Limpiar formato de proxy si tiene múltiples ':'
                    parts = line.split(':')
                    if len(parts) >= 2:
                        proxy = f"{parts[0]}:{parts[1]}"
                        valid_proxies.append(proxy)
            
            all_proxies.extend(valid_proxies)
            logger.info(f"Obtenidos {len(valid_proxies)} proxies de {url}")
            
        except requests.RequestException as e:
            logger.warning(f"Error obteniendo proxies de {url}: {e}")
        except Exception as e:
            logger.error(f"Error inesperado con {url}: {e}")
    
    # Eliminar duplicados manteniendo orden
    unique_proxies = list(dict.fromkeys(all_proxies))
    logger.info(f"Total de proxies únicos obtenidos: {len(unique_proxies)}")
    
    return unique_proxies

def scrape_user_agents() -> List[str]:
    """Scraping de user agents"""
    user_agent_urls = [
        "https://gist.githubusercontent.com/pzb/b4b6f57144aea7827ae4/raw/cf847b76a142955b1410c8bcef3aabe221a63db1/user-agents.txt",
    ]
    
    all_user_agents = []
    max_retries = 3
    
    for url in user_agent_urls:
        for attempt in range(max_retries):
            try:
                logger.info(f"Obteniendo user agents de {url} (intento {attempt + 1})")
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                
                lines = response.text.strip().split('\n')
                valid_user_agents = []
                
                for line in lines:
                    line = line.strip()
                    # Filtrar user agents móviles y problemáticos
                    if (line and 
                        not any(mobile in line for mobile in ['Android', 'iPhone', 'iPad', 'Mobile']) and
                        'Mozilla/' in line):
                        valid_user_agents.append(line)
                
                all_user_agents.extend(valid_user_agents)
                logger.info(f"Obtenidos {len(valid_user_agents)} user agents de {url}")
                break  # Éxito, salir del bucle de reintentos
                
            except requests.RequestException as e:
                logger.warning(f"Error obteniendo user agents de {url} (intento {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)  # Esperar antes del siguiente intento
            except Exception as e:
                logger.error(f"Error inesperado con {url}: {e}")
                break
    
    # Si no se obtuvieron user agents, usar valores por defecto
    if not all_user_agents:
        logger.warning("No se pudieron obtener user agents, usando valores por defecto")
        from ..config.config import DEFAULT_USER_AGENTS
        all_user_agents = DEFAULT_USER_AGENTS
    
    # Eliminar duplicados
    unique_user_agents = list(dict.fromkeys(all_user_agents))
    logger.info(f"Total de user agents únicos: {len(unique_user_agents)}")
    
    return unique_user_agents