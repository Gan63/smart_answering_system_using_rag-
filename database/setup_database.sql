import os
import psycopg2
from psycopg2 import pool

connection_pool = None

def init_db():
    global connection_pool
    try:
        connection_pool = psycopg2.pool.SimpleConnectionPool(
            1, 10,
            os.getenv("DATABASE_URL")
        )
        print("✅ DB connected")
    except Exception as e:
        print("❌ DB error:", e)


def get_conn():
    return connection_pool.getconn() if connection_pool else None


def release_conn(conn):
    if connection_pool and conn:
        connection_pool.putconn(conn)
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NULL,
    google_id VARCHAR(255) UNIQUE NULL,
    pfp_url TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP NULL
);

-- Index for faster lookups
CREATE INDEX idx_email ON users(email);
CREATE INDEX idx_google_id ON users(google_id);
