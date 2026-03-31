import mysql.connector
from mysql.connector import pooling
import os

# Database configurations
DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", "root@123"),  # Using environment variable or empty string default
    "database": os.getenv("MYSQL_DB", "smart_rag_db"),
    "port": int(os.getenv("MYSQL_PORT", 3306))
}

# Create a connection pool for general efficiency
try:
    connection_pool = pooling.MySQLConnectionPool(
        pool_name="smart_rag_pool",
        pool_size=5,
        **DB_CONFIG
    )
    print("✅ MySQL Connection Pool Created Successfully")
except Exception as e:
    print(f"❌ Error creating connection pool: {e}")
    # In case the database doesn't exist, try connecting without the database name first
    try:
        temp_config = DB_CONFIG.copy()
        db_name = temp_config.pop("database")
        conn = mysql.connector.connect(**temp_config)
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        cursor.close()
        conn.close()
        
        # Now try to create the pool again
        connection_pool = pooling.MySQLConnectionPool(
            pool_name="smart_rag_pool",
            pool_size=5,
            **DB_CONFIG
        )
        print(f"✅ Database {db_name} created and Connection Pool Initialized")
    except Exception as inner_e:
        if "1045" in str(inner_e):
            print("\n" + "="*50)
            print("🚨 CRITICAL: MySQL Access Denied (Error 1045)")
            print("Please update your password in: database/db_config.py")
            print("Or set the MYSQL_PASSWORD environment variable.")
            print("="*50 + "\n")
        else:
            print(f"❌ Critical Error initializing MySQL: {inner_e}")
        connection_pool = None

def get_db_connection():
    if connection_pool:
        return connection_pool.get_connection()
    return None

def init_db():
    """Initializes the database by creating necessary tables."""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        
        # Create users table
        create_users_table = """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            full_name VARCHAR(255) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP NULL
        );
        
        """
        cursor.execute(create_users_table)
        conn.commit()
        print("✅ MySQL Users table initialized in smart_rag_db")
        
        cursor.close()
    except Exception as e:
        print(f"❌ Error initializing tables: {e}")
    finally:
        conn.close()

# Initialize the DB on import
init_db()
