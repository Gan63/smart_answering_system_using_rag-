import os
import sys
import psycopg2
import psycopg2.pool
import psycopg2.extras

# Fix Windows console encoding so emoji/unicode prints don't crash
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# ──────────────────────────────────────────────────────────────────────────────
# DATABASE CONFIGURATION
# All values are read from environment variables — NEVER hardcode credentials.
#
# For LOCAL development, create a `.env` file and load it with python-dotenv.
# For RENDER deployment, set these in: Render Dashboard -> Your Service -> Environment
#
# Required environment variable:
#   DATABASE_URL  -> PostgreSQL connection string, e.g.:
#                   postgresql://user:password@host:5432/dbname
#                   (Render / Supabase / Neon / Railway provide this directly)
# ──────────────────────────────────────────────────────────────────────────────

# Load .env file automatically when running locally
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed; rely on real env vars (Render sets them natively)

_DATABASE_URL = os.getenv("DATABASE_URL")

if not _DATABASE_URL:
    print(
        f"\n{'='*60}\n"
        f"[WARNING] DATABASE_URL environment variable is not set.\n"
        f"   DB features (login/register) will be disabled.\n"
        f"   Set DATABASE_URL in Render -> Your Service -> Environment.\n"
        f"{'='*60}\n"
    )

# ── Connection pool (created once at import time) ────────────────────────────
connection_pool: psycopg2.pool.SimpleConnectionPool | None = None


def _create_pool() -> psycopg2.pool.SimpleConnectionPool | None:
    """Attempts to create a PostgreSQL connection pool. Returns None on failure."""
    if not _DATABASE_URL:
        return None
    try:
        pool = psycopg2.pool.SimpleConnectionPool(1, 10, _DATABASE_URL)
        print("[OK] PostgreSQL connection pool created successfully")
        return pool
    except psycopg2.OperationalError as e:
        _print_connection_error(e)
        return None
    except Exception as e:
        print(f"[ERROR] Unexpected error creating PostgreSQL pool: {e}")
        return None


def _print_connection_error(error: Exception) -> None:
    """Prints a user-friendly diagnosis of common PostgreSQL connection errors."""
    err_str = str(error)
    print(f"\n{'='*60}")
    print(f"[ERROR] PostgreSQL Connection Failed: {err_str}")
    if "could not connect" in err_str or "Connection refused" in err_str:
        print("   CAUSE  -> Host is unreachable")
        print("   FIX    -> Verify DATABASE_URL host/port in Render Environment vars")
    elif "password authentication failed" in err_str:
        print("   CAUSE  -> Wrong username or password")
        print("   FIX    -> Check the credentials in your DATABASE_URL")
    elif "does not exist" in err_str:
        print("   CAUSE  -> Database does not exist on the server")
        print("   FIX    -> Create the DB in your cloud provider dashboard first")
    elif "SSL" in err_str:
        print("   CAUSE  -> SSL required by server but not configured")
        print("   FIX    -> Append ?sslmode=require to your DATABASE_URL")
    print(f"{'='*60}\n")


# Build the pool on module import
connection_pool = _create_pool()


# ── Public API ────────────────────────────────────────────────────────────────

def get_conn() -> psycopg2.extensions.connection | None:
    """
    Returns a PostgreSQL connection from the pool.
    Returns None (instead of raising) so callers can handle gracefully.

    IMPORTANT: Always call release_conn(conn) in a finally block to
    return the connection back to the pool.

    Usage:
        conn = get_conn()
        if not conn:
            raise HTTPException(503, "Database unavailable")
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT ...")
                rows = cur.fetchall()
            conn.commit()
        finally:
            release_conn(conn)
    """
    if not connection_pool:
        print("[WARN] DB pool not available — returning None")
        return None
    try:
        return connection_pool.getconn()
    except Exception as e:
        print(f"[ERROR] Failed to get connection from pool: {e}")
        return None


def release_conn(conn) -> None:
    """Returns a connection back to the pool."""
    if connection_pool and conn:
        connection_pool.putconn(conn)


def get_db_connection() -> psycopg2.extensions.connection | None:
    """Alias for get_conn() — used by app.py and other modules."""
    return get_conn()


def test_connection() -> dict:
    """
    Health-check helper. Returns a status dict; safe to call from /db-health endpoint.
    """
    conn = get_conn()
    if not conn:
        return {"connected": False, "error": "Pool unavailable or DATABASE_URL not set"}
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT version()")
            version = cur.fetchone()[0]
        return {
            "connected": True,
            "database": _DATABASE_URL.split("/")[-1].split("?")[0] if _DATABASE_URL else "unknown",
            "version": version,
        }
    except Exception as e:
        return {"connected": False, "error": str(e)}
    finally:
        release_conn(conn)


def init_db() -> None:
    """
    Creates required tables if they don't already exist.
    Safe to call multiple times (idempotent).
    """
    conn = get_conn()
    if not conn:
        print("[INFO] Skipping DB init — no connection available")
        return

    ddl = """
    CREATE TABLE IF NOT EXISTS users (
        id            SERIAL PRIMARY KEY,
        full_name     VARCHAR(255) NOT NULL,
        email         VARCHAR(255) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NULL,
        google_id     VARCHAR(255) UNIQUE NULL,
        pfp_url       TEXT NULL,
        created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login    TIMESTAMP NULL
    );
    CREATE INDEX IF NOT EXISTS idx_email     ON users(email);
    CREATE INDEX IF NOT EXISTS idx_google_id ON users(google_id);
    """
    try:
        with conn.cursor() as cur:
            cur.execute(ddl)
        conn.commit()
        print("[OK] PostgreSQL users table ready")
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Error during DB init: {e}")
    finally:
        release_conn(conn)


# Auto-init tables when module loads
init_db()
