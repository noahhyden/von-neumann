"""mission - the end-to-end von Neumann probe mission as one pure fold.

Chains the four sibling modules (closure-sim, probe-sim, power-budget,
launch-economics) into a single deterministic run: launch a seed, arrive at a
heliocentric distance, split solar power between building and thinking, replicate,
and price the launch-mass payoff. See run.py for the stage-by-stage story.
"""

from mission.run import MissionResult, run_mission
from mission.scenario import MissionScenario, default_mission_scenario

__all__ = [
    "MissionResult",
    "run_mission",
    "MissionScenario",
    "default_mission_scenario",
]
