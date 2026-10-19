import sqlite3
from data.db import DB_PATH
from model.anomaly import score_transaction
from agent.agent import decide

PROFILE = {'customer_id': 1, 'num_transactions': 30, 'average_amount': 5000.0,
           'max_amount': 20000.0, 'past_flags': 0}

# (name, transaction, what we expect)
CASES = [
    ('normal small payment',
     {'transaction_id': 1, 'customer_id': 1, 'type': 'PAYMENT', 'amount': 40.0,
      'old_balance': 5000.0, 'new_balance': 4960.0}, 'approve'),
    ('normal medium payment',
     {'transaction_id': 2, 'customer_id': 1, 'type': 'PAYMENT', 'amount': 800.0,
      'old_balance': 20000.0, 'new_balance': 19200.0}, 'approve'),
    ('drains whole account by transfer',
     {'transaction_id': 3, 'customer_id': 1, 'type': 'TRANSFER', 'amount': 90000.0,
      'old_balance': 90000.0, 'new_balance': 0.0}, 'block or escalate'),
    ('drains whole account by cash out',
     {'transaction_id': 4, 'customer_id': 1, 'type': 'CASH_OUT', 'amount': 120000.0,
      'old_balance': 120000.0, 'new_balance': 0.0}, 'block or escalate'),
    ('medium cash out, balance remains',
     {'transaction_id': 5, 'customer_id': 1, 'type': 'CASH_OUT', 'amount': 20000.0,
      'old_balance': 80000.0, 'new_balance': 60000.0}, 'approve or hold'),
    ('small transfer, large balance',
     {'transaction_id': 6, 'customer_id': 1, 'type': 'TRANSFER', 'amount': 300.0,
      'old_balance': 100000.0, 'new_balance': 99700.0}, 'approve'),
    ('tricky: tiny balance fully moved',
     {'transaction_id': 7, 'customer_id': 1, 'type': 'TRANSFER', 'amount': 50.0,
      'old_balance': 50.0, 'new_balance': 0.0}, 'any (tricky)'),
    ('tricky: huge amount, huge balance',
     {'transaction_id': 8, 'customer_id': 1, 'type': 'TRANSFER', 'amount': 900000.0,
      'old_balance': 5000000.0, 'new_balance': 4100000.0}, 'any (tricky)'),
]


def matches(expected, got):
    if expected.startswith('any'):
        return True
    return got in expected.split(' or ')


print('--- Hand-made cases ---')
passed = 0
for name, txn, expected in CASES:
    s = score_transaction(txn)
    d = decide(txn, s, PROFILE)
    ok = matches(expected, d['decision'])
    passed += ok
    mark = 'PASS' if ok else 'FAIL'
    print(mark, '|', name, '| expected:', expected, '| got:', d['decision'],
          '| p =', d['p_fraud'])
print('Passed', passed, 'of', len(CASES))

print()
print('--- 300 real transactions compared with the is_fraud label ---')
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
rows = [dict(r) for r in conn.execute(
    'SELECT * FROM transactions ORDER BY transaction_id LIMIT 300')]
conn.close()

caught = missed = false_alarm = ok_count = 0
fraud_total = 0
decisions = {'approve': 0, 'hold': 0, 'escalate': 0, 'block': 0}
for t in rows:
    d = decide(t, score_transaction(t))
    decisions[d['decision']] += 1
    flagged = d['decision'] != 'approve'
    if t['is_fraud']:
        fraud_total += 1
    if t['is_fraud'] and flagged:
        caught += 1
    elif t['is_fraud']:
        missed += 1
    elif flagged:
        false_alarm += 1
    else:
        ok_count += 1

print('Transactions tested:', len(rows), '| real fraud among them:', fraud_total)
print('Decisions made:', decisions)
print('Fraud caught (not approved):', caught)
print('Fraud missed (approved):', missed)
print('False alarms (genuine but flagged):', false_alarm)
print('Correctly approved:', ok_count)

print()
print('--- 40 known fraud rows ---')
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
fraud_rows = [dict(r) for r in conn.execute(
    'SELECT * FROM transactions WHERE is_fraud = 1 ORDER BY transaction_id LIMIT 40')]
conn.close()
flagged_count = 0
for t in fraud_rows:
    d = decide(t, score_transaction(t))
    if d['decision'] != 'approve':
        flagged_count += 1
print('Fraud rows flagged:', flagged_count, 'of', len(fraud_rows))