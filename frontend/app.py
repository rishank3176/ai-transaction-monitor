import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title='AI Transaction Monitor', page_icon='🛡️', layout='wide')

st.markdown('''
<style>
.block-container {padding-top: 2rem;}
[data-testid="stMetric"] {
    background: rgba(120, 120, 120, 0.08);
    padding: 12px 16px;
    border-radius: 10px;
}
</style>
''', unsafe_allow_html=True)

st.title('🛡️ AI Transaction Monitor')
st.caption('Anomaly detection, a utility-based agent and automated response. '
           'Academic prototype on synthetic PaySim data, not for real payments.')

api_url = st.sidebar.text_input('FastAPI base URL', 'http://127.0.0.1:8000').rstrip('/')


def api_get(path, **params):
    r = requests.get(api_url + path, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def api_post(path, body=None):
    r = requests.post(api_url + path, json=body, timeout=30)
    r.raise_for_status()
    return r.json()


try:
    api_get('/transactions', limit=1)
    st.sidebar.success('API connected')
except requests.RequestException as exc:
    st.sidebar.error('API unavailable. Start FastAPI in another terminal.')
    st.error(f'Could not connect to {api_url}. Details: {exc}')
    st.stop()

try:
    st.sidebar.metric('Waiting for human review', len(api_get('/review-queue')))
    st.sidebar.metric('Total alerts', len(api_get('/alerts')))
except requests.RequestException:
    pass
st.sidebar.markdown('---')
st.sidebar.caption('Statuses: pending, approve, hold, escalate, block')

STYLE = {
    'approve': ('✅', 'success'),
    'hold': ('⏸️', 'warning'),
    'escalate': ('🧑‍⚖️', 'warning'),
    'block': ('⛔', 'error'),
}

PRESETS = {
    'Normal payment': ('PAYMENT', 40.0, 5000.0, 4960.0),
    'Account drained (transfer)': ('TRANSFER', 90000.0, 90000.0, 0.0),
    'Large cash-out': ('CASH_OUT', 120000.0, 120000.0, 0.0),
    'Big transfer, balance left': ('TRANSFER', 900000.0, 5000000.0, 4100000.0),
}

st.session_state.setdefault('f_type', 'TRANSFER')
st.session_state.setdefault('f_amount', 90000.0)
st.session_state.setdefault('f_old', 90000.0)
st.session_state.setdefault('f_new', 0.0)


def load_preset(name):
    t, a, o, n = PRESETS[name]
    st.session_state.update(f_type=t, f_amount=a, f_old=o, f_new=n)


def show_result(res, key):
    icon, kind = STYLE[res['decision']]
    getattr(st, kind)(f'{icon}  Decision: {res["decision"].upper()}')

    c1, c2, c3, c4 = st.columns(4)
    c1.metric('Fraud probability', f'{res["p_fraud"]:.1%}')
    c2.metric('Anomaly score', f'{res["anomaly_score"]:.3f}')
    c3.metric('Confidence', f'{res["confidence"]:.0%}')
    c4.metric('Decided by', res['decided_by'])

    left, right = st.columns([3, 2])
    with left:
        st.markdown('**Why this decision**')
        st.write(res['reasoning'])
    with right:
        st.markdown('**Expected utility of each action**')
        st.bar_chart(pd.DataFrame({'expected utility': res['expected_utilities']}))

    st.markdown('**Was the agent right? Give feedback**')
    choice = st.radio('Your final decision', ['approve', 'block'],
                      horizontal=True, key=f'choice_{key}')
    if st.button('Save feedback', key=f'save_{key}'):
        try:
            api_post('/feedback', {'transaction_id': res['transaction_id'],
                                   'human_decision': choice})
            st.success('Feedback saved.')
        except requests.RequestException as exc:
            st.error(f'Feedback could not be saved: {exc}')


tab1, tab2, tab3 = st.tabs(['🔍 Analyze a transaction',
                            '🧑‍⚖️ Review & alerts',
                            '📊 Activity & learning'])

with tab1:
    mode = st.radio('Choose input', ['Enter your own transaction', 'Pick from dataset'],
                    horizontal=True)

    if mode == 'Enter your own transaction':
        st.markdown('**Quick examples**')
        cols = st.columns(len(PRESETS))
        for col, name in zip(cols, PRESETS):
            col.button(name, on_click=load_preset, args=(name,), key=f'preset_{name}')

        with st.form('new_txn'):
            c1, c2 = st.columns(2)
            cust = c1.number_input('Customer ID', min_value=1, value=1, step=1)
            c2.selectbox('Type', ['TRANSFER', 'CASH_OUT', 'PAYMENT'], key='f_type')
            c1.number_input('Amount', min_value=0.01, key='f_amount')
            c2.number_input('Balance before', min_value=0.0, key='f_old')
            c1.number_input('Balance after', min_value=0.0, key='f_new')
            submitted = st.form_submit_button('Process transaction', type='primary')

        if submitted:
            try:
                st.session_state['result'] = api_post('/submit', {
                    'customer_id': int(cust),
                    'type': st.session_state['f_type'],
                    'amount': float(st.session_state['f_amount']),
                    'old_balance': float(st.session_state['f_old']),
                    'new_balance': float(st.session_state['f_new']),
                })
            except requests.RequestException as exc:
                st.error(f'Could not process the transaction: {exc}')
    else:
        rows = api_get('/transactions', limit=200)
        by_id = {int(r['transaction_id']): r for r in rows}
        chosen = st.selectbox('Choose a transaction', list(by_id.keys()))
        st.dataframe([by_id[chosen]], use_container_width=True, hide_index=True)
        if st.button('Process transaction', type='primary'):
            try:
                st.session_state['result'] = api_post(f'/process/{chosen}')
            except requests.RequestException as exc:
                st.error(f'Processing failed: {exc}')

    result = st.session_state.get('result')
    if result:
        st.divider()
        show_result(result, key=result['transaction_id'])

with tab2:
    st.subheader('Waiting for a human decision')
    queue = api_get('/review-queue')
    if not queue:
        st.info('Nothing to review.')
    for t in queue[:20]:
        tid = t['transaction_id']
        c1, c2, c3 = st.columns([5, 1, 1])
        amount_text = format(t['amount'], ',.0f')
        c1.write(f'**#{tid}**  |  {t["type"]}  |  amount {amount_text}  |  '
                 f'customer {t["customer_id"]}')
        if c2.button('Approve', key=f'qa_{tid}'):
            api_post('/feedback', {'transaction_id': tid, 'human_decision': 'approve'})
            st.rerun()
        if c3.button('Block', key=f'qb_{tid}'):
            api_post('/feedback', {'transaction_id': tid, 'human_decision': 'block'})
            st.rerun()

    st.subheader('All alerts')
    alerts = pd.DataFrame(api_get('/alerts'))
    if alerts.empty:
        st.info('No alerts yet. Process some transactions first.')
    else:
        picked = st.multiselect('Filter by status', sorted(alerts['status'].unique()),
                                default=sorted(alerts['status'].unique()))
        st.dataframe(alerts[alerts['status'].isin(picked)],
                     use_container_width=True, hide_index=True)

with tab3:
    actions = pd.DataFrame(api_get('/actions'))
    if actions.empty:
        st.info('No actions logged yet.')
    else:
        a, b = st.columns(2)
        a.markdown('**Decisions made**')
        a.bar_chart(actions['decision'].value_counts())
        b.markdown('**Who decided**')
        b.bar_chart(actions['decided_by'].value_counts())
        st.markdown('**Audit log**')
        st.dataframe(actions, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader('Learning from human feedback')
    st.caption('Updates the agent\'s utility values using all feedback saved so far.')
    if st.button('Update agent from feedback', type='primary'):
        try:
            from learning.feedback import update_utilities
            table = update_utilities()
            st.success('Agent updated. New utility values:')
            st.dataframe(pd.DataFrame(table).T, use_container_width=True)
        except Exception as exc:
            st.error(f'Could not update the agent: {exc}')