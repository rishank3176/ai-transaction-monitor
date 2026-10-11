
"""Save human review feedback for later analysis."""

from data.db import DB_PATH, VALID_DECISIONS, _connect


def save_feedback(txn_id: int, human_decision: str) -> dict:
    """Save a human decision after an agent decision exists."""

    if human_decision not in VALID_DECISIONS:
        raise ValueError(
            f"human_decision must be one of {sorted(VALID_DECISIONS)}"
        )

    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DB_PATH}. "
            "Run: python -m data.build_db"
        )

    with _connect() as conn:
        row = conn.execute(
            """
            SELECT decision
            FROM actions_log
            WHERE transaction_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (txn_id,),
        ).fetchone()

        if row is None:
            raise ValueError(
                f"Transaction {txn_id} has no agent decision to review"
            )

        agent_decision = row["decision"]

        conn.execute(
            """
            INSERT INTO feedback
                (transaction_id, agent_decision, human_decision)
            VALUES (?, ?, ?)
            """,
            (txn_id, agent_decision, human_decision),
        )

    return {
        "transaction_id": txn_id,
        "agent_decision": agent_decision,
        "human_decision": human_decision,
        "saved": True,
    }
