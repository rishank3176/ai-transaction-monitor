"""Streamlit dashboard for AI Transaction Monitor."""

import requests
import streamlit as st

st.set_page_config(
    page_title="AI Transaction Monitor",
    layout="wide",
)

st.title("AI Transaction Monitor")
st.caption(
    "Academic prototype using synthetic PaySim data. "
    "Not for real payment decisions."
)

api_url = st.sidebar.text_input(
    "FastAPI base URL",
    "http://127.0.0.1:8000",
).rstrip("/")

# Check whether the API is available.
try:
    health_response = requests.get(f"{api_url}/health", timeout=5)
    health_response.raise_for_status()
    st.sidebar.success("API connected")
except requests.RequestException as exc:
    st.sidebar.error("API unavailable. Start FastAPI in another terminal.")
    st.error(f"Could not connect to {api_url}. Details: {exc}")
    st.stop()

# Load transactions from the API.
try:
    list_response = requests.get(
        f"{api_url}/transactions?limit=100",
        timeout=10,
    )
    list_response.raise_for_status()
    transactions = list_response.json()["items"]
except requests.RequestException as exc:
    st.error(f"Could not load transactions: {exc}")
    st.stop()

if not transactions:
    st.warning("No transactions are available. Build the database first.")
    st.stop()

transaction_by_id = {
    int(row["transaction_id"]): row
    for row in transactions
}

selected_id = st.selectbox(
    "Choose a transaction",
    list(transaction_by_id.keys()),
)

st.dataframe(
    [transaction_by_id[selected_id]],
    use_container_width=True,
    hide_index=True,
)

# Process the selected transaction.
if st.button("Process transaction", type="primary"):
    try:
        response = requests.post(
            f"{api_url}/process/{selected_id}",
            timeout=30,
        )
        response.raise_for_status()
        st.session_state["last_result"] = response.json()
    except requests.RequestException as exc:
        st.error(f"Processing failed: {exc}")

# Display the processing result.
result = st.session_state.get("last_result")

if result and int(result["transaction"]["transaction_id"]) == int(selected_id):
    st.subheader("Decision result")

    score = result["score"]
    decision = result["decision"]

    left, middle, right = st.columns(3)

    left.metric("Demo fraud score", f"{score['p_fraud']:.1%}")
    middle.metric(
        "Anomaly review flag",
        "Yes" if score["is_anomaly"] else "No",
    )
    right.metric("Decision", decision["decision"].upper())

    st.caption(
        "The model score is not calibrated to real-world fraud prevalence."
    )

    st.markdown("**Review indicators**")
    for reason in score["top_reasons"]:
        st.write(f"- {reason}")

    st.markdown("**Decision reasoning**")
    st.write(decision["reasoning"])

    st.markdown("**Illustrative expected utilities**")
    st.dataframe(
        [
            {"decision": key, "expected_utility": value}
            for key, value in decision["expected_utilities"].items()
        ],
        use_container_width=True,
        hide_index=True,
    )

    with st.expander("Customer profile memory"):
        st.json(result["customer_profile"])

    with st.expander("Evaluation label (ground truth, demo only)"):
        st.write(result["evaluation_only"]["ground_truth_is_fraud"])
        st.caption(
            "This label is shown only after processing and is never a model input."
        )

    st.markdown("**Human review feedback**")
    human_decision = st.radio(
        "What should the final decision be?",
        ["approve", "hold", "block", "escalate"],
        horizontal=True,
    )

    if st.button("Save feedback"):
        try:
            response = requests.post(
                f"{api_url}/feedback/{selected_id}",
                json={"human_decision": human_decision},
                timeout=10,
            )
            response.raise_for_status()
            st.success(
                "Feedback saved for later analysis. The model was not retrained."
            )
        except requests.RequestException as exc:
            st.error(f"Feedback could not be saved: {exc}")
