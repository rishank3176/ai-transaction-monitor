"""
Visualization script for utility-based decision regions across fraud probabilities.

Calculates expected utilities for all actions (approve, hold, escalate, block)
over evenly spaced fraud probabilities [0, 1] using DEFAULT_UTILITY,
and outputs a sensitivity chart to docs/sensitivity.png.
"""

from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

from agent.utility import DEFAULT_UTILITY, expected_utilities


def generate_sensitivity_chart():
    # 101 probabilities evenly spaced between 0 and 1
    p_values = np.linspace(0.0, 1.0, 101)

    # Use default utility table for reproducible sensitivity analysis
    actions = ['approve', 'hold', 'escalate', 'block']
    eu_by_action = {action: [] for action in actions}

    for p in p_values:
        eu = expected_utilities(float(p), DEFAULT_UTILITY)
        for action in actions:
            eu_by_action[action].append(eu[action])

    # Plot
    plt.figure(figsize=(9, 6))

    colors = {
        'approve': '#2ca02c',   # Green
        'hold': '#ff7f0e',      # Orange
        'escalate': '#d62728',  # Red
        'block': '#1f77b4'      # Blue
    }

    for action in actions:
        plt.plot(
            p_values,
            eu_by_action[action],
            label=action.capitalize(),
            color=colors.get(action),
            linewidth=2
        )

    plt.xlabel('Probability of fraud')
    plt.ylabel('Expected utility')
    plt.title('Best action at each fraud probability')
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.legend()
    plt.tight_layout()

    # Save to docs/sensitivity.png at 150 DPI
    output_dir = Path(__file__).resolve().parent.parent / "docs"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "sensitivity.png"

    plt.savefig(output_path, dpi=150)
    plt.close()

    print(f"Sensitivity chart successfully saved to {output_path}")


if __name__ == '__main__':
    generate_sensitivity_chart()
