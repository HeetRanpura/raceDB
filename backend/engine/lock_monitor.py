from db.connection import get_connection

def get_live_lock_status():
    """
    Queries MySQL performance_schema and information_schema 
    to retrieve real lock and wait data.
    """
    try:
        conn = get_connection("READ COMMITTED")
        conn.autocommit = True
        cur = conn.cursor(dictionary=True)
        
        # In MySQL 8, performance_schema.data_lock_waits is used instead of innodb_lock_waits
        try:
            cur.execute("SELECT * FROM performance_schema.data_lock_waits LIMIT 50")
            lock_waits = cur.fetchall()
        except Exception:
            lock_waits = []
            
        cur.execute("SELECT * FROM information_schema.innodb_trx LIMIT 50")
        active_trx = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return {
            "active_transactions": active_trx,
            "lock_waits": lock_waits
        }
    except Exception as e:
        return {"error": str(e)}
