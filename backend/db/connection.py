import mysql.connector
from mysql.connector import Error
from config import DB_CONFIG

def get_connection(isolation_level: str = "REPEATABLE READ"):
    """
    Dispense a fresh MySQL connection using settings from the environment.
    Immediately sets the session transaction isolation level.
    """
    conn_kwargs = dict(DB_CONFIG)

    conn = mysql.connector.connect(**conn_kwargs)
    
    # Set requested isolation level for this session
    cursor = conn.cursor()
    cursor.execute(f"SET SESSION TRANSACTION ISOLATION LEVEL {isolation_level}")
    cursor.close()

    return conn

def close_resources(conn, cursor=None):
    """Safely close cursor and connection."""
    if cursor:
        try:
            cursor.close()
        except Exception:
            pass
    if conn and conn.is_connected():
        try:
            conn.close()
        except Exception:
            pass
