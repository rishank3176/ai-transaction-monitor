"""
How a customer's past transactions change the agent's decision.

The history is used in two ways, both feeding the expected-utility calculation:

1. Risk update. The model's fraud probability is moved up when the new transaction
   is out of character for this customer (an unusual amount for that type of
   transaction, or a type they rarely use), and moved down slightly when it is
   typical for a customer with a long, clean history. The move is made on the
   log-odds scale. Completely out-of-character behaviour also carries a small
   minimum risk of its own (risk_floor), so it is never waved through just because
   the model sees nothing wrong; that is enough to hold it for a check, not to block it.

2. Utilities. The costs and benefits in the utility table are customer specific:
   - Financial loss: a larger-than-usual amount means more is lost if fraud is
     approved and more is saved if it is stopped (loss_factor).
   - Customer convenience: interrupting an established customer behaving normally
     costs more than interrupting a new or unusual one (friction_factor).

Unusual behaviour on its own never blocks a transaction (see BLOCK_MIN_MODEL_P).
A customer with no history gets factors of 1 and no shift, so the agent behaves
exactly as it did before.
"""

import math

MIN_HISTORY_FOR_STATS = 5     
FULL_STRENGTH_AT = 8          
FULL_TRUST_AT = 20            
STD_FLOOR = 0.5              
Z_LOW, Z_HIGH = 1.5, 3.5     
TYPE_WEIGHT = 0.35             
RISK_SHIFT_MAX = 1.2           
TRUST_RISK_REDUCTION = 0.4    
FLAG_SHIFT = 0.3               
RISK_FLOOR_MAX = 0.12        
LOSS_WEIGHT = 0.5             
FRICTION_WEIGHT = 0.5        
FRICTION_ACTIONS = ('hold', 'escalate', 'block')

BLOCK_MIN_MODEL_P = 0.30


def _clip(x, low=0.0, high=1.0):
    return max(low, min(high, x))


def neutral_behaviour():
    return {
        'history_size': 0, 'history_strength': 0.0, 'size_score': 0.0,
        'type_novelty': 0.0, 'z_score': None, 'unusualness': 0.0, 'trust': 0.0,
        'unresolved_flags': 0, 'risk_shift': 0.0, 'risk_floor': 0.0, 'loss_factor': 1.0,
        'friction_factor': 1.0, 'notes': [],
    }


def assess_behaviour(txn, profile):
    """Describe how unusual `txn` is for this customer, and what that does to risk and utilities."""
    out = neutral_behaviour()
    if not profile:
        return out

    n = int(profile.get('num_transactions') or 0)
    amount = float(txn.get('amount') or 0.0)
    ttype = txn.get('type')
    flags = int(profile.get('unresolved_flags', profile.get('past_flags', 0)) or 0)
    strength = _clip(n / FULL_STRENGTH_AT)
    notes = []

    size = 0.0
    z = None
    stats = profile.get('amount_stats') or {}
    by_type = stats.get(ttype) or {}
    overall = stats.get('ALL') or {}
    if by_type.get('n', 0) >= MIN_HISTORY_FOR_STATS:
        chosen, basis = by_type, f'{ttype} amount'
    elif overall.get('n', 0) >= MIN_HISTORY_FOR_STATS:
        chosen, basis = overall, 'amount'
    else:
        chosen, basis = None, None

    if chosen:
        spread = max(chosen['log_std'], STD_FLOOR)
        z = (math.log(max(amount, 1.0)) - chosen['log_mean']) / spread
        size = _clip((z - Z_LOW) / (Z_HIGH - Z_LOW))
        typical = math.exp(chosen['log_mean'])
        if size > 0 and typical > 0:
            notes.append(f"amount is about {amount / typical:.1f}x this customer's typical {basis}")
    else:
        avg = float(profile.get('average_amount') or 0.0)
        if n >= 1 and avg > 0 and amount > avg:
            ratio = amount / avg
            size = _clip((math.log(ratio) - math.log(3)) / (math.log(20) - math.log(3)))
            if size > 0:
                notes.append(f"amount is {ratio:.1f}x the customer's average")

    novelty = 0.0
    counts = profile.get('type_counts') or {}
    if n >= MIN_HISTORY_FOR_STATS and counts and ttype:
        share = counts.get(ttype, 0) / n
        novelty = _clip(1.0 - share / 0.10)
        if novelty >= 0.5:
            notes.append(f'{ttype} is rare for this customer ({share:.0%} of past transactions)')

    unusualness = _clip(size + TYPE_WEIGHT * novelty) * strength
    trust = _clip(n / FULL_TRUST_AT) * max(0.0, 1.0 - 0.25 * flags)

    shift = RISK_SHIFT_MAX * unusualness - TRUST_RISK_REDUCTION * trust * (1.0 - unusualness)
    if flags >= 2:
        shift += FLAG_SHIFT
        notes.append(f'{flags} earlier transactions are still blocked or in review')

    risk_floor = RISK_FLOOR_MAX * unusualness
    loss_factor = 1.0 + LOSS_WEIGHT * unusualness
    friction_factor = 1.0 + FRICTION_WEIGHT * trust * (1.0 - unusualness)
    if friction_factor >= 1.1:
        notes.append('established customer behaving normally: interrupting them is costly')

    out.update({
        'history_size': n, 'history_strength': round(strength, 3),
        'size_score': round(size, 3), 'type_novelty': round(novelty, 3),
        'z_score': None if z is None else round(z, 2),
        'unusualness': round(unusualness, 3), 'trust': round(trust, 3),
        'unresolved_flags': flags, 'risk_shift': round(shift, 3),
        'risk_floor': round(risk_floor, 3),
        'loss_factor': round(loss_factor, 3), 'friction_factor': round(friction_factor, 3),
        'notes': notes,
    })
    return out


def apply_risk_shift(p, shift):
    """Move a probability by `shift` on the log-odds scale."""
    p = min(max(p, 1e-6), 1.0 - 1e-6)
    odds = p / (1.0 - p) * math.exp(shift)
    return odds / (1.0 + odds)


def adjust_utility(table, behaviour):
    """Customer-specific copy of the utility table (the original is not modified)."""
    loss = behaviour['loss_factor']
    friction = behaviour['friction_factor']
    adjusted = {}
    for action, outcome in table.items():
        fraud = outcome['fraud'] * loss                 
        legit = outcome['legit']
        if action in FRICTION_ACTIONS and legit < 0:
            legit = legit * friction                     
        adjusted[action] = {'fraud': fraud, 'legit': legit}
    return adjusted