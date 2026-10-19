
"""Streamlit dashboard for AI Transaction Monitor."""

import requests
import streamlit as st

st.set_page_config(page_title="AI Transaction Monitor", layout="wide")

st.title("AI Transaction Monitor")
st.caption(
    "Academic prototype using synthetic PaySim data. "
    "Not for real payment decisions."
)

api_url = st.sidebar.text_input(
    "FastAPI base URL", "http://127.0.0.1:8000"
).rstrip("/")

# Check the API using an endpoint that exists.
try:
    response = requests.get(f"{api_url}/transactions?limit=1", timeout=5)
    response.raise_for_status()
    st.sidebar.success("API connected")
except requests.RequestException as exc:
    st.sidebar.error("API unavailable. Start FastAPI in another terminal.")
    st.error(f"Could not connect to {api_url}. Details: {exc}")
    st.stop()

# Load transactions. The API returns a direct list.
try:
    response = requests.get(
        f"{api_url}/transactions?limit=100", timeout=10
    )
    response.raise_for_status()
    transactions = response.json()
except (requests.RequestException, ValueError) as exc:
    st.error(f"Could not load transactions: {exc}")
    st.stop()

if not transactions:
    st.warning("No transactions are available. Build the database first.")
    st.stop()

transaction_by_id = {
    int(row["transaction_id"]): row for row in transactions
}

selected_id = st.selectbox(
    "Choose a transaction", list(transaction_by_id.keys())
)

st.dataframe(
    [transaction_by_id[selected_id]],
    use_container_width=True,
    hide_index=True,
)

if st.button("Process transaction", type="primary"):
    try:
        response = requests.post(
            f"{api_url}/process/{selected_id}", timeout=30
        )
        response.raise_for_status()
        st.session_state["last_result"] = response.json()
        st.session_state["last_result_id"] = selected_id
    except requests.RequestException as exc:
        st.error(f"Processing failed: {exc}")

result = st.session_state.get("last_result")

if result and st.session_state.get("last_result_id") == selected_id:
    st.subheader("Decision result")

    left, middle, right = st.columns(3)
    left.metric("Demo fraud probability", f"{result['p_fraud']:.1%}")
    middle.metric("Anomaly score", f"{result['anomaly_score']:.3f}")
    right.metric("Decision", result["decision"].upper())

    st.caption(
        "Scores are experimental and are not calibrated to real-world "
        "fraud prevalence."
    )

    st.markdown("**Decision reasoning**")
    st.write(result["reasoning"])

    st.markdown("**Expected utilities**")
    st.dataframe(
        [
            {"decision": key, "expected_utility": value}
            for key, value in result["expected_utilities"].items()
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.write(f"**Decision confidence:** {result['confidence']:.1%}")
    st.write(f"**Decided by:** {result['decided_by']}")

    st.markdown("**Human review feedback**")
    human_decision = st.radio(
        "Final decision",
        ["approve", "block"],
        horizontal=True,
        key=f"feedback_{selected_id}",
    )

    if st.button("Save feedback", key=f"save_{selected_id}"):
        try:
            response = requests.post(
                f"{api_url}/feedback",
                json={
                    "transaction_id": selected_id,
                    "human_decision": human_decision,
                },
                timeout=10,
            )
            response.raise_for_status()
            st.success("Feedback saved. The model was not retrained.")
        except requests.RequestException as exc:
            st.error(f"Feedback could not be saved: {exc}")
st.divider()
st.subheader("Learning from human feedback")
if st.button("Update agent from feedback"):
    from learning.feedback import update_utilities
    st.json(update_utilities())
st.divider()
st.subheader("Try your own transaction")
st.caption(
    "Enter any transaction. Customer IDs 1 to 500 have history from the dataset. "
    "A new customer ID has no history."
)

with st.form("new_txn"):
    c1, c2 = st.columns(2)
    cust = c1.number_input("Customer ID", min_value=1, value=1, step=1)
    ttype = c2.selectbox("Type", ["TRANSFER", "CASH_OUT", "PAYMENT"])
    amount = c1.number_input("Amount", min_value=0.01, value=90000.0)
    old_b = c2.number_input("Balance before", min_value=0.0, value=90000.0)
    new_b = c1.number_input("Balance after", min_value=0.0, value=0.0)
    submitted = st.form_submit_button("Process new transaction")

if submitted:
    try:
        resp = requests.post(
            f"{api_url}/submit",
            json={
                "customer_id": int(cust),
                "type": ttype,
                "amount": float(amount),
                "old_balance": float(old_b),
                "new_balance": float(new_b),
            },
            timeout=30,
        )
        resp.raise_for_status()
        st.session_state["new_result"] = resp.json()
    except requests.RequestException as exc:
        st.error(f"Could not process the transaction: {exc}")

new_result = st.session_state.get("new_result")
if new_result:
    st.markdown("**Result for your transaction**")
    m1, m2, m3 = st.columns(3)
    m1.metric("Fraud probability", f"{new_result['p_fraud']:.1%}")
    m2.metric("Anomaly score", f"{new_result['anomaly_score']:.3f}")
    m3.metric("Decision", new_result["decision"].upper())
    st.write(new_result["reasoning"])
    st.write(f"**Confidence:** {new_result['confidence']:.1%}  |  "
             f"**Decided by:** {new_result['decided_by']}")
    st.dataframe(
        [{"action": k, "expected_utility": v}
         for k, v in new_result["expected_utilities"].items()],
        use_container_width=True,
        hide_index=True,
    )

    new_choice = st.radio(
        "Your final decision", ["approve", "block"], horizontal=True, key="new_choice"
    )
    if st.button("Save feedback for this transaction", key="new_feedback"):
        try:
            fb = requests.post(
                f"{api_url}/feedback",
                json={"transaction_id": new_result["transaction_id"],
                      "human_decision": new_choice},
                timeout=10,
            )
            fb.raise_for_status()
            st.success("Feedback saved.")
        except requests.RequestException as exc:
            st.error(f"Feedback could not be saved: {exc}")
