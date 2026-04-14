-- Smart RAG Database Schema
-- This file can be used to manually setup the MySQL database

CREATE DATABASE IF NOT EXISTS smart_rag_db;
USE smart_rag_db;

-- Users table
-- Note: password_hash is nullable to allow for social logins (Google, etc.)
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
