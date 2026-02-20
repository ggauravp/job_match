-- Create jobs table for Cotiviti Jobs Scraper
-- Run this script in your PostgreSQL database

CREATE TABLE IF NOT EXISTS jobs (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    company VARCHAR(255),
    location VARCHAR(255),
    link TEXT,
    description TEXT,
    qualifications TEXT,
    country VARCHAR(100),
    deadline DATE,
    adzuna_id VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index on adzuna_id for faster lookups
CREATE INDEX IF NOT EXISTS idx_adzuna_id ON jobs(adzuna_id);

-- Create index on company for filtering
CREATE INDEX IF NOT EXISTS idx_company ON jobs(company);

-- Create index on country for filtering
CREATE INDEX IF NOT EXISTS idx_country ON jobs(country);
