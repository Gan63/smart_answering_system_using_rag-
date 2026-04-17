'''import os
import mysql.connector
from mysql.connector import pooling, Error as MySQLError

# ──────────────────────────────────────────────────────────────────────────────
# DATABASE CONFIGURATION
# All values are read from environment variables — NEVER hardcode credentials.
#
# For LOCAL development, create a `.env` file and load it with python-dotenv.
# For RENDER deployment, set these in: Render Dashboard → Your Service → Environment
#
# Required environment variables:
#   MYSQL_HOST      → e.g. "monorail.proxy.rlwy.net"  (Railway)
#                          or "aws.connect.psdb.cloud"  (PlanetScale)
#   MYSQL_PORT      → e.g. 3306 or the port shown in your cloud DB dashboard
#   MYSQL_USER      → e.g. "root" or your cloud DB username
#   MYSQL_PASSWORD  → your cloud DB password
#   MYSQL_DB        → e.g. "smart_rag_db"
#   MYSQL_SSL       → "true" to enable SSL (required by PlanetScale, recommended for Railway)
# ──────────────────────────────────────────────────────────────────────────────

# Load .env file automatically when running locally
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed; rely on real env vars (Render sets them natively)

# ── Read all connection parameters from environment ──────────────────────────
_HOST     = os.getenv("MYSQL_HOST")
_PORT     = int(os.getenv("MYSQL_PORT", "3306"))
_USER     = os.getenv("MYSQL_USER")
_PASSWORD = os.getenv("MYSQL_PASSWORD")
_DATABASE = os.getenv("MYSQL_DB", "smart_rag_db")
_USE_SSL  = os.getenv("MYSQL_SSL", "false").lower() == "true"

# ── Validate that critical variables are present ─────────────────────────────
_MISSING_VARS = [v for v, val in {
    "MYSQL_HOST": _HOST,
    "MYSQL_USER": _USER,
    "MYSQL_PASSWORD": _PASSWORD,
}.items() if not val]

if _MISSING_VARS:
    print(
        f"\n{'='*60}\n"
        f"⚠️  WARNING: Missing required environment variables:\n"
        f"   {', '.join(_MISSING_VARS)}\n"
        f"   DB features (login/register) will be disabled.\n"
        f"   Set these vars in Render → Your Service → Environment.\n"
        f"{'='*60}\n"
    )

# ── Build the connector config dict ──────────────────────────────────────────
DB_CONFIG: dict = {
    "host":     _HOST or "localhost",   # fallback prevents crash on import
    "port":     _PORT,
    "user":     _USER or "root",
    "password": _PASSWORD or "",
    "database": _DATABASE,
    "connection_timeout": 10,
    "autocommit": False,
}

# PlanetScale and some Railway setups require SSL — enable when MYSQL_SSL=true
if _USE_SSL:
    DB_CONFIG["ssl_disabled"] = False
    DB_CONFIG["ssl_verify_cert"] = False   # set True and supply CA cert for strictest security

# ── Connection pool (created once at import time) ────────────────────────────
connection_pool = None

def _create_pool() -> pooling.MySQLConnectionPool | None:
    """Attempts to create a MySQL connection pool. Returns None on failure."""
    if _MISSING_VARS:
        return None  # don't even try if config is incomplete
    try:
        pool = pooling.MySQLConnectionPool(
            pool_name="smart_rag_pool",
            pool_size=5,
            **DB_CONFIG,
        )
        print("✅ MySQL connection pool created successfully")
        return pool
    except MySQLError as e:
        _print_connection_error(e)
        return None
    except Exception as e:
        print(f"❌ Unexpected error creating MySQL pool: {e}")
        return None

def _print_connection_error(error: Exception) -> None:
    """Prints a user-friendly diagnosis of common MySQL connection errors."""
    err_str = str(error)
    print(f"\n{'='*60}")
    print(f"❌ MySQL Connection Failed: {err_str}")
    if "111" in err_str or "Can't connect" in err_str:
        print("   CAUSE  → Host is unreachable (are you using 'localhost' on Render?)")
        print("   FIX    → Set MYSQL_HOST to your cloud DB hostname in Render Environment vars")
    elif "1045" in err_str or "Access denied" in err_str:
        print("   CAUSE  → Wrong username or password")
        print("   FIX    → Check MYSQL_USER and MYSQL_PASSWORD in your Render Environment vars")
    elif "1049" in err_str or "Unknown database" in err_str:
        print("   CAUSE  → Database does not exist yet on the cloud server")
        print("   FIX    → Create the DB in your Railway / PlanetScale dashboard first")
    elif "SSL" in err_str:
        print("   CAUSE  → SSL required by server but not configured")
        print("   FIX    → Set MYSQL_SSL=true in your Render Environment vars")
    print(f"{'='*60}\n")

# Build the pool on module import
connection_pool = _create_pool()

# ── Public API ────────────────────────────────────────────────────────────────

def get_db_connection() -> mysql.connector.MySQLConnection | None:
    """
    Returns a MySQL connection from the pool.
    Returns None (instead of raising) so callers can handle gracefully.

    Usage:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(503, "Database unavailable")
        try:
            cursor = conn.cursor(dictionary=True)
            ...
        finally:
            conn.close()   # returns the connection back to the pool
    """
    if not connection_pool:
        print("⚠️  DB pool not available — returning None")
        return None
    try:
        return connection_pool.get_connection()
    except MySQLError as e:
        print(f"❌ Failed to get connection from pool: {e}")
        return None

def test_connection() -> dict:
    """
    Health-check helper.  Returns a status dict; safe to call from /health endpoint.
    """
    conn = get_db_connection()
    if not conn:
        return {"connected": False, "error": "Pool unavailable or env vars not set"}
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        return {"connected": True, "host": _HOST, "database": _DATABASE}
    except Exception as e:
        return {"connected": False, "error": str(e)}
    finally:
        conn.close()

def init_db() -> None:
    """
    Creates required tables if they don't already exist.
    Safe to call multiple times (idempotent).
    """
    conn = get_db_connection()
    if not conn:
        print("⚠️  Skipping DB init — no connection available")
        return

    ddl = """
    CREATE TABLE IF NOT EXISTS users (
        id            INT AUTO_INCREMENT PRIMARY KEY,
        full_name     VARCHAR(255) NOT NULL,
        email         VARCHAR(255) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NULL,
        google_id     VARCHAR(255) UNIQUE NULL,
        pfp_url       TEXT NULL,
        created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login    TIMESTAMP NULL,
        INDEX idx_email     (email),
        INDEX idx_google_id (google_id)
    );
    """
    try:
        cursor = conn.cursor()
        cursor.execute(ddl)
        # Gracefully add columns that may be missing in older schemas
        _safe_alter(cursor, "ALTER TABLE users ADD COLUMN google_id VARCHAR(255) UNIQUE NULL AFTER password_hash")
        _safe_alter(cursor, "ALTER TABLE users ADD COLUMN pfp_url TEXT NULL AFTER google_id")
        conn.commit()
        print("✅ MySQL users table ready")
    except Exception as e:
        print(f"❌ Error during DB init: {e}")
    finally:
        cursor.close()
        conn.close()

def _safe_alter(cursor, sql: str) -> None:
    """Executes an ALTER TABLE, silently ignoring 'Duplicate column' errors."""
    try:
        cursor.execute(sql)
    except MySQLError as e:
        if e.errno == 1060:  # ER_DUP_FIELDNAME — column already exists, that's fine
            pass
        else:
            raise

# Auto-init tables when module loads
init_db()'''
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
