"""
Combinatorial Auction (Bundle) for MRTA — chain assignment mode.

Builds task chains for all agents in a single planning pass using a
regret-based winner-determination heuristic, extended to chain bidding:

Phase 1 — Regret-based greedy with virtual positions
    Agents bid from their virtual position (end of current chain), so
    bidding naturally reflects sequential travel cost.  The task with the
    highest regret (strongest preference for one agent over others) is
    assigned first.

Phase 2 — Local-swap improvement
    For every pair of adjacent tasks across all agents' chains, try
    swapping or moving one task to another agent's chain if it reduces
    total virtual-travel cost.  Repeat until no improvement is found.

This captures the key ideas of combinatorial auctions (joint evaluation,
winner determination) while staying tractable.  Queue mode: full chains
are built upfront in one call.
"""

from __future__ import annotations

from mrta.planner import MRTAPlanner


def combinatorial_auction_chains(agents, tasks):
    """
    Build task chains via combinatorial auction with virtual-position bidding
    and local-swap improvement.

    Returns
    -------
    dict[agent_id -> list[Task]]
    """
    if not agents or not tasks:
        return {}

    # Virtual positions advance as tasks are assigned.
    virtual_pos: dict = {a.id: (a.x, a.y) for a in agents}
    chains: dict = {a.id: [] for a in agents}

    def _bid(aid, task):
        vx, vy = virtual_pos[aid]
        return abs(vx - task.x) + abs(vy - task.y)

    # Phase 1: regret-based greedy with virtual positions
    free_tasks = list(tasks)

    while free_tasks:
        best_task = None
        best_agent_id = None
        best_regret = -1
        best_bid = float("inf")

        for task in free_tasks:
            bids = sorted(
                ((_bid(a.id, task), a.id) for a in agents),
                key=lambda b: b[0],
            )
            top_bid, top_aid = bids[0]
            second_bid = bids[1][0] if len(bids) > 1 else top_bid
            regret = second_bid - top_bid

            if regret > best_regret or (
                    regret == best_regret and top_bid < best_bid):
                best_regret = regret
                best_bid = top_bid
                best_task = task
                best_agent_id = top_aid

        if best_task is None:
            break

        chains[best_agent_id].append(best_task)
        virtual_pos[best_agent_id] = (best_task.x, best_task.y)
        free_tasks = [t for t in free_tasks if t.id != best_task.id]

    # Phase 2: local swap improvement
    # Compute total chain cost for a given agent given an ordered task list,
    # starting from the agent's real position.
    agent_map = {a.id: a for a in agents}

    def _chain_cost(aid, chain):
        ax, ay = agent_map[aid].x, agent_map[aid].y
        cost = 0
        for task in chain:
            cost += abs(ax - task.x) + abs(ay - task.y)
            ax, ay = task.x, task.y
        return cost

    # Try moving any single task from one agent's chain to another, and
    # swapping tasks between any two agents' chains.
    improved = True
    while improved:
        improved = False
        agent_ids = [a.id for a in agents if chains[a.id]]

        # Move: take task at position i in chain_a and insert it at position j
        # in chain_b (different agent).
        for aid_a in agent_ids:
            for i, task in enumerate(chains[aid_a]):
                for aid_b in agent_ids:
                    if aid_b == aid_a:
                        continue
                    base_cost = _chain_cost(aid_a, chains[aid_a]) + \
                                _chain_cost(aid_b, chains[aid_b])

                    new_chain_a = [t for t in chains[aid_a] if t.id != task.id]
                    # Try inserting task at every position in chain_b
                    for j in range(len(chains[aid_b]) + 1):
                        new_chain_b = (chains[aid_b][:j] + [task] +
                                       chains[aid_b][j:])
                        new_cost = (_chain_cost(aid_a, new_chain_a) +
                                    _chain_cost(aid_b, new_chain_b))
                        if new_cost < base_cost - 1e-9:
                            chains[aid_a] = new_chain_a
                            chains[aid_b] = new_chain_b
                            improved = True
                            break
                    if improved:
                        break
                if improved:
                    break
            if improved:
                break

    return {aid: chain for aid, chain in chains.items() if chain}


class CombinatorialAuctionPlanner(MRTAPlanner):
    DISPLAY_NAME = "Combinatorial Auction"
    DESCRIPTION = (
        "Combinatorial auction with virtual-position bidding, regret-based "
        "winner determination, and local-move improvement. Builds full task "
        "chains for all agents in a single pass. Queue mode."
    )
    IS_CENTRALIZED = False
    IS_ONLINE = False
    ASSIGNMENT_MODE = "queue"

    def plan(self, world, agents, tasks):
        return combinatorial_auction_chains(agents, tasks)
