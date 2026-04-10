"""
Sequential Single-Item Auction for MRTA — chain assignment mode.

Each round one unassigned task is auctioned.  The key difference from a
plain 1-to-1 auction is that agents bid from their **virtual position**
(the location of the last task already in their chain), not from their
current physical position.  This lets the auction build coherent task
chains: an agent that has already won task A bids for task B as if it
will depart from A, which naturally reflects the true future travel cost.

Task ordering uses the *bid-gap* heuristic: the task with the largest
difference between the best and second-best bid is auctioned first, so
the most "contested" (unique-fit) tasks are assigned first.

Reference
---------
Lagoudakis et al., "Auction-Based Multi-Robot Routing", RSS 2005.
"""

from mrta.planner import MRTAPlanner


def sequential_auction_chains(agents, tasks):
    """
    Build task chains via sequential auction with virtual-position bidding.

    Returns
    -------
    dict[agent_id -> list[Task]]
        Each agent's ordered list of tasks to execute in sequence.
    """
    if not agents or not tasks:
        return {}


    virtual_pos: dict = {a.id: (a.x, a.y) for a in agents}
    agent_map: dict = {a.id: a for a in agents}
    chains: dict = {a.id: [] for a in agents}

    free_tasks = list(tasks)

    while free_tasks:
        best_task = None
        best_agent_id = None
        best_gap = -1.0
        best_bid = float("inf")

        for task in free_tasks:
            bids = []
            for a in agents:
                vx, vy = virtual_pos[a.id]
                cost = abs(vx - task.x) + abs(vy - task.y)
                bids.append((cost, a.id))
            bids.sort(key=lambda b: b[0])

            top_bid, top_aid = bids[0]
            second_bid = bids[1][0] if len(bids) > 1 else top_bid
            gap = second_bid - top_bid

            if gap > best_gap or (gap == best_gap and top_bid < best_bid):
                best_gap = gap
                best_bid = top_bid
                best_task = task
                best_agent_id = top_aid

        if best_task is None:
            break


        chains[best_agent_id].append(best_task)
        virtual_pos[best_agent_id] = (best_task.x, best_task.y)
        free_tasks = [t for t in free_tasks if t.id != best_task.id]

    # Return only agents that received at least one task.
    return {aid: chain for aid, chain in chains.items() if chain}


class SequentialAuctionPlanner(MRTAPlanner):
    DISPLAY_NAME = "Sequential Auction"
    DESCRIPTION = (
        "Sequential single-item auction with virtual-position bidding. "
        "Agents bid from the end of their current task chain, so the "
        "auction naturally builds coherent multi-task routes. "
        "Queue mode: full chain planned upfront."
    )
    IS_CENTRALIZED = False
    IS_ONLINE = False
    ASSIGNMENT_MODE = "queue"

    def plan(self, world, agents, tasks):
        return sequential_auction_chains(agents, tasks)
