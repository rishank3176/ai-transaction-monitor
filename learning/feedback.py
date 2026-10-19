import copy
import json
import sqlite3
from data.db import DB_PATH
from agent.utility import DEFAULT_UTILITY, CONFIG_PATH


def update_utilities(step=1.0):
    # Recompute the utility table from the defaults plus ALL human feedback so far
    util = copy.deepcopy(DEFAULT_UTILITY)
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute('SELECT agent_decision, human_decision FROM feedback').fetchall()
    conn.close()

    for agent_d, human_d in rows:
        if agent_d not in util:
            continue
        if human_d == 'approve' and agent_d in ('hold', 'block', 'escalate'):
            util[agent_d]['legit'] -= step      # false alarm: this action costs more
        elif human_d == 'block':
            if agent_d in ('approve', 'hold'):
                util[agent_d]['fraud'] -= step  # fraud was under-reacted to
            else:
                util[agent_d]['fraud'] += step  # the agent was right: reward

    for a in util:
        for k in util[a]:
            util[a][k] = max(-200, min(200, util[a][k]))

    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(util, f, indent=2)
    return util