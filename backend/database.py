"""
database.py

SQLite-backed verification dataset for CertificateGuard AI.
Mirrors the small demo dataset used on the front end (KNOWN_INSTITUTIONS
and KNOWN_RECORDS in script.js) so the backend can be swapped in without
changing the shape of the data the app is checking against.

This is a demo dataset, not a live registry.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "certguard.db"

KNOWN_INSTITUTIONS = [
    "NPTEL", "Indian Institute of Technology Madras", "IIT Madras",
    "Anna University", "National Institute of Technology Trichy", "NIT Trichy",
    "Coursera", "Infosys Springboard", "Google Developers",
    "Amrita Vishwa Vidyapeetham", "VIT Vellore", "SRM Institute of Science and Technology",
    "Great Learning", "edX", "Skill India", "AICTE",
]

KNOWN_RECORDS = [
    {"id": "NPTEL24CS0113", "name": "Ananya Rao", "institution": "NPTEL",
     "course": "Data Structures and Algorithms", "issue_date": "2024-07-20"},
    {"id": "IITM-INT-2023-889", "name": "Karthik Subramaniam", "institution": "IIT Madras",
     "course": "Machine Learning Internship", "issue_date": "2023-05-11"},
    {"id": "ANU-BE-CSE-11029", "name": "Divya Sundaram", "institution": "Anna University",
     "course": "B.E. Computer Science and Engineering", "issue_date": "2022-06-01"},
    {"id": "GL-DS-2024-4471", "name": "Rohan Mehta", "institution": "Great Learning",
     "course": "Applied Data Science", "issue_date": "2024-02-18"},
]


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables and seed demo data if the database is empty."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS institutions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS certificates (
            cert_id TEXT PRIMARY KEY,
            candidate_name TEXT NOT NULL,
            institution TEXT NOT NULL,
            course TEXT,
            issue_date TEXT
        )
    """)

    cur.execute("SELECT COUNT(*) FROM institutions")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT OR IGNORE INTO institutions (name) VALUES (?)",
            [(name,) for name in KNOWN_INSTITUTIONS],
        )

    cur.execute("SELECT COUNT(*) FROM certificates")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            """INSERT OR IGNORE INTO certificates
               (cert_id, candidate_name, institution, course, issue_date)
               VALUES (:id, :name, :institution, :course, :issue_date)""",
            KNOWN_RECORDS,
        )

    conn.commit()
    conn.close()


def get_institution_names():
    conn = get_connection()
    rows = conn.execute("SELECT name FROM institutions").fetchall()
    conn.close()
    return [r["name"] for r in rows]


def find_certificate_by_id(cert_id: str):
    """Case-insensitive exact match, mirroring the frontend's lookup."""
    if not cert_id:
        return None
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM certificates WHERE LOWER(cert_id) = LOWER(?)",
        (cert_id.strip(),),
    ).fetchone()
    conn.close()
    return dict(row) if row else None