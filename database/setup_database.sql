-- ============================================================
-- Smart RAG Assistant — PostgreSQL Schema
-- ============================================================
-- Run this against your PostgreSQL database to create all tables.
-- Compatible with: Render Postgres, Supabase, Neon, Railway, local psql
--
-- Usage (psql):
--   psql $DATABASE_URL -f setup_database.sql
-- ============================================================

-- Users table
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

-- Indexes
CREATE INDEX IF NOT EXISTS idx_email     ON users(email);
CREATE INDEX IF NOT EXISTS idx_google_id ON users(google_id);
