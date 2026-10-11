import joblib
import numpy as np
import pandas as pd
from model.features import make_features

_bundle = None


def _load():
    global _bundle
    if _bundle is None:
        _bundle = joblib.load("model/model.joblib")
    return _bundle


def score_transaction(txn):
    b = _load()
    X = make_features(pd.DataFrame([txn]))
    raw = -b["iso"].score_samples(X)[0]
    score = float(min(max((raw - b["lo"]) / (b["hi"] - b["lo"]), 0), 1))

    cx = np.array([[score,
                    X["drained"].iloc[0],
                    min(X["amount_ratio"].iloc[0], 2),
                    X["type_TRANSFER"].iloc[0],
                    X["type_CASH_OUT"].iloc[0]]])
    p_fraud = float(b["calibrator"].predict_proba(cx)[0][1])

    reasons = []
    if txn["old_balance"] > 0 and txn["new_balance"] == 0:
        reasons.append("account balance fully drained")
    if txn["amount"] / (txn["old_balance"] + 1) > 0.9:
        reasons.append("amount is almost the entire balance")
    if txn["type"] in ("TRANSFER", "CASH_OUT"):
        reasons.append(f"high-risk transaction type: {txn['type']}")
    if not reasons:
        reasons.append("unusual combination of features")

    return {"score": score, "p_fraud": p_fraud,
            "is_anomaly": bool(score > b["threshold"] or p_fraud > 0.3), "top_reasons": reasons}