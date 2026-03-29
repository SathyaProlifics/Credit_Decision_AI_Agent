#!/usr/bin/env python3
"""Setup script to create the credit_applications table in the database."""

import os
import pymysql
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load environment variables
env_file = Path(__file__).parent / '.env'
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

# Load properties from resource/properties
def load_properties():
    props_path = os.path.join(os.path.dirname(__file__), "resource", "properties")
    result = {}
    try:
        if os.path.exists(props_path):
            logger.info(f"Loading DB properties from {props_path}")
            with open(props_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        result[k.strip()] = v.strip()
            logger.info(f"Successfully loaded {len(result)} DB properties")
        else:
            logger.warning(f"resource/properties file not found at {props_path}")
    except Exception as e:
        logger.error(f"Failed to read {props_path}: {e}")
    return result

props = load_properties()

# Get DB connection parameters
host = props.get("DB_HOST") or os.getenv("DB_HOST") or "sathya-database.cilmgugy4iud.us-east-1.rds.amazonaws.com"
port = int(props.get("DB_PORT") or os.getenv("DB_PORT") or "3306")
user = props.get("DB_USER") or os.getenv("DB_USER") or "admin"
password = props.get("DB_PASSWORD") or os.getenv("DB_PASSWORD")
db = props.get("DB_NAME") or os.getenv("DB_NAME") or "dev"

logger.info(f"Database config: host={host}, port={port}, user={user}, database={db}")

if not password:
    logger.error("Database password not set!")
    exit(1)

# Connect to database
try:
    logger.info(f"Connecting to {db}@{host}:{port}...")
    conn = pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=db,
        cursorclass=pymysql.cursors.DictCursor
    )
    logger.info("Successfully connected to database")
except Exception as e:
    logger.error(f"Failed to connect to database: {e}")
    exit(1)

# Create table SQL
create_table_sql = """
CREATE TABLE IF NOT EXISTS credit_applications (
    id INT PRIMARY KEY AUTO_INCREMENT,
    applicant_name VARCHAR(255),
    applicant_dob DATE,
    age INT,
    email VARCHAR(255),
    income DECIMAL(15,2),
    employment_status VARCHAR(50),
    credit_score INT,
    dti_ratio DECIMAL(5,4),
    existing_debts DECIMAL(15,2),
    requested_credit DECIMAL(15,2),
    
    source VARCHAR(50),              -- 'web', 'api', etc.
    application_status VARCHAR(50),  -- PENDING, PROCESSING, APPROVE, DENY, REFER, ERROR
    reason TEXT,                     -- Explanation from AI decision
    confidence INT,                  -- 1-100 from make_decision_tool
    agent_output JSON,               -- Complete result from all 4 steps
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_status (application_status),
    INDEX idx_applicant (applicant_name),
    INDEX idx_created (created_at)
);
"""

# Execute create table
try:
    with conn.cursor() as cur:
        logger.info("Creating credit_applications table...")
        cur.execute(create_table_sql)
        conn.commit()
        logger.info("✓ Table created successfully!")
except Exception as e:
    logger.error(f"Failed to create table: {e}")
    conn.close()
    exit(1)

# Verify table was created
try:
    with conn.cursor() as cur:
        cur.execute("SHOW TABLES LIKE 'credit_applications'")
        result = cur.fetchone()
        if result:
            logger.info("✓ Table 'credit_applications' verified in database")
        else:
            logger.warning("Table 'credit_applications' not found after creation")
except Exception as e:
    logger.error(f"Failed to verify table: {e}")

conn.close()
logger.info("Setup complete!")
