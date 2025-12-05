from typing import List, Optional, Tuple
import sqlite3

from .config import ANSWER_LIKE, ANSWER_DISLIKE, ANSWER_NEUTRAL, ROUND_ONE, ROUND_TWO
from .db import ensure_user, get_pair_for_user, get_pair_by_id


def create_or_join_pair(conn: sqlite3.Connection, user_id: int, username: Optional[str], chat_id: Optional[int]) -> Tuple[sqlite3.Row, bool]:
    """Create a new pending pair or join an existing pending pair.

    Returns (pair_row, paired_now). paired_now=True means the pair just became complete.
    """
    ensure_user(conn, user_id, username=username, chat_id=chat_id)

    # If user is already in a pair, return it
    existing = get_pair_for_user(conn, user_id)
    if existing:
        return existing, False

    cur = conn.cursor()
    # Find a pending pair waiting for a second user
    cur.execute("SELECT * FROM pairs WHERE user2_id IS NULL ORDER BY id ASC LIMIT 1")
    pending = cur.fetchone()
    if pending and pending["user1_id"] != user_id:
        cur.execute("UPDATE pairs SET user2_id=? WHERE id=?", (user_id, pending["id"]))
        conn.commit()
        updated = get_pair_by_id(conn, pending["id"])
        return updated, True

    # Otherwise create a new pending pair with this user as user1
    cur.execute("INSERT INTO pairs(user1_id, current_round) VALUES (?, ?)", (user_id, ROUND_ONE))
    conn.commit()
    new_pair_id = cur.lastrowid
    new_pair = get_pair_by_id(conn, new_pair_id)
    return new_pair, False


def get_user_pair(conn: sqlite3.Connection, user_id: int) -> Optional[sqlite3.Row]:
    return get_pair_for_user(conn, user_id)


def get_pair_users(conn: sqlite3.Connection, pair_id: int) -> Optional[Tuple[int, int]]:
    pr = get_pair_by_id(conn, pair_id)
    if not pr or pr["user2_id"] is None:
        return None
    return pr["user1_id"], pr["user2_id"]


def record_answer(conn: sqlite3.Connection, pair_id: int, round_num: int, user_id: int, name_id: int, answer: str) -> bool:
    if answer not in (ANSWER_LIKE, ANSWER_DISLIKE, ANSWER_NEUTRAL):
        raise ValueError("Invalid answer")
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO ratings(pair_id, round, user_id, name_id, answer) VALUES (?, ?, ?, ?, ?)",
        (pair_id, round_num, user_id, name_id, answer),
    )
    conn.commit()
    return cur.rowcount > 0


def get_next_name_for_round(conn: sqlite3.Connection, pair_id: int, round_num: int, user_id: int) -> Optional[sqlite3.Row]:
    cur = conn.cursor()
    if round_num == ROUND_ONE:
        cur.execute(
            """
            SELECT n.id, n.name FROM names n
            WHERE n.id NOT IN (
                SELECT name_id FROM ratings WHERE pair_id=? AND round=? AND user_id=?
            )
            ORDER BY n.id ASC
            LIMIT 1
            """,
            (pair_id, ROUND_ONE, user_id),
        )
        return cur.fetchone()

    # Round two: only names liked by both users in round 1
    cur.execute(
        """
        SELECT DISTINCT n.id, n.name
        FROM names n
        JOIN ratings r1 ON r1.name_id = n.id AND r1.pair_id = ? AND r1.round = 1 AND r1.answer = 'like'
        JOIN ratings r2 ON r2.name_id = n.id AND r2.pair_id = ? AND r2.round = 1 AND r2.answer = 'like'
        WHERE n.id NOT IN (
            SELECT name_id FROM ratings WHERE pair_id = ? AND round = 2 AND user_id = ?
        )
        ORDER BY n.id ASC
        LIMIT 1
        """,
        (pair_id, pair_id, pair_id, user_id),
    )
    return cur.fetchone()


def get_results_for_round(conn: sqlite3.Connection, pair_id: int, round_num: int) -> List[str]:
    cur = conn.cursor()
    # Restrict to likes from user1 and user2 specifically to avoid duplicates
    cur.execute(
        """
        SELECT DISTINCT n.name
        FROM names n
        JOIN ratings r1 ON r1.name_id = n.id AND r1.pair_id = ? AND r1.round = ? AND r1.answer = 'like' AND r1.user_id = (SELECT user1_id FROM pairs WHERE id = ?)
        JOIN ratings r2 ON r2.name_id = n.id AND r2.pair_id = ? AND r2.round = ? AND r2.answer = 'like' AND r2.user_id = (SELECT user2_id FROM pairs WHERE id = ?)
        ORDER BY n.name COLLATE NOCASE ASC
        """,
        (pair_id, round_num, pair_id, pair_id, round_num, pair_id),
    )
    return [row["name"] for row in cur.fetchall()]


def get_round_progress(conn: sqlite3.Connection, pair_id: int, round_num: int, user_id: int) -> Tuple[int, int]:
    """Return (answered_count, total_count) for the given pair/user/round.

    - Round 1 total is count of all names.
    - Round 2 total is count of names liked by both users in round 1.
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) AS cnt FROM ratings WHERE pair_id=? AND round=? AND user_id=?",
        (pair_id, round_num, user_id),
    )
    answered = int(cur.fetchone()["cnt"])

    if round_num == ROUND_ONE:
        cur.execute("SELECT COUNT(*) AS cnt FROM names")
        total = int(cur.fetchone()["cnt"])
        return answered, total

    # Round two total: names liked by both user1 and user2 in round 1
    cur.execute(
        """
        SELECT COUNT(DISTINCT n.id) AS cnt
        FROM names n
        JOIN ratings r1 ON r1.name_id = n.id AND r1.pair_id = ? AND r1.round = 1 AND r1.answer = 'like' AND r1.user_id = (SELECT user1_id FROM pairs WHERE id = ?)
        JOIN ratings r2 ON r2.name_id = n.id AND r2.pair_id = ? AND r2.round = 1 AND r2.answer = 'like' AND r2.user_id = (SELECT user2_id FROM pairs WHERE id = ?)
        """,
        (pair_id, pair_id, pair_id, pair_id),
    )
    total = int(cur.fetchone()["cnt"])
    return answered, total


def start_second_round(conn: sqlite3.Connection, pair_id: int) -> None:
    cur = conn.cursor()
    cur.execute("UPDATE pairs SET current_round=?, started_2=1 WHERE id=?", (ROUND_TWO, pair_id))
    conn.commit()