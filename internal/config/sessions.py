"""
Configuración de sesiones para diferentes sitios web
"""
from dataclasses import dataclass
from typing import Dict
from .config import DEFAULT_SESSION_TIMEOUT

@dataclass
class ProxySession:
    name: str
    url: str
    headers: Dict[str, str]
    timeout: int = DEFAULT_SESSION_TIMEOUT

# Sesiones configuradas
PROXY_SESSIONS = {
    "CoinMarketCap": ProxySession(
        name="CoinMarketCap",
        url="https://coinmarketcap.com/es/",
        headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        },
        timeout=DEFAULT_SESSION_TIMEOUT,
    ),
}

def get_headers_from_session(session_name: str) -> Dict[str, str]:
    """Obtener headers de una sesión específica"""
    session = PROXY_SESSIONS.get(session_name)
    return session.headers if session else {}