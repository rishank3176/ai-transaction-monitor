"""
Customer accounts, sessions and per-customer transaction storage.

Uses the existing SQLite database (data/transactions.db). It adds two tables
(users, sessions) and a few extra columns on the existing transactions table.
Nothing here is specific to FastAPI or Streamlit, so it can be tested directly.
"""

import hashlib
import hmac
import math
import re
import secrets
import sqlite3
import time

from data.db import DB_PATH

PBKDF2_ITERATIONS = 200_000
SESSION_SECONDS = 12 * 60 * 60
FIRST_NEW_CUSTOMER_ID = 1001         
NEW_ACCOUNT_BALANCE = 1_000_000.0
DEMO_BALANCE = 20_000_000.0           
DEMO_PASSWORD = 'demo1234'
DEMO_USERS = ['demo1', 'demo2', 'demo3']
USERNAME_RE = re.compile(r'^[a-z0-9_.]{3,30}$')
TRANSACTION_TYPES = ('PAYMENT', 'TRANSFER', 'CASH_OUT')
HELD_STATUSES = ('approve', 'hold', 'escalate', 'pending')   

EXTRA_COLUMNS = {
    'anomaly_score': 'REAL',
    'model_probability': 'REAL',
    'fraud_probability': 'REAL',
    'source': 'TEXT',
}


class InsufficientFunds(ValueError):
    pass


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema():
    """Create the account tables and add the extra columns. Safe to call many times."""
    conn = _connect()
    try:
        conn.execute('''CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            salt TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            customer_id INTEGER NOT NULL UNIQUE,
            opening_balance REAL NOT NULL,
            is_demo INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            expires_at REAL NOT NULL)''')
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'transactions' in tables:
            existing = {r[1] for r in conn.execute('PRAGMA table_info(transactions)')}
            for column, sql_type in EXTRA_COLUMNS.items():
                if column not in existing:
                    conn.execute(f'ALTER TABLE transactions ADD COLUMN {column} {sql_type}')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_txn_customer_step '
                         'ON transactions (customer_id, step)')
        conn.commit()
    finally:
        conn.close()



def _hash_password(password, salt_hex):
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'),
                               bytes.fromhex(salt_hex), PBKDF2_ITERATIONS).hex()


def _normalise_username(username):
    return (username or '').strip().lower()


def create_user(username, password, customer_id=None,
                opening_balance=NEW_ACCOUNT_BALANCE, is_demo=False):
    """Create an account. Passwords are stored only as salted PBKDF2 hashes."""
    ensure_schema()
    username = _normalise_username(username)
    if not USERNAME_RE.match(username):
        raise ValueError('Username must be 3 to 30 characters: letters, digits, _ or .')
    if len(password or '') < 8:
        raise ValueError('Password must be at least 8 characters')

    conn = _connect()
    try:
        if conn.execute('SELECT 1 FROM users WHERE username = ?', (username,)).fetchone():
            raise ValueError('Username already taken')
        if customer_id is None:
            top_user = conn.execute('SELECT MAX(customer_id) FROM users').fetchone()[0] or 0
            top_txn = conn.execute('SELECT MAX(customer_id) FROM transactions').fetchone()[0] or 0
            customer_id = max(top_user, top_txn, FIRST_NEW_CUSTOMER_ID - 1) + 1
        elif conn.execute('SELECT 1 FROM users WHERE customer_id = ?', (customer_id,)).fetchone():
            raise ValueError('That customer is already linked to an account')
        salt = secrets.token_hex(16)
        conn.execute(
            '''INSERT INTO users (username, salt, password_hash, customer_id,
                                  opening_balance, is_demo)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (username, salt, _hash_password(password, salt), customer_id,
             opening_balance, 1 if is_demo else 0))
        conn.commit()
        return {'username': username, 'customer_id': customer_id}
    finally:
        conn.close()


def authenticate(username, password):
    """Return the user dict if the credentials are right, otherwise None."""
    ensure_schema()
    username = _normalise_username(username)
    conn = _connect()
    try:
        row = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    finally:
        conn.close()
    if row is None:
        _hash_password(password or '', '00' * 16)      
        return None
    candidate = _hash_password(password or '', row['salt'])
    if not hmac.compare_digest(candidate, row['password_hash']):
        return None
    return {'username': row['username'], 'customer_id': row['customer_id'],
            'opening_balance': row['opening_balance']}



def _token_hash(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def create_session(username):
    ensure_schema()
    token = secrets.token_urlsafe(32)
    conn = _connect()
    try:
        conn.execute('DELETE FROM sessions WHERE expires_at < ?', (time.time(),))
        conn.execute('INSERT INTO sessions (token_hash, username, expires_at) VALUES (?, ?, ?)',
                     (_token_hash(token), username, time.time() + SESSION_SECONDS))
        conn.commit()
    finally:
        conn.close()
    return token


def user_from_token(token):
    """Return the logged-in user for a session token, or None."""
    if not token:
        return None
    ensure_schema()
    conn = _connect()
    try:
        row = conn.execute(
            '''SELECT u.username, u.customer_id, u.opening_balance
               FROM sessions s JOIN users u ON u.username = s.username
               WHERE s.token_hash = ? AND s.expires_at > ?''',
            (_token_hash(token), time.time())).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def delete_session(token):
    if not token:
        return
    ensure_schema()
    conn = _connect()
    try:
        conn.execute('DELETE FROM sessions WHERE token_hash = ?', (_token_hash(token),))
        conn.commit()
    finally:
        conn.close()



def seed_demo_users():
    """
    Link demo accounts to PaySim customers in a fixed, repeatable way: demo1 is the
    customer with the most transactions, demo2 the next, and so on (ties broken by
    customer ID). The customer IDs themselves are synthetic (see data/build_db.py).
    """
    ensure_schema()
    conn = _connect()
    try:
        rows = conn.execute(
            '''SELECT customer_id FROM transactions
               WHERE source IS NULL OR source != 'portal'
               GROUP BY customer_id
               ORDER BY COUNT(*) DESC, customer_id ASC LIMIT ?''',
            (len(DEMO_USERS),)).fetchall()
    finally:
        conn.close()
    created = []
    for username, row in zip(DEMO_USERS, rows):
        try:
            created.append(create_user(username, DEMO_PASSWORD,
                                       customer_id=row['customer_id'],
                                       opening_balance=DEMO_BALANCE, is_demo=True))
        except ValueError:
            pass           
    return created



def _available_balance(conn, customer_id, opening_balance):
    placeholders = ','.join('?' * len(HELD_STATUSES))
    committed = conn.execute(
        f'''SELECT COALESCE(SUM(amount), 0) FROM transactions
            WHERE customer_id = ? AND source = 'portal' AND status IN ({placeholders})''',
        (customer_id, *HELD_STATUSES)).fetchone()[0]
    return opening_balance - committed


def available_balance(customer_id, opening_balance):
    """Opening balance minus money that left (approved) or is frozen (hold, review)."""
    ensure_schema()
    conn = _connect()
    try:
        return _available_balance(conn, customer_id, opening_balance)
    finally:
        conn.close()


def submit_portal_transaction(user, txn_type, amount):
    """
    Store a new transaction for the logged-in customer and return its ID.
    The customer ID always comes from the session, never from the request.
    The transaction gets a step later than every existing one, so all of the
    customer's earlier transactions count as history for the agent.
    """
    ensure_schema()
    if txn_type not in TRANSACTION_TYPES:
        raise ValueError('Unknown transaction type')
    amount = round(float(amount), 2)
    if not math.isfinite(amount) or amount <= 0:
        raise ValueError('Amount must be greater than zero')

    conn = _connect()
    conn.isolation_level = None                      
    try:
        conn.execute('BEGIN IMMEDIATE')
        old_balance = _available_balance(conn, user['customer_id'], user['opening_balance'])
        if amount > old_balance:
            conn.execute('ROLLBACK')
            raise InsufficientFunds(f'Insufficient balance (available {old_balance:,.2f})')
        new_id = conn.execute(
            'SELECT COALESCE(MAX(transaction_id), 0) + 1 FROM transactions').fetchone()[0]
        new_step = conn.execute(
            'SELECT COALESCE(MAX(step), 0) + 1 FROM transactions').fetchone()[0]
        conn.execute(
            '''INSERT INTO transactions
               (transaction_id, customer_id, step, type, amount, old_balance,
                new_balance, is_fraud, status, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, 0, 'pending', 'portal')''',
            (new_id, user['customer_id'], new_step, txn_type, amount,
             old_balance, old_balance - amount))
        conn.execute('COMMIT')
        return new_id
    except InsufficientFunds:
        raise
    except Exception:
        try:
            conn.execute('ROLLBACK')
        except sqlite3.Error:
            pass
        raise
    finally:
        conn.close()


def save_risk(txn_id, anomaly_score, model_probability, fraud_probability):
    """Store the risk scores next to the transaction (the decision is its status)."""
    ensure_schema()
    conn = _connect()
    try:
        conn.execute(
            '''UPDATE transactions
               SET anomaly_score = ?, model_probability = ?, fraud_probability = ?
               WHERE transaction_id = ?''',
            (anomaly_score, model_probability, fraud_probability, txn_id))
        conn.commit()
    finally:
        conn.close()



def customer_history(customer_id, limit=100):
    """Transactions of ONE customer, newest first, with the stored risk and decision."""
    ensure_schema()
    conn = _connect()
    try:
        rows = conn.execute(
            '''SELECT t.transaction_id, t.step, t.type, t.amount, t.status, t.source,
                      t.anomaly_score, t.model_probability, t.fraud_probability,
                      (SELECT a.reasoning FROM actions_log a
                        WHERE a.transaction_id = t.transaction_id
                        ORDER BY a.id DESC LIMIT 1) AS reasoning,
                      (SELECT a.decided_by FROM actions_log a
                        WHERE a.transaction_id = t.transaction_id
                        ORDER BY a.id DESC LIMIT 1) AS decided_by
               FROM transactions t
               WHERE t.customer_id = ?
               ORDER BY t.step DESC, t.transaction_id DESC
               LIMIT ?''',
            (customer_id, limit)).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def customer_summary(user):
    """Account figures and what the agent knows about this customer."""
    ensure_schema()
    cid = user['customer_id']
    conn = _connect()
    try:
        n, avg, biggest = conn.execute(
            'SELECT COUNT(*), AVG(amount), MAX(amount) FROM transactions WHERE customer_id = ?',
            (cid,)).fetchone()
        flagged = conn.execute(
            '''SELECT COUNT(*) FROM transactions
               WHERE customer_id = ? AND status IN ('hold', 'block', 'escalate')''',
            (cid,)).fetchone()[0]
        by_type = [dict(r) for r in conn.execute(
            '''SELECT type, COUNT(*) AS count, AVG(amount) AS average_amount
               FROM transactions WHERE customer_id = ? GROUP BY type ORDER BY type''', (cid,))]
        balance = _available_balance(conn, cid, user['opening_balance'])
    finally:
        conn.close()
    return {'username': user['username'], 'customer_id': cid,
            'available_balance': balance, 'num_transactions': n,
            'average_amount': avg or 0.0, 'largest_amount': biggest or 0.0,
            'flagged_transactions': flagged, 'by_type': by_type}