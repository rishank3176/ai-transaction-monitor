"""
Standalone test script for UtilityAgent.

Tests decision boundaries across diverse fraud probabilities and customer history
adjustments using hand-crafted transaction data and profiles.
"""

from agent.agent import decide, UtilityAgent


def run_test_a():
    print("=" * 60)
    print("Test A: Decisions across different fraud probabilities")
    print("=" * 60)

    # Customer profile with normal baseline that triggers no adjustments
    neutral_profile = {
        'customer_id': 101,
        'num_transactions': 10,
        'average_amount': 1000.0,
        'max_amount': 2500.0,
        'past_flags': 0
    }

    # Transaction with amount matching average (ratio = 1.0, no adjustments)
    txn = {
        'transaction_id': 1,
        'customer_id': 101,
        'step': 10,
        'type': 'PAYMENT',
        'amount': 1000.0,
        'old_balance': 5000.0,
        'new_balance': 4000.0
    }

    test_cases = [
        (0.02, 'approve'),
        (0.15, 'hold'),
        (0.40, 'escalate'),
        (0.90, 'block')
    ]

    all_passed = True
    for p, expected_action in test_cases:
        score_result = {
            'score': 0.1,
            'p_fraud': p,
            'is_anomaly': p > 0.3,
            'top_reasons': ['test pattern']
        }

        res = decide(txn, score_result, profile=neutral_profile)
        actual_action = res['decision']
        confidence = res['confidence']
        p_res = res['p_fraud']

        match = (actual_action == expected_action)
        if not match:
            all_passed = False

        status_str = "PASS" if match else f"FAIL (expected {expected_action})"
        print(f"p={p:.2f} -> Action: {actual_action:8s} | Conf: {confidence:.3f} | Result p: {p_res:.3f} | [{status_str}]")

    print(f"Test A Summary: {'ALL PASSED' if all_passed else 'SOME FAILED'}\n")
    return all_passed


def run_test_b():
    print("=" * 60)
    print("Test B: Customer-history adjustment")
    print("=" * 60)

    # Profile: 20 previous txns, avg amount 5,000, 0 past flags
    profile_b = {
        'customer_id': 202,
        'num_transactions': 20,
        'average_amount': 5000.0,
        'max_amount': 10000.0,
        'past_flags': 0
    }

    # Txn amount 90,000 -> 18x average (>10x and num_txns>=5 -> +0.15)
    txn_b = {
        'transaction_id': 2,
        'customer_id': 202,
        'step': 15,
        'type': 'TRANSFER',
        'amount': 90000.0,
        'old_balance': 100000.0,
        'new_balance': 10000.0
    }

    initial_p = 0.15
    score_result_b = {
        'score': 0.25,
        'p_fraud': initial_p,
        'is_anomaly': False,
        'top_reasons': ['high-risk transaction type: TRANSFER']
    }

    res_b = decide(txn_b, score_result_b, profile=profile_b)
    adj_p = res_b['p_fraud']
    decision = res_b['decision']
    reasoning = res_b['reasoning']

    expected_p = 0.30
    expected_decision = 'escalate'

    p_match = abs(adj_p - expected_p) < 1e-4
    dec_match = (decision == expected_decision)
    test_passed = p_match and dec_match

    print(f"Initial p_fraud:     {initial_p:.2f}")
    print(f"Adjusted p_fraud:    {adj_p:.3f} (Expected: {expected_p:.2f}) -> {'PASS' if p_match else 'FAIL'}")
    print(f"Decision:            {decision} (Expected: {expected_decision}) -> {'PASS' if dec_match else 'FAIL'}")
    print(f"Reasoning:           {reasoning}")
    print(f"Test B Summary:      {'PASS' if test_passed else 'FAIL'}\n")
    return test_passed


def main():
    print("Starting UtilityAgent Validation Tests...\n")
    passed_a = run_test_a()
    passed_b = run_test_b()

    if passed_a and passed_b:
        print("All try_agent tests completed successfully!")
    else:
        print("Some try_agent tests failed!")
        exit(1)


if __name__ == '__main__':
    main()
