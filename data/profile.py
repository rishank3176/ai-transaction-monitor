import math
import sqlite3

from data.db import DB_PATH


def _stats(amounts):
    """Count, mean and spread of log(amount). Amounts are roughly log-normal."""
    logs = [math.log(max(a, 1.0)) for a in amounts]
    n = len(logs)
    if n == 0:
        return {'n': 0, 'log_mean': 0.0, 'log_std': 0.0}
    mean = sum(logs) / n
    var = sum((x - mean) ** 2 for x in logs) / n
    return {'n': n, 'log_mean': mean, 'log_std': math.sqrt(var)}


def build_customer_profile(customer_id, before_txn_id=None):
    """
    Build a summary using all available data or only transactions
    from strictly earlier PaySim simulation steps.

    before_txn_id identifies the transaction whose step is used
    as the cutoff. Transactions at the same step are excluded.

    The original keys (num_transactions, average_amount, max_amount, past_flags)
    are unchanged. Extra keys used by the utility-based agent:
      type_counts       how many past transactions of each type
      amount_stats      per type (and ALL): count, mean and std of log(amount)
      unresolved_flags  earlier transactions still blocked or waiting for review
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

        rows_query = "SELECT type, amount FROM transactions WHERE customer_id = ?"
        rows_params = [customer_id]
        unresolved_query = (
            "SELECT COUNT(*) FROM transactions WHERE customer_id = ? "
            "AND status IN ('block', 'escalate')"
        )
        unresolved_params = [customer_id]
        if cutoff_step is not None:
            rows_query += " AND step < ?"
            rows_params.append(cutoff_step)
            unresolved_query += " AND step < ?"
            unresolved_params.append(cutoff_step)

        by_type = {}
        all_amounts = []
        for r in conn.execute(rows_query, rows_params):
            by_type.setdefault(r["type"], []).append(r["amount"])
            all_amounts.append(r["amount"])
        unresolved = conn.execute(unresolved_query, unresolved_params).fetchone()[0]

        amount_stats = {t: _stats(a) for t, a in by_type.items()}
        amount_stats["ALL"] = _stats(all_amounts)

        return {
            "customer_id": customer_id,
            "num_transactions": row["n"],
            "average_amount": row["avg_amount"] or 0.0,
            "max_amount": row["max_amount"] or 0.0,
            "past_flags": flags,
            "type_counts": {t: len(a) for t, a in by_type.items()},
            "amount_stats": amount_stats,
            "unresolved_flags": unresolved,
        }
    finally:
        conn.close()