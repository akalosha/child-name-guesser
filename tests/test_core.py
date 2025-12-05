import unittest
import sqlite3
from pathlib import Path

from bot_app import config
from bot_app.db import init_db, add_names
from bot_app.core import (
    create_or_join_pair,
    get_user_pair,
    get_next_name_for_round,
    record_answer,
    get_results_for_round,
    start_second_round,
    get_round_progress,
)
from bot_app.names_loader import load_names


class TestCoreLogic(unittest.TestCase):
    def setUp(self):
        # In-memory DB for isolation
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        init_db(self.conn)
        # Load names from file
        names_file = config.NAMES_FILE
        self.assertTrue(Path(names_file).exists(), f"Names file missing: {names_file}")
        names = load_names(names_file)
        # To keep tests fast, only seed first 30 names
        add_names(self.conn, names[:30])

    def test_pairing_and_round1_flow(self):
        # User 1 joins
        pair1, paired_now1 = create_or_join_pair(self.conn, 101, "user1", 1001)
        self.assertFalse(paired_now1)
        self.assertIsNone(pair1["user2_id"])  # waiting

        # User 2 joins
        pair2, paired_now2 = create_or_join_pair(self.conn, 202, "user2", 2002)
        self.assertTrue(paired_now2)
        self.assertEqual(pair1["id"], pair2["id"])  # same pair

        pair = get_user_pair(self.conn, 101)
        self.assertIsNotNone(pair)
        self.assertEqual(pair["user1_id"], 101)
        self.assertEqual(pair["user2_id"], 202)

        # Get next name for round 1
        n1 = get_next_name_for_round(self.conn, pair["id"], 1, 101)
        self.assertIsNotNone(n1)
        # Record like by user1
        ok1 = record_answer(self.conn, pair["id"], 1, 101, n1["id"], "like")
        self.assertTrue(ok1)
        # Duplicate record should be ignored
        ok1_dup = record_answer(self.conn, pair["id"], 1, 101, n1["id"], "like")
        self.assertFalse(ok1_dup)

        # User2 also likes the same name
        ok2 = record_answer(self.conn, pair["id"], 1, 202, n1["id"], "like")
        self.assertTrue(ok2)

        # Next name appears for user1 and user2
        n1_next = get_next_name_for_round(self.conn, pair["id"], 1, 101)
        n2_next = get_next_name_for_round(self.conn, pair["id"], 1, 202)
        self.assertIsNotNone(n1_next)
        self.assertIsNotNone(n2_next)

        # Both like second name
        record_answer(self.conn, pair["id"], 1, 101, n1_next["id"], "like")
        record_answer(self.conn, pair["id"], 1, 202, n1_next["id"], "like")

        # Third name: user1 like, user2 dislike
        n3 = get_next_name_for_round(self.conn, pair["id"], 1, 101)
        record_answer(self.conn, pair["id"], 1, 101, n3["id"], "like")
        record_answer(self.conn, pair["id"], 1, 202, n3["id"], "dislike")

        # Result for round 1 should include first two names only
        r1 = get_results_for_round(self.conn, pair["id"], 1)
        self.assertIn(n1["name"], r1)
        self.assertIn(n1_next["name"], r1)
        self.assertNotIn(n3["name"], r1)

    def test_round2_flow_and_results(self):
        pair1, _ = create_or_join_pair(self.conn, 300, "u300", 1300)
        pair2, _ = create_or_join_pair(self.conn, 400, "u400", 1400)
        pair = get_user_pair(self.conn, 300)

        # Let both users like first two names
        n1 = get_next_name_for_round(self.conn, pair["id"], 1, 300)
        n2 = get_next_name_for_round(self.conn, pair["id"], 1, 400)
        record_answer(self.conn, pair["id"], 1, 300, n1["id"], "like")
        record_answer(self.conn, pair["id"], 1, 400, n1["id"], "like")
        # Next name for each
        n1_next = get_next_name_for_round(self.conn, pair["id"], 1, 300)
        record_answer(self.conn, pair["id"], 1, 300, n1_next["id"], "like")
        record_answer(self.conn, pair["id"], 1, 400, n1_next["id"], "like")

        # Third name: one neutral, one like -> not in round1 results
        n3 = get_next_name_for_round(self.conn, pair["id"], 1, 300)
        record_answer(self.conn, pair["id"], 1, 300, n3["id"], "neutral")
        record_answer(self.conn, pair["id"], 1, 400, n3["id"], "like")

        r1 = get_results_for_round(self.conn, pair["id"], 1)
        self.assertEqual(len(r1), 2)

        # Start round 2
        start_second_round(self.conn, pair["id"])

        # Round 2 should offer only those two names
        n2_r2_a = get_next_name_for_round(self.conn, pair["id"], 2, 300)
        self.assertIsNotNone(n2_r2_a)
        record_answer(self.conn, pair["id"], 2, 300, n2_r2_a["id"], "like")
        record_answer(self.conn, pair["id"], 2, 400, n2_r2_a["id"], "like")

        n2_r2_b = get_next_name_for_round(self.conn, pair["id"], 2, 300)
        self.assertIsNotNone(n2_r2_b)
        # One dislikes in round2, so it won't be in round2 results
        record_answer(self.conn, pair["id"], 2, 300, n2_r2_b["id"], "dislike")
        record_answer(self.conn, pair["id"], 2, 400, n2_r2_b["id"], "like")

        # Round 2 results should include only the first liked-by-both
        r2 = get_results_for_round(self.conn, pair["id"], 2)
        self.assertIn(n2_r2_a["name"], r2)
        self.assertNotIn(n2_r2_b["name"], r2)

    def test_progress_counts_rounds(self):
        pair1, _ = create_or_join_pair(self.conn, 501, "u501", 1501)
        pair2, _ = create_or_join_pair(self.conn, 502, "u502", 1502)
        pair = get_user_pair(self.conn, 501)

        # Initially, round1 answered = 0, total = number of names seeded (30)
        a1, t1 = get_round_progress(self.conn, pair["id"], 1, 501)
        self.assertEqual(a1, 0)
        self.assertEqual(t1, 30)

        # User 501 rates two names in round1
        n1 = get_next_name_for_round(self.conn, pair["id"], 1, 501)
        record_answer(self.conn, pair["id"], 1, 501, n1["id"], "like")
        n2 = get_next_name_for_round(self.conn, pair["id"], 1, 501)
        record_answer(self.conn, pair["id"], 1, 501, n2["id"], "like")
        a1b, t1b = get_round_progress(self.conn, pair["id"], 1, 501)
        self.assertEqual(a1b, 2)
        self.assertEqual(t1b, 30)

        # Make two common likes to seed round2 candidates
        record_answer(self.conn, pair["id"], 1, 502, n1["id"], "like")
        record_answer(self.conn, pair["id"], 1, 502, n2["id"], "like")
        start_second_round(self.conn, pair["id"])

        # Round2 total should be 2, answered initially 0
        a2, t2 = get_round_progress(self.conn, pair["id"], 2, 501)
        self.assertEqual(a2, 0)
        self.assertEqual(t2, 2)

        # User 501 answers one in round2
        n2_r2 = get_next_name_for_round(self.conn, pair["id"], 2, 501)
        record_answer(self.conn, pair["id"], 2, 501, n2_r2["id"], "like")
        a2b, t2b = get_round_progress(self.conn, pair["id"], 2, 501)
        self.assertEqual(a2b, 1)
        self.assertEqual(t2b, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)