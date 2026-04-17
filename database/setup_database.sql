import os
import psycopg2
from psycopg2 import pool

connection_pool = None


def init_db():
    global connection_pool
    try:
        db_url = os.getenv("DATABASE_URL")

        if not db_url:
            print("❌ DATABASE_URL not set")
            return

        connection_pool = psycopg2.pool.SimpleConnectionPool(1, 10, db_url)
        print("✅ DB connected")

    except Exception as e:
        print("❌ DB error:", e)


def get_conn():
    return connection_pool.getconn() if connection_pool else None


def release_conn(conn):
    if connection_pool and conn:
        connection_pool.putconn(conn)


# ✅ CREATE TABLE inside function
def create_tables():
    conn = get_conn()

    if not conn:
        print("❌ No DB connection")
        return

    try:
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            full_name VARCHAR(255) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255),
            google_id VARCHAR(255) UNIQUE,
            pfp_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        );
        """)

        cur.execute("CREATE INDEX IF NOT EXISTS idx_email ON users(email);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_google_id ON users(google_id);")

        conn.commit()
        print("✅ Tables created")

    except Exception as e:
        print("❌ Table error:", e)

    finally:
        cur.close()
        release_conn(conn)
