# Person 5 Report — Dashboard, Human Feedback, Testing and Documentation

## 1. Responsibilities

Person 5 is responsible for the Streamlit dashboard, human feedback functionality, automated tests, and project documentation.

## 2. Dashboard

**File:** `frontend/app.py`

The dashboard is built using Streamlit and communicates with the FastAPI backend through HTTP requests.

Features implemented:
- Project title and synthetic-data disclaimer.
- Configurable FastAPI base URL.
- API health check.
- Transaction loading and selection.
- Transaction processing request.
- Display of the demo fraud score and anomaly flag.
- Display of the agent decision and reasoning.
- Expected utilities and customer profile.
- Evaluation-only ground-truth display after processing.
- Human review options: approve, hold, block, and escalate.

The dashboard expects the backend endpoints to be implemented and available before end-to-end testing.

## 3. Human Feedback

**File:** `learning/feedback.py`

The `save_feedback(txn_id, human_decision)` function is intended to:
- Validate the human decision against the permitted decisions.
- Check that the database exists.
- Find the latest agent decision for the transaction.
- Save the agent decision and human decision in the feedback table.
- Return a result confirming the saved feedback.

Human feedback is stored for later analysis. It does not automatically retrain the model.

**Current limitation:** Functional testing depends on the shared database implementation, which is not yet available in the current repository version.

## 4. Automated Testing

**File:** `tests/test_dashboard.py`

The dashboard tests check:
1. The dashboard file exists.
2. The project title is present.
3. Streamlit is imported.
4. HTTP requests are used instead of direct database access.
5. All four human feedback options are present.

Command used:

```bash
python -m pytest tests/test_dashboard.py -q
```

Result:

```text
5 passed
```

These are structural tests. They do not verify actual API processing, database writes, or end-to-end behavior.

## 5. Remaining Work

- Integrate with the completed FastAPI backend.
- Confirm that the shared database schema and database builder are implemented.
- Test transaction processing through the dashboard.
- Test saving human feedback to the database.
- Run the full test suite.
- Update the main README with setup and execution instructions.
- Perform an end-to-end demonstration with the team.

## 6. Safety and Limitations

This is an academic prototype using synthetic transaction data. It must not be used to make real payment decisions. The demo fraud score is not calibrated to real-world fraud prevalence. Ground-truth labels are for evaluation only and must not be used as model inputs.
