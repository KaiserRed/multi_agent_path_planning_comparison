"""
Central algorithm registry.

To add a new algorithm:
  1. Implement a subclass of MAPFPlanner or MRTAPlanner.
  2. Import it here and append an instance to the appropriate list.
"""

from mapf.cbs import CBSPlanner, CBSSIPPPlanner
from mapf.ecbs import ECBSPlanner
from mapf.eecbs import EECBSPlanner
from mapf.m_star import MStarPlanner
from mapf.pibt import PIBTPlanner
from mapf.ca_star import CAStarPlanner
from mapf.whca_star import WHCAStarPlanner

from mrta.hungarian import HungarianPlanner
from mrta.min_cost_flow import MinCostFlowPlanner
from mrta.sequential_auction import SequentialAuctionPlanner
from mrta.greedy import GreedyPlanner
from mrta.combinatorial_auction import CombinatorialAuctionPlanner
from mrta.random_assign import RandomPlanner

# Registry 
ALGORITHMS: dict = {
    "MAPF": [
        CBSPlanner(),
        CBSSIPPPlanner(),
        ECBSPlanner(),
        EECBSPlanner(),
        MStarPlanner(),
        PIBTPlanner(),
        CAStarPlanner(),
        WHCAStarPlanner(),
    ],
    "MRTA": [
        HungarianPlanner(),
        MinCostFlowPlanner(),
        SequentialAuctionPlanner(),
        GreedyPlanner(),
        CombinatorialAuctionPlanner(),
        RandomPlanner(),
    ],
}


def get_planner(algo_type: str, display_name: str):
    """Return the planner instance matching *algo_type* and *display_name*."""
    for planner in ALGORITHMS.get(algo_type, []):
        if planner.DISPLAY_NAME == display_name:
            return planner
    raise KeyError(f"Algorithm '{display_name}' of type '{algo_type}' not found.")
