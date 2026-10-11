import sqlite3
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
from model.features import make_features

conn = sqlite3.connect("data/transactions.db")
df = pd.read_sql("SELECT * FROM transactions", conn)
conn.close()

X = make_features(df)
y = df["is_fraud"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.3, stratify=y, random_state=42)

iso = IsolationForest(n_estimators=200, random_state=42).fit(X_train)

raw_train = -iso.score_samples(X_train)
lo, hi = float(raw_train.min()), float(raw_train.max())

def to_score(raw):
    return np.clip((raw - lo) / (hi - lo), 0, 1)

score_train = to_score(raw_train)
score_test = to_score(-iso.score_samples(X_test))

def calib_X(feats, score):
    return np.column_stack([score, feats["drained"],
                            np.clip(feats["amount_ratio"], 0, 2),
                            feats["type_TRANSFER"], feats["type_CASH_OUT"]])

calibrator = LogisticRegression(max_iter=1000).fit(calib_X(X_train, score_train), y_train)
p_test = calibrator.predict_proba(calib_X(X_test, score_test))[:, 1]
print("Calibrated probability ROC AUC:", roc_auc_score(y_test, p_test))

threshold = float(np.percentile(score_train, 95))

pred = (score_test > threshold).astype(int)
print("Confusion matrix:")
print(confusion_matrix(y_test, pred))
print(classification_report(y_test, pred))
print("ROC AUC:", roc_auc_score(y_test, score_test))

joblib.dump({"iso": iso, "lo": lo, "hi": hi,
             "calibrator": calibrator, "threshold": threshold},
            "model/model.joblib")
print("Saved model/model.joblib")