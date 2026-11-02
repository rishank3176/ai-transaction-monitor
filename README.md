# SentinelAI

Academic prototype that scores synthetic payment transactions for fraud, chooses an action with a history-aware utility agent, and shows the result in a dashboard and a customer portal.

This is not for real payment decisions. Scores are experimental and are not calibrated to real-world fraud rates. Ground-truth labels are for evaluation only and are not model inputs. Demo passwords are for local testing only.

## What it does

1. An isolation forest plus a calibrator scores each transaction (`model/`).
2. The utility agent compares the transaction with that customer's history and picks `approve`, `hold`, `escalate`, or `block` (`agent/`, `agent/behaviour.py`). A customer with no history is scored the same way as before the history adjustment.
3. Guardrails can turn a low-confidence or very large block into `escalate` (`backend/responder.py`).
4. FastAPI stores the decision. Streamlit has two pages:
   - **SentinelAI** — analyst dashboard for any transaction, the review queue, alerts, and feedback.
   - **Customer Portal** — login, send a payment, transfer, or cash-out, and see only that customer's history.

## Requirements

- Python 3.11
- The committed model at `model/model.joblib`
- A local SQLite database at `data/transactions.db` (not committed; see below)

## Setup

From the project root:

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

### Database

`data/transactions.db` is gitignored. If you already have it, skip the PaySim build.

Otherwise, download the PaySim dataset and save it as `data/raw/paysim.csv`. The builder expects `step`, `type`, `amount`, `oldbalanceOrg`, `newbalanceOrig`, and `isFraud`. Then:

```bash
./venv/bin/python data/build_db.py
```

That samples up to 400 fraud rows and 30,000 normal `TRANSFER`, `CASH_OUT`, and `PAYMENT` rows and creates `transactions`, `actions_log`, and `feedback`.

The API creates `users` and `sessions` on startup and adds score columns to `transactions` when the database is present. It also creates three demo accounts linked to the PaySim customers with the most history:

| Username | Password |
| --- | --- |
| `demo1` | `demo1234` |
| `demo2` | `demo1234` |
| `demo3` | `demo1234` |

New registrations start with a balance of 1,000,000 and no history. Usernames are 3–30 characters (`a-z`, digits, `_`, `.`) and passwords must be at least 8 characters.

Retrain only if you rebuilt the database and want a new model:

```bash
./venv/bin/python model/train.py
```

## Run

Use two terminals, both in the project root.

API:

```bash
./venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Dashboard and customer portal:

```bash
./venv/bin/streamlit run frontend/app.py
```

Open [http://127.0.0.1:8501](http://127.0.0.1:8501). The customer portal is the **Customer Portal** page in the sidebar. API docs are at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). Stop either process with Ctrl+C.

The model file is loaded from `model/model.joblib` relative to the current working directory, so start the API from the project root.

## Dashboard

- **Analyze a transaction.** Use a preset or your own values, or pick one of the first 200 dataset rows, then process it.
- **Review & alerts.** Escalated transactions can be approved or blocked. Other alert statuses are listed in the table.
- **Activity & learning.** Charts show the audit log. **Update agent from feedback** rewrites `agent/utility_config.json` from saved feedback. It does not retrain the fraud model.

Human feedback on the analyst dashboard accepts `approve` or `block`.

## Customer portal

Log in as `demo1`, `demo2`, or `demo3`, or register a new account. Sending a transaction checks the available balance, stores it on that customer only, and runs the same agent. The result shows the model risk, the risk after history, and the decision with and without history.

Customer routes require `Authorization: Bearer <token>` from `POST /auth/login`. The customer id is taken from the session, not from the request body.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/submit` | Save a new transaction and process it |
| `POST` | `/process/{txn_id}` | Score and decide an existing transaction |
| `GET` | `/transactions` | List transactions (`status`, `limit`) |
| `GET` | `/alerts` | Transactions on hold, blocked, or escalated |
| `GET` | `/review-queue` | Escalated transactions |
| `GET` | `/actions` | Audit log |
| `POST` | `/feedback` | Save a human `approve` or `block` |
| `POST` | `/auth/register` | Create an account |
| `POST` | `/auth/login` | Return a session token |
| `POST` | `/auth/logout` | End the session |
| `GET` | `/customer/me` | Balance and history summary |
| `GET` | `/customer/history` | That customer's transactions |
| `POST` | `/customer/transaction` | Submit a `PAYMENT`, `TRANSFER`, or `CASH_OUT` |

`/submit` accepts `customer_id`, `type` (`TRANSFER`, `CASH_OUT`, or `PAYMENT`), `amount`, `old_balance`, and `new_balance`.

## Tests

Dashboard checks (pytest is not in `requirements.txt`):

```bash
./venv/bin/pip install pytest
./venv/bin/python -m pytest tests/test_dashboard.py -q
```

Scenario checks against the model and database:

```bash
PYTHONPATH=. ./venv/bin/python tests/run_tests.py
```

## Layout

| Path | Role |
| --- | --- |
| `frontend/app.py` | Analyst dashboard |
| `frontend/pages/1_Customer_Portal.py` | Customer login and transactions |
| `backend/` | FastAPI app, auth, pipeline, guardrails |
| `model/` | Features, training, scoring, saved model |
| `agent/` | Utility agent, history behaviour, optional learned utility table |
| `data/` | Database helpers, PaySim builder, customer accounts |
| `learning/feedback.py` | Updates utility values from human feedback |
| `tests/` | Dashboard checks and scenario script |
| `docs/` | Evaluation charts and the Person 5 report |

## Notes

- Analyst `/submit` rows are stored with `step` 0 and `is_fraud` 0. Portal transactions use the customer's balance and are marked with source `portal`.
- The dataset picker requests the first 200 transaction ids, not the newest submissions.
- The review screen only offers actions for escalated transactions.
- Do not commit `data/transactions.db`, `data/raw/paysim.csv`, `agent/utility_config.json`, or `venv/`.
