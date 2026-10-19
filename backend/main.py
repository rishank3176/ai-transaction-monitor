import sqlite3
from typing import Literal
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from data.db import DB_PATH, update_status
from backend.pipeline import process_transaction

app = FastAPI(title='AI Transaction Monitor')


def query(sql, params=()):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    conn.close()
    return rows


@app.post('/process/{txn_id}')
def process(txn_id: int):
    result = process_transaction(txn_id)
    if result is None:
        raise HTTPException(404, 'Transaction not found')
    return result


class NewTransaction(BaseModel):
    customer_id: int = Field(ge=1)
    type: Literal['TRANSFER', 'CASH_OUT', 'PAYMENT']
    amount: float = Field(gt=0)
    old_balance: float = Field(ge=0)
    new_balance: float = Field(ge=0)


@app.post('/submit')
def submit(tx: NewTransaction):
    # Save a brand-new transaction, then run it through the same pipeline
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute('SELECT COALESCE(MAX(transaction_id), 0) FROM transactions').fetchone()
    new_id = row[0] + 1
    conn.execute(
        '''INSERT INTO transactions
           (transaction_id, customer_id, step, type, amount,
            old_balance, new_balance, is_fraud, status)
           VALUES (?, ?, 0, ?, ?, ?, ?, 0, 'pending')''',
        (new_id, tx.customer_id, tx.type, tx.amount, tx.old_balance, tx.new_balance))
    conn.commit()
    conn.close()
    result = process_transaction(new_id)
    return result


@app.get('/transactions')
def transactions(status: str = None, limit: int = 50):
    if status:
        return query(
            'SELECT * FROM transactions WHERE status = ? ORDER BY transaction_id LIMIT ?',
            (status, limit))
    return query('SELECT * FROM transactions ORDER BY transaction_id LIMIT ?', (limit,))


@app.get('/alerts')
def alerts():
    return query('''SELECT * FROM transactions
                    WHERE status IN ('hold', 'block', 'escalate')
                    ORDER BY transaction_id DESC''')


@app.get('/review-queue')
def review_queue():
    return query(
        'SELECT * FROM transactions WHERE status = ? ORDER BY transaction_id', ('escalate',))


@app.get('/actions')
def actions(limit: int = 200):
    return query('SELECT * FROM actions_log ORDER BY id DESC LIMIT ?', (limit,))


class Feedback(BaseModel):
    transaction_id: int
    human_decision: str      # approve or block


@app.post('/feedback')
def feedback(fb: Feedback):
    if fb.human_decision not in ('approve', 'block'):
        raise HTTPException(400, 'human_decision must be approve or block')
    last = query(
        'SELECT decision FROM actions_log WHERE transaction_id = ? ORDER BY id DESC LIMIT 1',
        (fb.transaction_id,))
    agent_decision = last[0]['decision'] if last else 'unknown'
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        'INSERT INTO feedback (transaction_id, agent_decision, human_decision) VALUES (?, ?, ?)',
        (fb.transaction_id, agent_decision, fb.human_decision))
    conn.execute(
        '''INSERT INTO actions_log (transaction_id, decision, confidence, reasoning, decided_by)
           VALUES (?, ?, 1.0, 'Human reviewer decision', 'human')''',
        (fb.transaction_id, fb.human_decision))
    conn.commit()
    conn.close()
    update_status(fb.transaction_id, fb.human_decision)
    return {'ok': True}