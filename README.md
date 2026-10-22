# SentinelAI

A utility-based intelligent agent for fraud detection and automated response
in financial transactions.

Pipeline: transaction -> anomaly model (Isolation Forest + logistic regression)
-> utility-based agent -> response engine with guardrails -> human review and learning.

Dataset: PaySim (Lopez-Rojas, Elmir and Axelsson, 2016), synthetic data.

Run: uvicorn backend.main:app --reload
     streamlit run frontend/app.py
