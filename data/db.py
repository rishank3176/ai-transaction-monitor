from pathlib import Path
import sqlite3

DB_PATH = Path(__file__).resolve().with_name("transactions.db")

VALID_STATUSES = {"pending", "approve", "hold", "block", "escalate"}


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_transaction(txn_id):
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM transactions WHERE transaction_id = ?",
            (txn_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_customer_history(customer_id):
    conn = _connect()
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) AS num_transactions,
                   AVG(amount) AS average_amount,
                   MAX(amount) AS max_amount
            FROM transactions
            WHERE customer_id = ?
            """,
            (customer_id,),
        ).fetchone()

        return {
            "customer_id": customer_id,
            "num_transactions": row["num_transactions"],
            "average_amount": row["average_amount"] or 0.0,
            "max_amount": row["max_amount"] or 0.0,
        }
    finally:
        conn.close()


def update_status(txn_id, status):
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}")

    conn = _connect()
    try:
        cursor = conn.execute(
            "UPDATE transactions SET status = ? WHERE transaction_id = ?",
            (status, txn_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def log_action(
    transaction_id,
    decision,
    confidence,
    reasoning,
    decided_by="agent",
):
    if decision not in VALID_STATUSES - {"pending"}:
        raise ValueError(f"Invalid decision: {decision}")

    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO actions_log
            (transaction_id, decision, confidence, reasoning, decided_by)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                transaction_id,
                decision,
                confidence,
                reasoning,
                decided_by,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def add_feedback(transaction_id, agent_decision, human_decision):
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO feedback
            (transaction_id, agent_decision, human_decision)
            VALUES (?, ?, ?)
            """,
            (transaction_id, agent_decision, human_decision),
        )
        conn.commit()
    finally:
        conn.close()