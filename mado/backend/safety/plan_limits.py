"""Plan-based resource limits for MADO.

Enforces project count and other limits based on the active plan.
Plans are configured via environment variables or a license key.

Environment variables:
  MADO_PLAN: "free" | "pro" | "team" | "enterprise" (default: "free")
  MADO_LICENSE_KEY: License key that overrides MADO_PLAN
  MADO_MAX_PROJECTS: Override the max project count (any plan)
"""

import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Plan definitions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PlanConfig:
    """Resource limits for a plan tier."""
    name: str
    display_name: str
    max_projects: int
    max_agents_per_run: int
    max_iterations: int
    max_concurrent_runs: int
    web_access: bool


PLANS: dict[str, PlanConfig] = {
    "free": PlanConfig(
        name="free",
        display_name="Free",
        max_projects=3,
        max_agents_per_run=4,
        max_iterations=5,
        max_concurrent_runs=1,
        web_access=False,
    ),
    "pro": PlanConfig(
        name="pro",
        display_name="Pro",
        max_projects=20,
        max_agents_per_run=9,
        max_iterations=10,
        max_concurrent_runs=3,
        web_access=True,
    ),
    "team": PlanConfig(
        name="team",
        display_name="Team",
        max_projects=100,
        max_agents_per_run=9,
        max_iterations=20,
        max_concurrent_runs=10,
        web_access=True,
    ),
    "enterprise": PlanConfig(
        name="enterprise",
        display_name="Enterprise",
        max_projects=10000,
        max_agents_per_run=9,
        max_iterations=50,
        max_concurrent_runs=50,
        web_access=True,
    ),
}


# ---------------------------------------------------------------------------
# License key validation (simple hash-based)
# ---------------------------------------------------------------------------

_LICENSE_PLAN_PREFIXES = {
    "MADO-PRO-": "pro",
    "MADO-TEAM-": "team",
    "MADO-ENT-": "enterprise",
}


def _resolve_plan_from_license(license_key: str) -> Optional[str]:
    """Resolve plan name from a license key prefix."""
    for prefix, plan in _LICENSE_PLAN_PREFIXES.items():
        if license_key.startswith(prefix):
            return plan
    return None


# ---------------------------------------------------------------------------
# Active plan resolution
# ---------------------------------------------------------------------------

def get_active_plan() -> PlanConfig:
    """Get the currently active plan based on env vars / license key."""
    # License key takes priority
    license_key = os.environ.get("MADO_LICENSE_KEY", "").strip()
    if license_key:
        plan_name = _resolve_plan_from_license(license_key)
        if plan_name and plan_name in PLANS:
            logger.info(f"Plan resolved from license key: {plan_name}")
            return PLANS[plan_name]
        logger.warning(f"Invalid license key prefix, falling back to env/default")

    # Explicit plan env var
    plan_name = os.environ.get("MADO_PLAN", "free").strip().lower()
    if plan_name in PLANS:
        return PLANS[plan_name]

    logger.warning(f"Unknown plan '{plan_name}', defaulting to free")
    return PLANS["free"]


def get_max_projects() -> int:
    """Get the effective max project count (respects override env var)."""
    override = os.environ.get("MADO_MAX_PROJECTS", "").strip()
    if override:
        try:
            val = int(override)
            if val > 0:
                return val
        except ValueError:
            pass
    return get_active_plan().max_projects


def get_plan_info() -> dict:
    """Get plan info for API responses."""
    plan = get_active_plan()
    max_projects = get_max_projects()
    return {
        "plan": plan.name,
        "display_name": plan.display_name,
        "limits": {
            "max_projects": max_projects,
            "max_agents_per_run": plan.max_agents_per_run,
            "max_iterations": plan.max_iterations,
            "max_concurrent_runs": plan.max_concurrent_runs,
        },
    }


class PlanLimitError(Exception):
    """Raised when a plan limit is exceeded."""
    def __init__(self, resource: str, current: int, limit: int, plan: str):
        self.resource = resource
        self.current = current
        self.limit = limit
        self.plan = plan
        super().__init__(
            f"{resource} limit reached: {current}/{limit} "
            f"(plan: {plan}). Upgrade to increase limits."
        )
