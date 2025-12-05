import sqlite3
from typing import Iterable, Optional

from .config import ANSWER_LIKE, ANSWER_DISLIKE, ANSWER_NEUTRAL


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    # Names table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS names (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );
        """
    )

    # Users table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            chat_id INTEGER
        );
        """
    )

    # Pair sessions (two participants per pair)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS pairs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user1_id INTEGER NOT NULL,
            user2_id INTEGER,
            current_round INTEGER NOT NULL DEFAULT 1,
            started_2 INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # Ratings (each user answers each name only once per pair and round)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pair_id INTEGER NOT NULL,
            round INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            name_id INTEGER NOT NULL,
            answer TEXT NOT NULL CHECK (answer IN ('like','dislike','neutral')),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(pair_id, round, user_id, name_id)
        );
        """
    )

    # Helpful indexes
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ratings_pair_round ON ratings(pair_id, round);
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ratings_user_round ON ratings(user_id, round);
        """
    )
    conn.commit()


def ensure_user(conn: sqlite3.Connection, user_id: int, username: Optional[str] = None, chat_id: Optional[int] = None) -> None:
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users(user_id, username, chat_id) VALUES (?, ?, ?)", (user_id, username, chat_id))
    # Update fields if provided
    if username is not None:
        cur.execute("UPDATE users SET username=? WHERE user_id=?", (username, user_id))
    if chat_id is not None:
        cur.execute("UPDATE users SET chat_id=? WHERE user_id=?", (chat_id, user_id))
    conn.commit()


def get_user(conn: sqlite3.Connection, user_id: int) -> Optional[sqlite3.Row]:
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    return row


def add_names(conn: sqlite3.Connection, names: Iterable[str]) -> int:
    cur = conn.cursor()
    to_insert = [(n.strip(),) for n in names if n and n.strip()]
    cur.executemany("INSERT OR IGNORE INTO names(name) VALUES (?)", to_insert)
    conn.commit()
    return cur.rowcount


def get_pair_by_id(conn: sqlite3.Connection, pair_id: int) -> Optional[sqlite3.Row]:
    cur = conn.cursor()
    cur.execute("SELECT * FROM pairs WHERE id=?", (pair_id,))
    return cur.fetchone()


def get_pair_for_user(conn: sqlite3.Connection, user_id: int) -> Optional[sqlite3.Row]:
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM pairs WHERE user1_id=? OR user2_id=? ORDER BY id DESC LIMIT 1",
        (user_id, user_id),
    )
    return cur.fetchone()


def get_other_user_id(conn: sqlite3.Connection, pair_id: int, user_id: int) -> Optional[int]:
    pair = get_pair_by_id(conn, pair_id)
    if not pair:
        return None
    if pair["user1_id"] == user_id:
        return pair["user2_id"]
    return pair["user1_id"]


def get_user_chat_id(conn: sqlite3.Connection, user_id: int) -> Optional[int]:
    u = get_user(conn, user_id)
    return None if u is None else u["chat_id"]