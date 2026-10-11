import sqlite3
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import confusion_matrix, roc_curve, roc_auc_score, ConfusionMatrixDisplay
from sklearn.model_selection import train_test_split
from model.features import make_features

b = joblib.load("model/model.joblib")
conn = sqlite3.connect("data/transactions.db")
df = pd.read_sql("SELECT * FROM transactions", conn)
conn.close()

X = make_features(df)
y = df["is_fraud"]
_, X_test, _, y_test = train_test_split(X, y, test_size=0.3, stratify=y, random_state=42)
score = np.clip((-b["iso"].score_samples(X_test) - b["lo"]) / (b["hi"] - b["lo"]), 0, 1)

pred = (score > b["threshold"]).astype(int)
ConfusionMatrixDisplay(confusion_matrix(y_test, pred)).plot()
plt.title("Confusion matrix")
plt.savefig("docs/confusion_matrix.png", dpi=150)
plt.close()

fpr, tpr, _ = roc_curve(y_test, score)
plt.plot(fpr, tpr, label=f"AUC = {roc_auc_score(y_test, score):.3f}")
plt.plot([0, 1], [0, 1], "--")
plt.xlabel("False positive rate")
plt.ylabel("True positive rate")
plt.legend()
plt.title("ROC curve")
plt.savefig("docs/roc_curve.png", dpi=150)
print("Saved charts to docs/")