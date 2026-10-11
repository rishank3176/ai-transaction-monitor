import sqlite3

from data.db import DB_PATH


def build_customer_profile(customer_id, before_txn_id=None):
    """
    Build a summary using all available data or only transactions
    from strictly earlier PaySim simulation steps.

    before_txn_id identifies the transaction whose step is used
    as the cutoff. Transactions at the same step are excluded.
    """

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        cutoff_step = None

        if before_txn_id is not None:
            current = conn.execute(
                "SELECT step FROM transactions WHERE transaction_id = ?",
                (before_txn_id,),
            ).fetchone()

            if current is None:
                raise ValueError(
                    f"Transaction {before_txn_id} was not found."
                )

            cutoff_step = current["step"]

        query = """
            SELECT COUNT(*) AS n,
                   AVG(amount) AS avg_amount,
                   MAX(amount) AS max_amount
            FROM transactions
            WHERE customer_id = ?
        """
        params = [customer_id]

        if cutoff_step is not None:
            query += " AND step < ?"
            params.append(cutoff_step)

        row = conn.execute(query, params).fetchone()

        flags_query = """
            SELECT COUNT(*)
            FROM actions_log AS a
            JOIN transactions AS t
              ON a.transaction_id = t.transaction_id
            WHERE t.customer_id = ?
              AND a.decision IN ('hold', 'block', 'escalate')
        """
        flags_params = [customer_id]

        if cutoff_step is not None:
            flags_query += " AND t.step < ?"
            flags_params.append(cutoff_step)

        flags = conn.execute(
            flags_query,
            flags_params,
        ).fetchone()[0]

        return {
            "customer_id": customer_id,
            "num_transactions": row["n"],
            "average_amount": row["avg_amount"] or 0.0,
            "max_amount": row["max_amount"] or 0.0,
            "past_flags": flags,
        }
    finally:
        conn.close()