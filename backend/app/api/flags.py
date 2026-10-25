"""Feature flags and experiment arm policy configuration.

Owner: Mit.
Enforces experiment arm behavior across generic, static_personalized, and closed_loop.
"""

from pydantic import BaseModel

from app.auth.models import ExperimentArm
from app.contracts.explanation import StyleParams


class ArmFeatureFlags(BaseModel):
    arm: ExperimentArm
    allow_trait_personalization: bool
    allow_closed_loop_feedback: bool
    allow_exploration: bool
    forced_style: StyleParams | None = None


GENERIC_STYLE = StyleParams(
    example_first=False,
    length="medium",
    depth="how",
    tone="neutral",
    include_diagram=False,
)


def get_arm_features(arm: ExperimentArm) -> ArmFeatureFlags:
    """Returns the operational feature flags for a given study arm."""
    if arm == "generic":
        return ArmFeatureFlags(
            arm=arm,
            allow_trait_personalization=False,
            allow_closed_loop_feedback=False,
            allow_exploration=False,
            forced_style=GENERIC_STYLE,
        )
    elif arm == "static_personalized":
        return ArmFeatureFlags(
            arm=arm,
            allow_trait_personalization=True,
            allow_closed_loop_feedback=False,
            allow_exploration=False,
            forced_style=None,
        )
    else:  # closed_loop
        return ArmFeatureFlags(
            arm=arm,
            allow_trait_personalization=True,
            allow_closed_loop_feedback=True,
            allow_exploration=True,
            forced_style=None,
        )
