"""
RaceDB — database configuration + connection helpers
"""
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     int(os.getenv("DB_PORT", "3306")),
    "user":     os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "racedb"),
    "autocommit": False,
    "connection_timeout": 10,
}

# If a Unix socket path is supplied, use it instead of TCP
_SOCKET = os.getenv("DB_UNIX_SOCKET", "")
if _SOCKET:
    DB_CONFIG["unix_socket"] = _SOCKET
    # Remove host/port when using socket (mysql-connector ignores them anyway)
