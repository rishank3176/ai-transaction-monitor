"""
Utility-based agent for transaction monitoring and decision making.

Combines the ML anomaly model's fraud probability with the customer's transaction
history. The history changes both the fraud probability and the utility values
(see agent/behaviour.py), and the agent then chooses the action with the highest
expected utility.
"""

from data.profile import build_customer_profile
from agent.utility import choose_action, load_utility
from agent.behaviour import (
    BLOCK_MIN_MODEL_P,
    adjust_utility,
    apply_risk_shift,
    assess_behaviour,
    neutral_behaviour,
)


class UtilityAgent:
    """
    Perceives a transaction and the model output, updates its state from the
    customer's history, adjusts risk and utilities, and picks the action with
    the maximum expected utility.
    """

    def __init__(self):
        self.txn = None
        self.score_result = None
        self.profile = None
        self.adjustments = []
        self.behaviour = None
        self.p_model = 0.0
        self.base_utility = None
        self.utility = None
        self.guard_note = None

    def perceive(self, txn, score_result):
        """
        Store the current transaction and anomaly model output.
        """
        self.txn = txn
        self.score_result = score_result
        self.profile = None
        self.adjustments = []
        self.behaviour = None
        self.guard_note = None

    def update_state(self, profile=None):
        """
        Accept an explicitly supplied customer profile for testing,
        or retrieve historical profile using build_customer_profile(before_txn_id=...).
        """
        if profile is not None:
            self.profile = profile
        else:
            cust_id = self.txn.get('customer_id') if isinstance(self.txn, dict) else None
            txn_id = self.txn.get('transaction_id') if isinstance(self.txn, dict) else None
            try:
                self.profile = build_customer_profile(cust_id, before_txn_id=txn_id)
            except Exception:
                self.profile = {
                    'customer_id': cust_id,
                    'num_transactions': 0,
                    'average_amount': 0.0,
                    'max_amount': 0.0,
                    'past_flags': 0
                }

    def estimate_p_fraud(self):
        """
        Start from the model's fraud probability and update it with the customer's
        behaviour: unusual amount or type raises it, typical behaviour of a trusted
        customer lowers it slightly. Also stores the behaviour assessment that
        choose_action() uses to personalise the utilities.
        """
        self.p_model = max(0.0, min(1.0, float(self.score_result.get('p_fraud', 0.0) or 0.0)))
        if isinstance(self.txn, dict) and self.profile:
            self.behaviour = assess_behaviour(self.txn, self.profile)
        else:
            self.behaviour = neutral_behaviour()
        self.adjustments = list(self.behaviour['notes'])
        p = apply_risk_shift(self.p_model, self.behaviour['risk_shift'])
        p = max(p, self.behaviour['risk_floor'])
        return max(0.0, min(1.0, p))

    def choose_action(self, p):
        """
        Maximum expected utility using the customer-specific utility table.
        A block must be supported by the ML model: unusual behaviour alone
        can raise a transaction to hold or escalate, but not to block.
        """
        if self.behaviour is None:
            self.behaviour = neutral_behaviour()
        self.base_utility = load_utility()
        self.utility = adjust_utility(self.base_utility, self.behaviour)
        action, eu, gap = choose_action(p, self.utility)
        self.guard_note = None

        if action == 'block' and self.p_model < BLOCK_MIN_MODEL_P:
            ranked = sorted(((a, v) for a, v in eu.items() if a != 'block'),
                            key=lambda item: item[1], reverse=True)
            action = ranked[0][0]
            gap = ranked[0][1] - ranked[1][1] if len(ranked) > 1 else 0.0
            self.guard_note = ('block not applied: the model risk is low and unusual '
                               'behaviour alone cannot justify blocking')
        return action, eu, gap

    def decide(self, txn, score_result, profile=None):
        """
        Run the complete decision pipeline:
        1. Perceive transaction and model score.
        2. Update the customer-history state.
        3. Update the fraud probability and the utilities from that history.
        4. Choose the action with the highest expected utility.
        5. Confidence = 0.5 + 0.5 * min(1.0, utility_gap / 30).
        6. Also work out what the decision would have been without history.
        """
        self.perceive(txn, score_result)
        self.update_state(profile)
        p_adj = self.estimate_p_fraud()
        best_action, eu, utility_gap = self.choose_action(p_adj)

        base_action, base_eu, _ = choose_action(self.p_model, self.base_utility)

        confidence = 0.5 + 0.5 * min(1.0, utility_gap / 30.0)

        model_reasons = self.score_result.get('top_reasons', []) if isinstance(self.score_result, dict) else []
        history_reasons = list(self.adjustments)
        if self.guard_note:
            history_reasons.append(self.guard_note)
        all_reasons = list(model_reasons) + history_reasons
        reasons_str = "; ".join(all_reasons) if all_reasons else "standard evaluation"

        reasoning = (
            f"Action '{best_action}' selected based on expected utility with adjusted "
            f"p_fraud={p_adj:.3f} (model {self.p_model:.3f}). Reasons: {reasons_str}."
        )

        txn_id = txn.get('transaction_id') if isinstance(txn, dict) else None

        return {
            'transaction_id': txn_id,
            'decision': best_action,
            'confidence': round(confidence, 3),
            'p_fraud': round(p_adj, 3),
            'expected_utilities': {k: round(v, 1) for k, v in eu.items()},
            'reasoning': reasoning,
            'p_model': round(self.p_model, 3),
            'decision_without_history': base_action,
            'baseline_expected_utilities': {k: round(v, 1) for k, v in base_eu.items()},
            'behaviour': self.behaviour,
        }


_agent_instance = UtilityAgent()


def decide(txn, score_result, profile=None):
    """
    Public entry point for utility-based decision making.
    Preserves contract expected by backend and dashboard.
    """
    return _agent_instance.decide(txn, score_result, profile=profile)