# AI Transaction Monitor

Academic prototype that scores synthetic payment transactions for fraud, chooses an action with a utility-based agent, and shows the result in a dashboard.

This is not for real payment decisions. Scores are experimental and are not calibrated to real-world fraud rates. Ground-truth labels are for evaluation only and are not model inputs.

## What it does

1. An isolation forest plus a calibrator scores each transaction (`model/`).
2. A utility-based agent adjusts that score with customer history and picks `approve`, `hold`, `escalate`, or `block` (`agent/`).
3. Guardrails can turn a low-confidence or very large block into `escalate` (`backend/responder.py`).
4. A FastAPI service stores the decision. A Streamlit dashboard lets you submit a transaction, pick one from the dataset, review escalations, and save human feedback.

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

`data/transactions.db` is gitignored. If you already have it, skip this section.

Otherwise, download the PaySim dataset and save it as `data/raw/paysim.csv`. The builder expects the columns `step`, `type`, `amount`, `oldbalanceOrg`, `newbalanceOrig`, and `isFraud`. Then:

```bash
./venv/bin/python data/build_db.py
```

That samples up to 400 fraud rows and 30,000 normal `TRANSFER`, `CASH_OUT`, and `PAYMENT` rows and creates `transactions`, `actions_log`, and `feedback`.

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

Dashboard:

```bash
./venv/bin/streamlit run frontend/app.py
```

Open [http://127.0.0.1:8501](http://127.0.0.1:8501). API docs are at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). Stop either process with Ctrl+C.

The model file is loaded from `model/model.joblib` relative to the current working directory, so start the API from the project root.

## Dashboard

- **Analyze a transaction.** Use a preset or your own values, or pick one of the first 200 dataset rows, then process it.
- **Review & alerts.** Escalated transactions can be approved or blocked. Other alert statuses are listed in the table.
- **Activity & learning.** Charts show the audit log. **Update agent from feedback** rewrites `agent/utility_config.json` from saved feedback. It does not retrain the fraud model.

Human feedback accepts `approve` or `block`.

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
| `frontend/app.py` | Streamlit dashboard |
| `backend/` | FastAPI app, pipeline, guardrails |
| `model/` | Features, training, scoring, saved model |
| `agent/` | Utility agent and optional learned utility table |
| `data/` | Database helpers, PaySim builder, customer profiles |
| `learning/feedback.py` | Updates utility values from human feedback |
| `tests/` | Dashboard checks and scenario script |
| `docs/` | Evaluation charts and the Person 5 report |

## Notes

- Typed-in transactions are stored with `step` 0 and `is_fraud` 0, so customer-history adjustments do not apply to them.
- The dataset picker requests the first 200 transaction ids, not the newest submissions.
- The review screen only offers actions for escalated transactions.
- Do not commit `data/transactions.db`, `data/raw/paysim.csv`, or `venv/`.
