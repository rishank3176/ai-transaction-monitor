"""
Utility-based agent for transaction monitoring and decision making.

Combines ML anomaly detection model scores with customer profile history to estimate
adjusted fraud probabilities and chooses optimal actions based on expected utility.
"""

from data.profile import build_customer_profile
from agent.utility import choose_action


class UtilityAgent:
    """
    UtilityAgent perceives transactions and anomaly model results,
    updates state from customer profile history, adjusts fraud probability,
    and decides on the best action via maximum expected utility.
    """

    def __init__(self):
        self.txn = None
        self.score_result = None
        self.profile = None
        self.adjustments = []

    def perceive(self, txn, score_result):
        """
        Store the current transaction and anomaly model output.
        """
        self.txn = txn
        self.score_result = score_result
        self.profile = None
        self.adjustments = []

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
        Start with model's p_fraud and adjust it using customer history.

        Rules:
        1. Calculate txn amount / average_amount (avoid div by zero if <= 0).
        2. If num_transactions >= 5 and amount > 10 * average: add 0.15.
        3. Else if amount > 5 * average: add 0.07.
        4. If past_flags >= 2: add 0.05.
        5. Store understandable explanations for every applied adjustment.
        6. Clamp final probability between 0.0 and 1.0.
        """
        raw_p = float(self.score_result.get('p_fraud', 0.0))
        p = raw_p
        self.adjustments = []

        if self.profile and isinstance(self.txn, dict):
            avg_amount = float(self.profile.get('average_amount', 0.0) or 0.0)
            num_txns = int(self.profile.get('num_transactions', 0) or 0)
            past_flags = int(self.profile.get('past_flags', 0) or 0)
            current_amount = float(self.txn.get('amount', 0.0) or 0.0)

            ratio = (current_amount / avg_amount) if avg_amount > 0 else 0.0

            if num_txns >= 5 and ratio > 10.0:
                p += 0.15
                self.adjustments.append(
                    f"amount is {ratio:.1f}x customer average with established history (+0.15)"
                )
            elif ratio > 5.0:
                p += 0.07
                self.adjustments.append(
                    f"amount is {ratio:.1f}x customer average (+0.07)"
                )

            if past_flags >= 2:
                p += 0.05
                self.adjustments.append(
                    f"customer has {past_flags} past flags (+0.05)"
                )

        p = max(0.0, min(1.0, p))
        return p

    def choose_action(self, p):
        """
        Use utility-based decision rule from agent.utility.
        """
        return choose_action(p)

    def decide(self, txn, score_result, profile=None):
        """
        Run complete decision pipeline:
        1. Perceive transaction and score.
        2. Update customer-history state.
        3. Estimate adjusted fraud probability.
        4. Choose action using maximum expected utility.
        5. Calculate confidence: 0.5 + 0.5 * min(1.0, utility_gap / 30).
        6. Combine model reasons with history explanations.
        7. Format reasoning and return required dictionary.
        """
        self.perceive(txn, score_result)
        self.update_state(profile)
        p_adj = self.estimate_p_fraud()
        best_action, eu, utility_gap = self.choose_action(p_adj)

        confidence = 0.5 + 0.5 * min(1.0, utility_gap / 30.0)

        model_reasons = self.score_result.get('top_reasons', []) if isinstance(self.score_result, dict) else []
        all_reasons = list(model_reasons) + list(self.adjustments)
        reasons_str = "; ".join(all_reasons) if all_reasons else "standard evaluation"

        reasoning = (
            f"Action '{best_action}' selected based on expected utility with adjusted "
            f"p_fraud={p_adj:.3f}. Reasons: {reasons_str}."
        )

        txn_id = txn.get('transaction_id') if isinstance(txn, dict) else None

        rounded_eu = {k: round(v, 1) for k, v in eu.items()}

        return {
            'transaction_id': txn_id,
            'decision': best_action,
            'confidence': round(confidence, 3),
            'p_fraud': round(p_adj, 3),
            'expected_utilities': rounded_eu,
            'reasoning': reasoning
        }


# Module-level agent instance
_agent_instance = UtilityAgent()


def decide(txn, score_result, profile=None):
    """
    Public entry point for utility-based decision making.
    Preserves contract expected by backend and dashboard.
    """
    return _agent_instance.decide(txn, score_result, profile=profile)
