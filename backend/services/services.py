import sqlite3
import os
import pathlib

PATH = pathlib.Path.home() / "spacecat" / "backend" / "spacecat.db"


def init_db(): 
    db = sqlite3.connect(PATH)
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            password TEXT NOT NULL
        )
    """)
