import sqlite3
from data.db import DB_PATH, update_status

# Status names follow data/db.py: pending, approve, hold, block, escalate
STATUS = {'approve': 'approve', 'hold': 'hold',
          'block': 'block', 'escalate': 'escalate'}
MIN_CONFIDENCE_TO_BLOCK = 0.7
MAX_AUTO_BLOCK_AMOUNT = 5000000


def apply_guardrails(decision):
    # Safety rules the agent cannot override
    d = dict(decision)
    d['decided_by'] = 'agent'
    if d['decision'] == 'block' and d['confidence'] < MIN_CONFIDENCE_TO_BLOCK:
        d['decision'] = 'escalate'
        d['decided_by'] = 'guardrail'
        d['reasoning'] += ' [Guardrail: low confidence, block sent to human review]'
    if d['decision'] == 'block' and d.get('amount', 0) > MAX_AUTO_BLOCK_AMOUNT:
        d['decision'] = 'escalate'
        d['decided_by'] = 'guardrail'
        d['reasoning'] += ' [Guardrail: very large amount, needs human approval]'
    return d


def log_action(d):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        '''INSERT INTO actions_log
           (transaction_id, decision, confidence, reasoning, decided_by)
           VALUES (?, ?, ?, ?, ?)''',
        (d['transaction_id'], d['decision'], d['confidence'],
         d['reasoning'], d['decided_by']))
    conn.commit()
    conn.close()


def send_alert(d):
    # Simple version: print. Optional upgrade: email (smtplib) or a Telegram webhook.
    tid = d['transaction_id']
    action = d['decision'].upper()
    reason = d['reasoning']
    print(f'[ALERT] Transaction {tid} -> {action} | {reason}')


def execute_action(decision):
    d = apply_guardrails(decision)
    update_status(d['transaction_id'], STATUS[d['decision']])
    log_action(d)
    if d['decision'] != 'approve':
        send_alert(d)
    return d