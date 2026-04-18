"""
PostgreSQL Connection Diagnostic Tool
Replaces the old test_mysql.py.

Usage:
    python test_postgres.py

Requires DATABASE_URL to be set in environment or .env file.
"""

import os
import psycopg2

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def test_connection(database_url: str) -> bool:
    try:
        conn = psycopg2.connect(database_url)
        with conn.cursor() as cur:
            cur.execute("SELECT version()")
            version = cur.fetchone()[0]
        conn.close()
        print(f"✅ SUCCESS: Connected to PostgreSQL")
        print(f"   Version : {version}")
        print(f"   DSN     : {database_url.split('@')[-1]}")  # hide credentials
        return True
    except psycopg2.OperationalError as e:
        print(f"❌ Connection failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


if __name__ == "__main__":
    print("--- PostgreSQL Connection Diagnostic Tool ---\n")

    db_url = os.getenv("DATABASE_URL")

    if not db_url:
        print("❌ DATABASE_URL is not set in the environment.")
        print("   → Create a .env file and add:")
        print("     DATABASE_URL=postgresql://user:password@host:5432/dbname")
        exit(1)

    success = test_connection(db_url)

    if success:
        print("\n💡 Database is reachable. Your app should connect normally.")
    else:
        print("\n❌ Could not connect. Check:")
        print("   1. DATABASE_URL value is correct")
        print("   2. Your IP is whitelisted in the cloud DB dashboard")
        print("   3. SSL: try appending ?sslmode=require to the URL")
