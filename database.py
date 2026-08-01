"""
database.py
------------
Handles the database connection and schema for ENZ Bank.

Currently uses SQLite (file-based, zero setup, real SQL).
To migrate to PostgreSQL later:
  1. `pip install psycopg2-binary`
  2. Replace `get_connection()` below with a psycopg2.connect(...) call
     using a DATABASE_URL environment variable.
  3. Because all queries in bank.py use plain SQL through this single
     `get_connection()` function, nothing else needs to change.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.db")

# The bank's single IFSC code (ENZ Bank is modeled as one branch/bank).
# Used to validate "own-bank" IFSC transfers.
BANK_IFSC_CODE = "ENZB0000001"

# Where profile photos are stored on disk (path saved in the accounts table).
PROFILE_PHOTO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profile_photos")
os.makedirs(PROFILE_PHOTO_DIR, exist_ok=True)

UPI_DOMAIN = "enzbank"  # UPI IDs look like 9876543210@enzbank

# Account status values
STATUS_ACTIVE = "active"
STATUS_FROZEN = "frozen"      # can log in & view, cannot transact
STATUS_SUSPENDED = "suspended"  # cannot log in at all


def get_connection():
    """Return a new sqlite3 connection with row access by column name."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create tables if they don't already exist."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            account_number TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            age INTEGER NOT NULL,
            email TEXT NOT NULL,
            address TEXT NOT NULL,
            pin_hash TEXT NOT NULL,
            ifsc_code TEXT NOT NULL,
            balance REAL NOT NULL DEFAULT 0,
            wallet_balance REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            mobile_number TEXT,
            upi_id TEXT,
            profile_photo_path TEXT,
            status TEXT NOT NULL DEFAULT 'active'
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_number TEXT NOT NULL,
            type TEXT NOT NULL,
            amount REAL NOT NULL,
            balance_after REAL NOT NULL,
            description TEXT,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            FOREIGN KEY (account_number) REFERENCES accounts (account_number)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL
        )
    """)

    # Audit trail of admin actions on customer accounts (freeze/suspend/delete).
    # Admin can never edit account data, but every account-affecting action
    # they take is logged here so it's always auditable.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admin_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_username TEXT NOT NULL,
            account_number TEXT NOT NULL,
            action TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL
        )
    """)

    conn.commit()

    # --- Migration: add new columns to an accounts table created by an
    # older version of this app, without losing existing data. ---
    cur.execute("PRAGMA table_info(accounts)")
    existing_columns = {row["name"] for row in cur.fetchall()}
    migrations = {
        "mobile_number": "ALTER TABLE accounts ADD COLUMN mobile_number TEXT",
        "upi_id": "ALTER TABLE accounts ADD COLUMN upi_id TEXT",
        "profile_photo_path": "ALTER TABLE accounts ADD COLUMN profile_photo_path TEXT",
        "status": "ALTER TABLE accounts ADD COLUMN status TEXT NOT NULL DEFAULT 'active'",
    }
    for column, statement in migrations.items():
        if column not in existing_columns:
            cur.execute(statement)
    conn.commit()

    # Seed a default admin account if none exists yet (username: admin / password: admin123)
    cur.execute("SELECT COUNT(*) as c FROM admins")
    if cur.fetchone()["c"] == 0:
        import hashlib
        default_hash = hashlib.sha256("admin123".encode()).hexdigest()
        cur.execute(
            "INSERT INTO admins (username, password_hash) VALUES (?, ?)",
            ("admin", default_hash),
        )
        conn.commit()

    conn.close()
