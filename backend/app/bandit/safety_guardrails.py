"""
Safety Guardrails & Exploration Constraints for Contextual Bandit Engine (Phase 4.6).
Enforces:
- NO_ACTION selection & fallbacks
- User-defined quiet periods (Do Not Disturb)
- Rate limiting / intervention frequency caps
- Arm quarantine circuit breaker (3 consecutive negative rewards)
- Explicit arm and category exclusions
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

NO_ACTION_ARM = "NO_ACTION"
DEFAULT_QUIET_HOURS = [22, 23, 0, 1, 2, 3, 4, 5, 6, 7]
DEFAULT_RATE_LIMIT_MINUTES = 45
CIRCUIT_BREAKER_CONSECUTIVE_NEGATIVES = 3
QUARANTINE_HOURS = 24


def _normalize_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class BanditSafetyGuardrails:
    """Enforces safety, rate limiting, and quarantine policies before bandit arm selection."""

    @classmethod
    def filter_eligible_arms(
        cls,
        candidate_arms: List[str],
        quarantined_arms: Set[str],
        excluded_arms: Optional[List[str]] = None,
        recent_presented_arms: Optional[Set[str]] = None,
    ) -> List[str]:
        """
        Filters candidate arms by removing quarantined, excluded, or recently repeated arms.
        Always guarantees NO_ACTION is included in the returned eligible set.
        """
        excluded = set(excluded_arms or [])
        recent = recent_presented_arms or set()

        eligible = []
        for arm in candidate_arms:
            if arm == NO_ACTION_ARM:
                continue
            if arm in quarantined_arms:
                continue
            if arm in excluded:
                continue
            if arm in recent:
                continue
            eligible.append(arm)

        # NO_ACTION is always an eligible fallback
        eligible.append(NO_ACTION_ARM)
        return eligible

    @classmethod
    def check_preconditions(
        cls,
        current_hour: int,
        last_nudge_timestamp: Optional[datetime],
        quiet_hours: Optional[List[int]] = None,
        rate_limit_minutes: int = DEFAULT_RATE_LIMIT_MINUTES,
        quiet_hours_override: bool = False,
        as_of: Optional[datetime] = None,
        is_imminent_deadline: bool = False,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates whether ANY intervention can be delivered at this epoch.
        Returns (is_allowed, block_reason). If not allowed, caller must select NO_ACTION.
        """
        now = _normalize_utc(as_of) or datetime.now(timezone.utc)
        qh = quiet_hours if quiet_hours is not None else DEFAULT_QUIET_HOURS

        # 1. Quiet hours check
        if not quiet_hours_override and current_hour in qh and not is_imminent_deadline:
            return False, f"Current hour {current_hour}:00 is inside user quiet period."

        # 2. Rate limiting / Cooldown check
        if last_nudge_timestamp and not is_imminent_deadline:
            last_utc = _normalize_utc(last_nudge_timestamp)
            mins_elapsed = (now - last_utc).total_seconds() / 60.0
            if mins_elapsed < rate_limit_minutes:
                return False, f"Rate limited: {mins_elapsed:.1f} min elapsed since last intervention (limit {rate_limit_minutes} min)."

        return True, None

    @classmethod
    def should_fallback_to_no_action(
        cls,
        best_arm: str,
        best_score: float,
        best_expected_payoff: float,
        min_payoff_threshold: float = 0.05,
    ) -> bool:
        """
        Safety check: If the top actionable arm has expected payoff below threshold,
        conclude that silent observation (NO_ACTION) is optimal to preserve momentum.
        """
        if best_arm == NO_ACTION_ARM:
            return True
        return best_expected_payoff < min_payoff_threshold
