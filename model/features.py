import pandas as pd
def make_features(df):
    out = pd.DataFrame(index=df.index)
    out["amount"] = df["amount"]
    out["old_balance"] = df["old_balance"]
    out["new_balance"] = df["new_balance"]
    out["amount_ratio"] = df["amount"] / (df["old_balance"] + 1)
    out["drained"] = ((df["new_balance"] == 0) & (df["old_balance"] > 0)).astype(int)
    for t in ["TRANSFER", "CASH_OUT", "PAYMENT"]:
        out["type_" + t] = (df["type"] == t).astype(int)
    return out