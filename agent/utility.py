"""
Utility-based decision making for transaction fraud management.

Computes expected utilities across possible actions (approve, hold, escalate, block)
and selects optimal actions based on calibrated fraud probability.
"""

import json
from pathlib import Path

DEFAULT_UTILITY = {
    'approve': {'fraud': -100, 'legit': 5},
    'hold': {'fraud': 30, 'legit': -8},
    'escalate': {'fraud': 55, 'legit': -15},
    'block': {'fraud': 80, 'legit': -50}
}

CONFIG_PATH = Path(__file__).resolve().parent / "utility_config.json"


def _validate_utility(table):
    """
    Validate that table contains required actions and numerical fraud/legit outcomes.
    """
    if not isinstance(table, dict):
        return False
    required_actions = {'approve', 'hold', 'escalate', 'block'}
    if not required_actions.issubset(table.keys()):
        return False
    for action in required_actions:
        outcomes = table.get(action)
        if not isinstance(outcomes, dict):
            return False
        if 'fraud' not in outcomes or 'legit' not in outcomes:
            return False
        if not isinstance(outcomes['fraud'], (int, float)) or not isinstance(outcomes['legit'], (int, float)):
            return False
    return True


def load_utility():
    """
    Load utility table from agent/utility_config.json if it exists and is valid.
    Otherwise, returns DEFAULT_UTILITY.
    Does not modify or create the configuration file automatically.
    """
    if CONFIG_PATH.is_file():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if _validate_utility(data):
                return data
        except Exception:
            pass
    return {k: dict(v) for k, v in DEFAULT_UTILITY.items()}


def expected_utilities(p_fraud, utility):
    """
    Calculate the expected utility for every action.
    Expected Utility = P(fraud) * Utility(fraud) + P(legitimate) * Utility(legitimate)
    where P(legitimate) = 1 - P(fraud).
    """
    if not isinstance(p_fraud, (int, float)):
        raise TypeError(f"Fraud probability must be a number, got {type(p_fraud).__name__}")
    if p_fraud < 0.0 or p_fraud > 1.0:
        raise ValueError(f"Fraud probability must be between 0.0 and 1.0, got {p_fraud}")

    p_legit = 1.0 - p_fraud
    eu = {}
    for action, outcomes in utility.items():
        u_fraud = outcomes['fraud']
        u_legit = outcomes['legit']
        eu[action] = p_fraud * u_fraud + p_legit * u_legit
    return eu


def choose_action(p_fraud, utility=None):
    """
    Select the action with the highest expected utility.
    
    Returns:
        (best_action, expected_utilities_dictionary, utility_gap)
    """
    if not isinstance(p_fraud, (int, float)):
        raise TypeError(f"Fraud probability must be a number, got {type(p_fraud).__name__}")
    if p_fraud < 0.0 or p_fraud > 1.0:
        raise ValueError(f"Fraud probability must be between 0.0 and 1.0, got {p_fraud}")

    if utility is None:
        table = load_utility()
    else:
        table = utility

    eu = expected_utilities(p_fraud, table)

    sorted_actions = sorted(eu.items(), key=lambda item: item[1], reverse=True)
    best_action, best_utility = sorted_actions[0]
    second_best_utility = sorted_actions[1][1] if len(sorted_actions) > 1 else best_utility
    utility_gap = best_utility - second_best_utility

    return best_action, eu, utility_gap
