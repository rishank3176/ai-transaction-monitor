from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "data" / "raw" / "paysim.csv"
DB_PATH = ROOT / "data" / "transactions.db"


def main():
    if not CSV_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found: {CSV_PATH}"
        )

    print("Loading PaySim dataset...")

    # Read only the columns required by our project.
    df = pd.read_csv(
        CSV_PATH,
        usecols=[
            "step",
            "type",
            "amount",
            "oldbalanceOrg",
            "newbalanceOrig",
            "isFraud",
        ],
    )

    print(f"Loaded {len(df):,} rows.")

    # Keep the transaction types selected for this project.
    df = df[
        df["type"].isin(["TRANSFER", "CASH_OUT", "PAYMENT"])
    ]

    # Sample up to 400 fraud cases and 30,000 normal cases.
    fraud_rows = df[df["isFraud"] == 1]
    normal_rows = df[df["isFraud"] == 0]

    fraud = fraud_rows.sample(
        n=min(400, len(fraud_rows)),
        random_state=42,
    )

    normal = normal_rows.sample(
        n=min(30000, len(normal_rows)),
        random_state=42,
    )

    df = pd.concat([fraud, normal], ignore_index=True)
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)

    # Synthetic customer IDs for this prototype.
    rng = np.random.default_rng(42)
    df["customer_id"] = rng.integers(
        1, 501, size=len(df)
    )

    df = df.rename(
        columns={
            "oldbalanceOrg": "old_balance",
            "newbalanceOrig": "new_balance",
            "isFraud": "is_fraud",
        }
    )

    df["transaction_id"] = np.arange(1, len(df) + 1)
    df["status"] = "pending"

    df = df[
        [
            "transaction_id",
            "customer_id",
            "step",
            "type",
            "amount",
            "old_balance",
            "new_balance",
            "is_fraud",
            "status",
        ]
    ]

    # Create the SQLite database and tables.
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        df.to_sql(
            "transactions",
            conn,
            if_exists="replace",
            index=False,
        )

        conn.execute("""
            CREATE TABLE IF NOT EXISTS actions_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id INTEGER,
                decision TEXT,
                confidence REAL,
                reasoning TEXT,
                decided_by TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id INTEGER,
                agent_decision TEXT,
                human_decision TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

    print(f"Database created: {DB_PATH}")
    print(f"Transactions saved: {len(df):,}")
    print(f"Fraud cases: {int(df['is_fraud'].sum()):,}")
    print("Database build complete!")


if __name__ == "__main__":
    main()
