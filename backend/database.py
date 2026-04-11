"""
RaceDB — MySQL connection factory
"""
import mysql.connector
from config import DB_CONFIG


def get_connection(isolation_level: str = "REPEATABLE READ"):
    """Open a fresh MySQL connection and set the isolation level."""
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute(f"SET SESSION TRANSACTION ISOLATION LEVEL {isolation_level}")
    cursor.close()
    return conn
