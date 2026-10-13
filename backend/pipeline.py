from data.db import get_transaction
from model.anomaly import score_transaction
from agent.agent import decide
from backend.responder import execute_action


def process_transaction(txn_id):
    txn = get_transaction(txn_id)
    if txn is None:
        return None
    score_result = score_transaction(txn)
    decision = decide(txn, score_result)
    decision['amount'] = txn['amount']
    final = execute_action(decision)
    final['anomaly_score'] = score_result['score']
    return final