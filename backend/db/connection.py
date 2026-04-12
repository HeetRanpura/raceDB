import mysql.connector
from mysql.connector import pooling
from config import DB_CONFIG

# Fix #1: Whitelist valid isolation levels to prevent SQL injection
VALID_ISOLATION_LEVELS = {
    "READ UNCOMMITTED",
    "READ COMMITTED",
    "REPEATABLE READ",
    "SERIALIZABLE",
}

# Fix #11: Connection pool to prevent exhaustion under high concurrency.
# MySQL default max_connections=151; pool of 20 keeps us well within limits.
_pool = None

def _get_pool():
    """Lazy-initialize a connection pool using DB_CONFIG."""
    global _pool
    if _pool is None:
        pool_config = dict(DB_CONFIG)
        pool_config.pop("autocommit", None)  # pool doesn't accept autocommit
        _pool = pooling.MySQLConnectionPool(
            pool_name="racedb_pool",
            pool_size=20,
            pool_reset_session=True,
            **pool_config,
        )
    return _pool


def get_connection(isolation_level: str = "REPEATABLE READ"):
    """
    Dispense a MySQL connection from the pool.
    Validates and sets the session transaction isolation level.
    """
    level = isolation_level.upper().strip()
    if level not in VALID_ISOLATION_LEVELS:
        raise ValueError(
            f"Invalid isolation level: '{isolation_level}'. "
            f"Must be one of: {', '.join(sorted(VALID_ISOLATION_LEVELS))}"
        )

    try:
        conn = _get_pool().get_connection()
    except pooling.PoolError:
        # Pool exhausted — fall back to a direct connection
        conn_kwargs = dict(DB_CONFIG)
        conn = mysql.connector.connect(**conn_kwargs)

    # Set requested isolation level for this session
    cursor = conn.cursor()
    cursor.execute(f"SET SESSION TRANSACTION ISOLATION LEVEL {level}")
    cursor.close()

    return conn


def close_resources(conn, cursor=None):
    """Safely close cursor and connection (returns conn to pool)."""
    if cursor:
        try:
            cursor.close()
        except Exception:
            pass
    if conn:
        try:
            conn.close()
        except Exception:
            pass
