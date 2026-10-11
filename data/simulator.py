import sqlite3
import time

from data.db import DB_PATH


def stream_transactions(start_id=1, count=20, delay=1.0):
    """Yield transactions sequentially to simulate a live feed."""

    if count < 0:
        raise ValueError("count cannot be negative.")

    if delay < 0:
        raise ValueError("delay cannot be negative.")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        rows = conn.execute(
            """
            SELECT *
            FROM transactions
            WHERE transaction_id >= ?
            ORDER BY transaction_id
            LIMIT ?
            """,
            (start_id, count),
        ).fetchall()
    finally:
        conn.close()

    for index, row in enumerate(rows):
        yield dict(row)

        if index < len(rows) - 1:
            time.sleep(delay)


if __name__ == "__main__":
    for txn in stream_transactions(count=5, delay=0.5):
        print(
            "New transaction:",
            txn["transaction_id"],
            txn["type"],
            txn["amount"],
        )