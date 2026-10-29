"""
Customer portal: login, make transactions, see your own history.

Streamlit shows this page in the sidebar of the existing dashboard
(run: streamlit run frontend/app.py). It only talks to the FastAPI backend.
"""

import pandas as pd
import requests
import streamlit as st

API = 'http://127.0.0.1:8000'

st.set_page_config(page_title='SentinelAI Customer Portal', page_icon='🏦', layout='wide')
st.title('🏦 Customer Portal')

MESSAGES = {
    'approve': ('success', 'Your transaction was approved.'),
    'hold': ('warning', 'Your transaction is on hold for a quick security check.'),
    'escalate': ('warning', 'Your transaction is being reviewed by our team.'),
    'block': ('error', 'Your transaction was blocked to protect your account.'),
}


def call(method, path, body=None):
    headers = {}
    if st.session_state.get('token'):
        headers['Authorization'] = 'Bearer ' + st.session_state['token']
    try:
        resp = requests.request(method, API + path, json=body, headers=headers, timeout=60)
    except requests.RequestException as exc:
        st.error(f'Cannot reach the API. Start it first (uvicorn backend.main:app --reload). {exc}')
        return None
    if resp.status_code != 200:
        try:
            detail = resp.json().get('detail', resp.text)
        except ValueError:
            detail = resp.text
        if isinstance(detail, list):                  
            detail = '; '.join(str(d.get('msg', d)) for d in detail)
        if resp.status_code == 401 and st.session_state.get('token'):
            for key in ('token', 'username', 'last_result'):
                st.session_state.pop(key, None)
            st.warning('Your session has ended. Please log in again.')
            st.rerun()
        st.error(str(detail))
        return None
    return resp.json()


if not st.session_state.get('token'):
    st.info('Demo accounts: **demo1**, **demo2**, **demo3** (password **demo1234**). '
            'They are linked to PaySim customers with a long transaction history. '
            'Or create a new account and build a history from scratch.')
    tab_login, tab_register = st.tabs(['Log in', 'Create account'])
    with tab_login:
        with st.form('login'):
            u = st.text_input('Username')
            p = st.text_input('Password', type='password')
            go = st.form_submit_button('Log in', type='primary')
        if go:
            data = call('POST', '/auth/login', {'username': u, 'password': p})
            if data:
                st.session_state['token'] = data['token']
                st.session_state['username'] = data['username']
                st.rerun()
    with tab_register:
        st.caption('New accounts start with a balance of 1,000,000 and no history.')
        with st.form('register'):
            u2 = st.text_input('Choose a username (3 to 30 letters, digits, _ or .)')
            p2 = st.text_input('Choose a password (8 or more characters)', type='password')
            go2 = st.form_submit_button('Create account')
        if go2:
            data = call('POST', '/auth/register', {'username': u2, 'password': p2})
            if data:
                st.success(f'Account created (customer ID {data["customer_id"]}). '
                           'Now log in from the other tab.')
    st.stop()

me = call('GET', '/customer/me')
if me is None:
    st.stop()

st.sidebar.write(f'Logged in as **{me["username"]}**')
st.sidebar.write(f'Customer ID: {me["customer_id"]}')
if st.sidebar.button('Log out'):
    call('POST', '/auth/logout')
    for key in ('token', 'username', 'last_result'):
        st.session_state.pop(key, None)
    st.rerun()

st.subheader('Your account')
c1, c2, c3 = st.columns(3)
c1.metric('Available balance', f'{me["available_balance"]:,.0f}')
c2.metric('Transactions on record', me['num_transactions'])
c3.metric('Flagged transactions', me['flagged_transactions'])

st.subheader('What the agent knows about you')
st.caption('The utility-based agent compares every new transaction with this history.')
if me['by_type']:
    st.dataframe(pd.DataFrame(me['by_type']).rename(columns={
        'type': 'Type', 'count': 'Transactions', 'average_amount': 'Average amount'}),
        use_container_width=True, hide_index=True)
else:
    st.write('No history yet. Your first transactions will be judged mainly by the ML model.')

st.subheader('Make a transaction')
with st.form('send'):
    f1, f2 = st.columns(2)
    ttype = f1.selectbox('Type', ['PAYMENT', 'TRANSFER', 'CASH_OUT'])
    amount = f2.number_input('Amount', min_value=1.0, value=500.0, step=100.0)
    send = st.form_submit_button('Send', type='primary')
if send:
    res = call('POST', '/customer/transaction', {'type': ttype, 'amount': float(amount)})
    if res:
        st.session_state['last_result'] = res
        st.rerun()

res = st.session_state.get('last_result')
if res:
    kind, text = MESSAGES[res['decision']]
    getattr(st, kind)(f'Transaction #{res["transaction_id"]}: {text}')
    with st.expander('How your history influenced this decision (demo view)', expanded=True):
        b = res.get('behaviour', {})
        m1, m2, m3, m4 = st.columns(4)
        m1.metric('Model risk', f'{res["p_model"]:.1%}')
        m2.metric('Risk after your history', f'{res["p_fraud"]:.1%}')
        m3.metric('Decision without history', res['decision_without_history'].upper())
        m4.metric('Final decision', res['decision'].upper())
        f1, f2, f3 = st.columns(3)
        f1.metric('How unusual for you', f'{b.get("unusualness", 0):.0%}')
        f2.metric('Loss factor (amount at stake)', f'{b.get("loss_factor", 1):.2f}')
        f3.metric('Convenience factor (cost of interrupting you)', f'{b.get("friction_factor", 1):.2f}')
        for note in b.get('notes', []):
            st.write('• ' + note)
        st.write(res['reasoning'])
        st.markdown('**Expected utility of each action**')
        st.bar_chart(pd.DataFrame({
            'without history': res['baseline_expected_utilities'],
            'with your history': res['expected_utilities'],
        }))

st.subheader('Your transactions')
rows = call('GET', '/customer/history') or []
if rows:
    table = pd.DataFrame(rows)
    table['source'] = table['source'].map({'portal': 'Portal'}).fillna('Historical')
    table['fraud_probability'] = table['fraud_probability'].map(
        lambda v: '' if pd.isna(v) else f'{v:.1%}')
    table = table[['transaction_id', 'type', 'amount', 'status', 'fraud_probability',
                   'source', 'decided_by', 'reasoning']]
    st.dataframe(table.rename(columns={
        'transaction_id': 'ID', 'type': 'Type', 'amount': 'Amount', 'status': 'Final decision',
        'fraud_probability': 'Risk', 'source': 'Origin', 'decided_by': 'Decided by',
        'reasoning': 'Agent reasoning'}), use_container_width=True, hide_index=True)
else:
    st.info('No transactions yet.')