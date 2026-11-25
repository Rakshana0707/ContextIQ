"""
Service layer for ContextIQ Long-Term Behavioral Memory & Pattern Evolution (Phase 8.3).
Maintains structured, evolving behavioral memory over extended periods, extending the core
Behavioral Profile digital twin rather than introducing a competing profile system.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models.behavioral_memory import (
    BehavioralMemory,
    BehavioralTemporalSummary,
    MemoryCategory,
    MemorySourceType,
    MemoryValidityStatus,
    PatternEvolutionType,
    UserBehavioralMemoryPreference,
)
from app.models.behavioral_profile import ProfileSnapshot, UserBehavioralProfile
from app.models.focus_window import UserFocusWindow
from app.models.knowledge_graph import Goal, Milestone
from app.models.recommendation_feedback import RecommendationFeedback
from app.models.user_intervention import UserIntervention
from app.schemas.behavioral_memory import (
    BehavioralMemoryCreate,
    BehavioralMemoryOverviewRead,
    BehavioralMemoryRead,
    BehavioralMemoryUpdate,
    MemoryCorrectionRequest,
    MemorySynthesisResponse,
    UserBehavioralMemoryPreferenceRead,
    UserBehavioralMemoryPreferenceUpdate,
)

logger = logging.getLogger(__name__)


class BehavioralMemoryService:
    """Core service for long-term behavioral memory lifecycle, evolution, and user control."""

    # -----------------------------------------------------------------------
    # User Preferences & Configuration Controls
    # -----------------------------------------------------------------------

    @staticmethod
    def get_or_create_preferences(
        db: Session,
        user_id: uuid.UUID,
    ) -> UserBehavioralMemoryPreference:
        pref = db.execute(
            select(UserBehavioralMemoryPreference).where(
                UserBehavioralMemoryPreference.user_id == user_id
            )
        ).scalar_one_or_none()
        if not pref:
            pref = UserBehavioralMemoryPreference(
                user_id=user_id,
                disabled_categories=[],
                retention_policy_days=365,
                auto_outdate_dormant_days=45,
                auto_synthesis_enabled=True,
            )
            db.add(pref)
            db.flush()
        return pref

    @staticmethod
    def update_preferences(
        db: Session,
        user_id: uuid.UUID,
        payload: UserBehavioralMemoryPreferenceUpdate,
    ) -> UserBehavioralMemoryPreference:
        pref = BehavioralMemoryService.get_or_create_preferences(db, user_id)
        if payload.disabled_categories is not None:
            pref.disabled_categories = payload.disabled_categories
        if payload.retention_policy_days is not None:
            pref.retention_policy_days = payload.retention_policy_days
        if payload.auto_outdate_dormant_days is not None:
            pref.auto_outdate_dormant_days = payload.auto_outdate_dormant_days
        if payload.auto_synthesis_enabled is not None:
            pref.auto_synthesis_enabled = payload.auto_synthesis_enabled
        db.flush()
        return pref

    # -----------------------------------------------------------------------
    # Memory CRUD Operations
    # -----------------------------------------------------------------------

    @staticmethod
    def create_memory(
        db: Session,
        user_id: uuid.UUID,
        payload: BehavioralMemoryCreate,
    ) -> BehavioralMemory:
        prefs = BehavioralMemoryService.get_or_create_preferences(db, user_id)
        cat_str = payload.category.value if hasattr(payload.category, "value") else str(payload.category)
        if cat_str in (prefs.disabled_categories or []):
            raise ValidationError(f"Category '{cat_str}' is currently disabled in user memory preferences.")

        now = datetime.now(timezone.utc)
        evolution_initial = [
            {
                "timestamp": now.isoformat(),
                "evolution_type": PatternEvolutionType.EMERGING.value,
                "previous_status": None,
                "new_status": MemoryValidityStatus.ACTIVE.value,
                "previous_confidence": None,
                "new_confidence": float(payload.confidence),
                "reason": "Initial memory record creation.",
                "evidence_summary": payload.supporting_evidence or {},
            }
        ]

        exp_policy = payload.expiration_policy or {
            "retention_days": prefs.retention_policy_days,
            "review_after_days": 30,
            "auto_outdate_dormant_days": prefs.auto_outdate_dormant_days,
        }

        memory = BehavioralMemory(
            user_id=user_id,
            category=payload.category,
            title=payload.title,
            description=payload.description,
            source_type=payload.source_type,
            validity_status=MemoryValidityStatus.ACTIVE,
            confidence=float(payload.confidence),
            observation_count=1,
            first_observed_at=now,
            last_observed_at=now,
            supporting_evidence=payload.supporting_evidence or {},
            evolution_history=evolution_initial,
            expiration_policy=exp_policy,
            is_user_corrected=False,
            is_disabled=False,
        )
        db.add(memory)
        db.flush()
        return memory

    @staticmethod
    def get_memory_by_id(
        db: Session,
        user_id: uuid.UUID,
        memory_id: uuid.UUID,
    ) -> BehavioralMemory:
        memory = db.execute(
            select(BehavioralMemory).where(
                BehavioralMemory.id == memory_id,
                BehavioralMemory.user_id == user_id,
            )
        ).scalar_one_or_none()
        if not memory:
            raise NotFoundError(f"BehavioralMemory {memory_id} not found for user {user_id}")
        return memory

    @staticmethod
    def list_memories(
        db: Session,
        user_id: uuid.UUID,
        category: Optional[MemoryCategory] = None,
        validity_status: Optional[MemoryValidityStatus] = None,
        source_type: Optional[MemorySourceType] = None,
        search_query: Optional[str] = None,
        include_disabled: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> List[BehavioralMemory]:
        stmt = select(BehavioralMemory).where(BehavioralMemory.user_id == user_id)
        if not include_disabled:
            stmt = stmt.where(BehavioralMemory.is_disabled.is_(False))
        if category:
            stmt = stmt.where(BehavioralMemory.category == category)
        if validity_status:
            stmt = stmt.where(BehavioralMemory.validity_status == validity_status)
        if source_type:
            stmt = stmt.where(BehavioralMemory.source_type == source_type)
        if search_query:
            q_like = f"%{search_query.strip()}%"
            stmt = stmt.where(
                or_(
                    BehavioralMemory.title.ilike(q_like),
                    BehavioralMemory.description.ilike(q_like),
                )
            )

        stmt = stmt.order_by(BehavioralMemory.confidence.desc(), BehavioralMemory.last_observed_at.desc())
        return list(db.execute(stmt.limit(limit).offset(offset)).scalars().all())

    @staticmethod
    def update_memory(
        db: Session,
        user_id: uuid.UUID,
        memory_id: uuid.UUID,
        payload: BehavioralMemoryUpdate,
    ) -> BehavioralMemory:
        memory = BehavioralMemoryService.get_memory_by_id(db, user_id, memory_id)
        now = datetime.now(timezone.utc)
        prev_status = memory.validity_status.value if hasattr(memory.validity_status, "value") else str(memory.validity_status)
        prev_conf = memory.confidence

        if payload.title is not None:
            memory.title = payload.title
        if payload.description is not None:
            memory.description = payload.description
        if payload.confidence is not None:
            memory.confidence = float(payload.confidence)
        if payload.is_disabled is not None:
            memory.is_disabled = payload.is_disabled
        if payload.user_correction_notes is not None:
            memory.user_correction_notes = payload.user_correction_notes
        if payload.expiration_policy is not None:
            memory.expiration_policy = payload.expiration_policy
        if payload.validity_status is not None:
            memory.validity_status = payload.validity_status

        # If status or confidence changed, append evolution event
        new_status = memory.validity_status.value if hasattr(memory.validity_status, "value") else str(memory.validity_status)
        if new_status != prev_status or abs(memory.confidence - prev_conf) > 0.01:
            history = list(memory.evolution_history or [])
            history.append({
                "timestamp": now.isoformat(),
                "evolution_type": PatternEvolutionType.PREFERENCE_CHANGE.value,
                "previous_status": prev_status,
                "new_status": new_status,
                "previous_confidence": prev_conf,
                "new_confidence": memory.confidence,
                "reason": "Direct memory update.",
                "evidence_summary": {"update_payload": payload.model_dump(exclude_unset=True)},
            })
            memory.evolution_history = history

        db.flush()
        return memory

    @staticmethod
    def correct_memory(
        db: Session,
        user_id: uuid.UUID,
        memory_id: uuid.UUID,
        correction: MemoryCorrectionRequest,
    ) -> BehavioralMemory:
        """
        User-initiated correction of inaccurate or misinferred behavioral memories.
        Applies user adjustments, preserves audit provenance, and adapts pattern status.
        """
        memory = BehavioralMemoryService.get_memory_by_id(db, user_id, memory_id)
        now = datetime.now(timezone.utc)
        prev_status = memory.validity_status.value if hasattr(memory.validity_status, "value") else str(memory.validity_status)
        prev_conf = memory.confidence

        memory.is_user_corrected = True
        memory.user_correction_notes = correction.user_notes

        if correction.corrected_description:
            memory.description = correction.corrected_description

        if correction.is_inaccurate:
            memory.validity_status = MemoryValidityStatus.CORRECTED
            memory.confidence = max(0.1, memory.confidence * 0.5)
        elif correction.validity_status:
            memory.validity_status = correction.validity_status

        history = list(memory.evolution_history or [])
        history.append({
            "timestamp": now.isoformat(),
            "evolution_type": PatternEvolutionType.PREFERENCE_CHANGE.value,
            "previous_status": prev_status,
            "new_status": memory.validity_status.value if hasattr(memory.validity_status, "value") else str(memory.validity_status),
            "previous_confidence": prev_conf,
            "new_confidence": memory.confidence,
            "reason": f"User correction applied: {correction.user_notes}",
            "evidence_summary": {
                "user_notes": correction.user_notes,
                "is_inaccurate": correction.is_inaccurate,
                "corrected_description": correction.corrected_description,
            },
        })
        memory.evolution_history = history
        db.flush()
        return memory

    @staticmethod
    def delete_memory(
        db: Session,
        user_id: uuid.UUID,
        memory_id: uuid.UUID,
    ) -> None:
        memory = BehavioralMemoryService.get_memory_by_id(db, user_id, memory_id)
        db.delete(memory)
        db.flush()

    @staticmethod
    def reset_behavioral_memories(
        db: Session,
        user_id: uuid.UUID,
        category: Optional[MemoryCategory] = None,
    ) -> int:
        """
        User-controlled selective or full memory reset.
        Preserves user autonomy and right-to-forget privacy guarantees.
        """
        stmt = delete(BehavioralMemory).where(BehavioralMemory.user_id == user_id)
        if category:
            stmt = stmt.where(BehavioralMemory.category == category)
        result = db.execute(stmt)
        db.flush()
        return result.rowcount

    # -----------------------------------------------------------------------
    # Pattern Evolution & Confidence Dynamics
    # -----------------------------------------------------------------------

    @staticmethod
    def reinforce_pattern(
        db: Session,
        memory: BehavioralMemory,
        supporting_evidence: Dict[str, Any],
        boost_factor: float = 0.05,
    ) -> BehavioralMemory:
        """
        Strengthens an established or emerging pattern upon observed corroborating telemetry.
        """
        now = datetime.now(timezone.utc)
        prev_status = memory.validity_status.value if hasattr(memory.validity_status, "value") else str(memory.validity_status)
        prev_conf = memory.confidence

        memory.observation_count += 1
        memory.reinforcement_count += 1
        memory.last_observed_at = now
        memory.last_reinforced_at = now

        # Asymptotic confidence reinforcement: c_new = c + boost * (1 - c)
        new_conf = min(0.98, prev_conf + boost_factor * (1.0 - prev_conf))
        memory.confidence = round(new_conf, 4)

        # Transition status based on evidence depth
        new_status = prev_status
        if memory.validity_status == MemoryValidityStatus.EMERGING and memory.observation_count >= 3:
            memory.validity_status = MemoryValidityStatus.STRENGTHENING
            new_status = MemoryValidityStatus.STRENGTHENING.value
        elif memory.validity_status in (MemoryValidityStatus.STRENGTHENING, MemoryValidityStatus.EMERGING) and memory.observation_count >= 5 and memory.confidence >= 0.75:
            memory.validity_status = MemoryValidityStatus.ACTIVE
            new_status = MemoryValidityStatus.ACTIVE.value
        elif memory.validity_status in (MemoryValidityStatus.WEAKENING, MemoryValidityStatus.OUTDATED):
            memory.validity_status = MemoryValidityStatus.STRENGTHENING
            new_status = MemoryValidityStatus.STRENGTHENING.value

        history = list(memory.evolution_history or [])
        history.append({
            "timestamp": now.isoformat(),
            "evolution_type": PatternEvolutionType.STRENGTHENING.value,
            "previous_status": prev_status,
            "new_status": new_status,
            "previous_confidence": prev_conf,
            "new_confidence": memory.confidence,
            "reason": f"Pattern reinforced with new empirical telemetry (obs={memory.observation_count}).",
            "evidence_summary": supporting_evidence,
        })
        memory.evolution_history = history
        db.flush()
        return memory

    @staticmethod
    def contradict_pattern(
        db: Session,
        memory: BehavioralMemory,
        contradicting_evidence: Dict[str, Any],
        penalty: float = 0.15,
    ) -> BehavioralMemory:
        """
        Weakens or flags a pattern upon observed contrary behavior.
        Explicit user instructions require repeated counter-evidence before any status shift.
        """
        now = datetime.now(timezone.utc)
        prev_status = memory.validity_status.value if hasattr(memory.validity_status, "value") else str(memory.validity_status)
        prev_conf = memory.confidence

        memory.contradiction_count += 1
        memory.last_contradicted_at = now

        # If explicit instruction, do not penalize aggressively on noise
        effective_penalty = penalty * 0.4 if memory.source_type == MemorySourceType.EXPLICIT_USER_INSTRUCTION else penalty
        new_conf = max(0.1, prev_conf - effective_penalty)
        memory.confidence = round(new_conf, 4)

        new_status = prev_status
        if memory.confidence < 0.45 and memory.source_type != MemorySourceType.EXPLICIT_USER_INSTRUCTION:
            memory.validity_status = MemoryValidityStatus.WEAKENING
            new_status = MemoryValidityStatus.WEAKENING.value
        if memory.contradiction_count >= 4 and memory.confidence < 0.3:
            memory.validity_status = MemoryValidityStatus.CONTRADICTED
            new_status = MemoryValidityStatus.CONTRADICTED.value

        history = list(memory.evolution_history or [])
        history.append({
            "timestamp": now.isoformat(),
            "evolution_type": PatternEvolutionType.CONTRADICTORY.value if new_status == MemoryValidityStatus.CONTRADICTED.value else PatternEvolutionType.WEAKENING.value,
            "previous_status": prev_status,
            "new_status": new_status,
            "previous_confidence": prev_conf,
            "new_confidence": memory.confidence,
            "reason": f"Pattern contradicted by new operational telemetry (contra={memory.contradiction_count}).",
            "evidence_summary": contradicting_evidence,
        })
        memory.evolution_history = history
        db.flush()
        return memory

    @staticmethod
    def evaluate_outdated_patterns(
        db: Session,
        user_id: uuid.UUID,
        dormant_days: Optional[int] = None,
    ) -> List[BehavioralMemory]:
        """
        Scans active/strengthening memories and transitions dormant patterns to OUTDATED.
        Prevents assuming historical behavior permanently represents current behavior.
        """
        prefs = BehavioralMemoryService.get_or_create_preferences(db, user_id)
        threshold_days = dormant_days or prefs.auto_outdate_dormant_days
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=threshold_days)

        stmt = select(BehavioralMemory).where(
            BehavioralMemory.user_id == user_id,
            BehavioralMemory.source_type != MemorySourceType.EXPLICIT_USER_INSTRUCTION,
            BehavioralMemory.validity_status.in_([
                MemoryValidityStatus.ACTIVE,
                MemoryValidityStatus.STRENGTHENING,
                MemoryValidityStatus.WEAKENING,
            ]),
            BehavioralMemory.last_observed_at <= cutoff_date,
        )
        candidates = list(db.execute(stmt).scalars().all())
        now = datetime.now(timezone.utc)

        updated_memories: List[BehavioralMemory] = []
        for mem in candidates:
            prev_status = mem.validity_status.value if hasattr(mem.validity_status, "value") else str(mem.validity_status)
            mem.validity_status = MemoryValidityStatus.OUTDATED
            mem.confidence = max(0.1, round(mem.confidence * 0.7, 4))

            history = list(mem.evolution_history or [])
            history.append({
                "timestamp": now.isoformat(),
                "evolution_type": PatternEvolutionType.OUTDATED.value,
                "previous_status": prev_status,
                "new_status": MemoryValidityStatus.OUTDATED.value,
                "previous_confidence": mem.confidence,
                "new_confidence": mem.confidence,
                "reason": f"No corroborating observations in past {threshold_days} days.",
                "evidence_summary": {"threshold_days": threshold_days, "last_observed": mem.last_observed_at.isoformat()},
            })
            mem.evolution_history = history
            updated_memories.append(mem)

        if updated_memories:
            db.flush()
        return updated_memories

    # -----------------------------------------------------------------------
    # Profile Grounding & Synthesis from Core Behavioral Telemetry
    # -----------------------------------------------------------------------

    @staticmethod
    def synthesize_memories_from_behavioral_profile(
        db: Session,
        user_id: uuid.UUID,
    ) -> MemorySynthesisResponse:
        """
        Extracts, synthesizes, and updates long-term behavioral memories from the authoritative
        UserBehavioralProfile (Phase 4.2), UserFocusWindow (Phase 4.3), UserIntervention (Phase 4.5),
        and recommendation feedback.
        """
        prefs = BehavioralMemoryService.get_or_create_preferences(db, user_id)
        disabled_cats = set(prefs.disabled_categories or [])

        created = 0
        reinforced = 0
        weakened = 0
        messages: List[str] = []

        # 1. Inspect existing UserBehavioralProfile
        profile = db.execute(
            select(UserBehavioralProfile).where(UserBehavioralProfile.user_id == user_id)
        ).scalar_one_or_none()

        if profile:
            focus_dim = profile.focus_dimension or {}
            interruption_dim = profile.interruption_dimension or {}
            task_dim = profile.task_completion_dimension or {}
            context_dim = profile.context_dimension or {}
            baselines = profile.baselines or {}

            # Synthesize Focus Pattern Memory
            if MemoryCategory.FOCUS_PATTERNS.value not in disabled_cats:
                typ_duration = focus_dim.get("typical_session_duration_minutes", {}).get("observed_value")
                stability = focus_dim.get("focus_stability_score", {}).get("observed_value")
                if typ_duration:
                    mem_title = f"Typical Focus Session Duration: ~{int(float(typ_duration))} mins"
                    existing = db.execute(
                        select(BehavioralMemory).where(
                            BehavioralMemory.user_id == user_id,
                            BehavioralMemory.category == MemoryCategory.FOCUS_PATTERNS,
                            BehavioralMemory.title == mem_title,
                        )
                    ).scalar_one_or_none()
                    if not existing:
                        BehavioralMemoryService.create_memory(
                            db=db,
                            user_id=user_id,
                            payload=BehavioralMemoryCreate(
                                category=MemoryCategory.FOCUS_PATTERNS,
                                title=mem_title,
                                description=(
                                    f"Observed focus sessions cluster around {float(typ_duration):.1f} minutes "
                                    f"with stability rating {float(stability or 50):.1f}/100."
                                ),
                                source_type=MemorySourceType.FREQUENTLY_OBSERVED_BEHAVIOR,
                                confidence=min(0.95, float(profile.global_confidence_score or 0.8)),
                                supporting_evidence={
                                    "typical_duration": typ_duration,
                                    "stability_score": stability,
                                    "source": "user_behavioral_profiles.focus_dimension",
                                },
                            ),
                        )
                        created += 1
                    else:
                        BehavioralMemoryService.reinforce_pattern(
                            db=db,
                            memory=existing,
                            supporting_evidence={"updated_from_profile": True, "duration": typ_duration},
                        )
                        reinforced += 1

            # Synthesize Recovery Pattern Memory
            if MemoryCategory.RECOVERY_PATTERNS.value not in disabled_cats:
                isi = interruption_dim.get("interruption_sensitivity_index", {}).get("observed_value")
                rec_dist = interruption_dim.get("recovery_duration_distribution", {}).get("observed_value")
                if isi is not None:
                    mem_title = f"Interruption Sensitivity Profile (ISI: {float(isi):.2f})"
                    existing = db.execute(
                        select(BehavioralMemory).where(
                            BehavioralMemory.user_id == user_id,
                            BehavioralMemory.category == MemoryCategory.RECOVERY_PATTERNS,
                            BehavioralMemory.title == mem_title,
                        )
                    ).scalar_one_or_none()
                    if not existing:
                        BehavioralMemoryService.create_memory(
                            db=db,
                            user_id=user_id,
                            payload=BehavioralMemoryCreate(
                                category=MemoryCategory.RECOVERY_PATTERNS,
                                title=mem_title,
                                description=(
                                    f"User exhibits an Interruption Sensitivity Index of {float(isi):.2f} "
                                    f"with median recovery delay parameters grounded in empirical sessions."
                                ),
                                source_type=MemorySourceType.MODEL_INFERRED_PATTERN,
                                confidence=0.82,
                                supporting_evidence={"isi": isi, "recovery_distribution": rec_dist},
                            ),
                        )
                        created += 1

            # Synthesize Productivity / Task Management Preferences
            if MemoryCategory.PRODUCTIVITY_PATTERNS.value not in disabled_cats:
                comp_rate = task_dim.get("task_completion_rate", {}).get("observed_value")
                postpone = task_dim.get("postponement_frequency", {}).get("observed_value")
                if comp_rate is not None:
                    mem_title = f"Baseline Task Completion Velocity ({float(comp_rate)*100:.0f}%)"
                    existing = db.execute(
                        select(BehavioralMemory).where(
                            BehavioralMemory.user_id == user_id,
                            BehavioralMemory.category == MemoryCategory.PRODUCTIVITY_PATTERNS,
                            BehavioralMemory.title == mem_title,
                        )
                    ).scalar_one_or_none()
                    if not existing:
                        BehavioralMemoryService.create_memory(
                            db=db,
                            user_id=user_id,
                            payload=BehavioralMemoryCreate(
                                category=MemoryCategory.PRODUCTIVITY_PATTERNS,
                                title=mem_title,
                                description=(
                                    f"Task completion rate averages {float(comp_rate)*100:.1f}% "
                                    f"with an average postponement frequency of {float(postpone or 0.0):.2f} shifts/task."
                                ),
                                source_type=MemorySourceType.FREQUENTLY_OBSERVED_BEHAVIOR,
                                confidence=0.85,
                                supporting_evidence={"completion_rate": comp_rate, "postponement_freq": postpone},
                            ),
                        )
                        created += 1

            # Synthesize Context Associations
            if MemoryCategory.CONTEXT_ASSOCIATIONS.value not in disabled_cats:
                overhead = context_dim.get("context_switch_overhead_seconds", {}).get("observed_value")
                if overhead:
                    mem_title = f"App Context Switch Resumption Overhead (~{int(float(overhead))}s)"
                    existing = db.execute(
                        select(BehavioralMemory).where(
                            BehavioralMemory.user_id == user_id,
                            BehavioralMemory.category == MemoryCategory.CONTEXT_ASSOCIATIONS,
                            BehavioralMemory.title == mem_title,
                        )
                    ).scalar_one_or_none()
                    if not existing:
                        BehavioralMemoryService.create_memory(
                            db=db,
                            user_id=user_id,
                            payload=BehavioralMemoryCreate(
                                category=MemoryCategory.CONTEXT_ASSOCIATIONS,
                                title=mem_title,
                                description=f"Median latency to re-engage after desktop application transitions is {float(overhead):.1f}s.",
                                source_type=MemorySourceType.MODEL_INFERRED_PATTERN,
                                confidence=0.80,
                                supporting_evidence={"switch_overhead_seconds": overhead},
                            ),
                        )
                        created += 1

            messages.append("Synthesized behavioral patterns from UserBehavioralProfile dimensions.")

        # 2. Inspect UserFocusWindow (Phase 4.3)
        if MemoryCategory.FOCUS_PATTERNS.value not in disabled_cats:
            windows = db.execute(
                select(UserFocusWindow).where(
                    UserFocusWindow.user_id == user_id,
                    UserFocusWindow.is_active.is_(True),
                )
            ).scalars().all()
            for win in windows:
                dow_name = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][win.day_of_week] if win.day_of_week is not None else "Daily"
                time_range = f"{win.start_time.strftime('%H:%M')} - {win.end_time.strftime('%H:%M')}"
                mem_title = f"Optimal Focus Window: {dow_name} {time_range}"
                existing = db.execute(
                    select(BehavioralMemory).where(
                        BehavioralMemory.user_id == user_id,
                        BehavioralMemory.category == MemoryCategory.FOCUS_PATTERNS,
                        BehavioralMemory.title == mem_title,
                    )
                ).scalar_one_or_none()
                if not existing:
                    BehavioralMemoryService.create_memory(
                        db=db,
                        user_id=user_id,
                        payload=BehavioralMemoryCreate(
                            category=MemoryCategory.FOCUS_PATTERNS,
                            title=mem_title,
                            description=(
                                f"High-quality recurrent focus interval discovered on {dow_name} ({time_range}) "
                                f"with quality score {win.quality_score:.1f}/100 and {win.completion_rate*100:.0f}% completion rate."
                            ),
                            source_type=MemorySourceType.MODEL_INFERRED_PATTERN,
                            confidence=min(0.96, win.quality_score / 100.0),
                            supporting_evidence={
                                "focus_window_id": str(win.id),
                                "quality_score": win.quality_score,
                                "duration_minutes": win.duration_minutes,
                            },
                        ),
                    )
                    created += 1
                else:
                    BehavioralMemoryService.reinforce_pattern(
                        db=db,
                        memory=existing,
                        supporting_evidence={"quality_score": win.quality_score},
                    )
                    reinforced += 1
            if windows:
                messages.append(f"Grounding {len(windows)} active focus windows into Focus Patterns.")

        # 3. Inspect UserIntervention & RecommendationFeedback (Phase 2 & Phase 4.5)
        # Successful Interventions
        if MemoryCategory.SUCCESSFUL_INTERVENTIONS.value not in disabled_cats:
            accepted_intvs = db.execute(
                select(UserIntervention).where(
                    UserIntervention.user_id == user_id,
                    UserIntervention.lifecycle_status.in_(["ACCEPTED", "COMPLETED"]),
                )
            ).scalars().all()
            if accepted_intvs:
                # Group by intervention type
                intv_counts: Dict[str, int] = {}
                for it in accepted_intvs:
                    intv_counts[it.intervention_type] = intv_counts.get(it.intervention_type, 0) + 1

                for it_type, count in intv_counts.items():
                    mem_title = f"Receptive Intervention: {it_type.replace('_', ' ').title()}"
                    existing = db.execute(
                        select(BehavioralMemory).where(
                            BehavioralMemory.user_id == user_id,
                            BehavioralMemory.category == MemoryCategory.SUCCESSFUL_INTERVENTIONS,
                            BehavioralMemory.title == mem_title,
                        )
                    ).scalar_one_or_none()
                    if not existing:
                        BehavioralMemoryService.create_memory(
                            db=db,
                            user_id=user_id,
                            payload=BehavioralMemoryCreate(
                                category=MemoryCategory.SUCCESSFUL_INTERVENTIONS,
                                title=mem_title,
                                description=f"User positively accepts {it_type} interventions (accepted {count} times).",
                                source_type=MemorySourceType.FREQUENTLY_OBSERVED_BEHAVIOR,
                                confidence=min(0.95, 0.7 + count * 0.05),
                                supporting_evidence={"intervention_type": it_type, "accepted_count": count},
                            ),
                        )
                        created += 1
                    else:
                        BehavioralMemoryService.reinforce_pattern(
                            db=db,
                            memory=existing,
                            supporting_evidence={"accepted_count": count},
                        )
                        reinforced += 1

        # Unsuccessful Interventions
        if MemoryCategory.UNSUCCESSFUL_INTERVENTIONS.value not in disabled_cats:
            dismissed_intvs = db.execute(
                select(UserIntervention).where(
                    UserIntervention.user_id == user_id,
                    UserIntervention.lifecycle_status == "DISMISSED",
                )
            ).scalars().all()
            if dismissed_intvs:
                dismiss_counts: Dict[str, int] = {}
                for it in dismissed_intvs:
                    dismiss_counts[it.intervention_type] = dismiss_counts.get(it.intervention_type, 0) + 1

                for it_type, count in dismiss_counts.items():
                    if count >= 2:  # Only establish if observed repeatedly
                        mem_title = f"Friction Intervention: {it_type.replace('_', ' ').title()}"
                        existing = db.execute(
                            select(BehavioralMemory).where(
                                BehavioralMemory.user_id == user_id,
                                BehavioralMemory.category == MemoryCategory.UNSUCCESSFUL_INTERVENTIONS,
                                BehavioralMemory.title == mem_title,
                            )
                        ).scalar_one_or_none()
                        if not existing:
                            BehavioralMemoryService.create_memory(
                                db=db,
                                user_id=user_id,
                                payload=BehavioralMemoryCreate(
                                    category=MemoryCategory.UNSUCCESSFUL_INTERVENTIONS,
                                    title=mem_title,
                                    description=f"User frequently dismisses {it_type} prompts (dismissed {count} times). Reduce frequency.",
                                    source_type=MemorySourceType.FREQUENTLY_OBSERVED_BEHAVIOR,
                                    confidence=min(0.92, 0.7 + count * 0.05),
                                    supporting_evidence={"intervention_type": it_type, "dismissed_count": count},
                                ),
                            )
                            created += 1

        # 4. Long-Term Goals
        if MemoryCategory.LONG_TERM_GOALS.value not in disabled_cats:
            goals = db.execute(
                select(Goal).where(Goal.user_id == user_id, Goal.status == "ACTIVE")
            ).scalars().all()
            for g in goals:
                mem_title = f"Active Goal: {g.title}"
                existing = db.execute(
                    select(BehavioralMemory).where(
                        BehavioralMemory.user_id == user_id,
                        BehavioralMemory.category == MemoryCategory.LONG_TERM_GOALS,
                        BehavioralMemory.title == mem_title,
                    )
                ).scalar_one_or_none()
                if not existing:
                    BehavioralMemoryService.create_memory(
                        db=db,
                        user_id=user_id,
                        payload=BehavioralMemoryCreate(
                            category=MemoryCategory.LONG_TERM_GOALS,
                            title=mem_title,
                            description=f"Long-term objective in category {g.category} (progress: {g.progress_pct:.0f}%).",
                            source_type=MemorySourceType.EXPLICIT_USER_INSTRUCTION,
                            confidence=1.0,
                            supporting_evidence={"goal_id": str(g.id), "progress": g.progress_pct},
                        ),
                    )
                    created += 1

        # 5. Evaluate and transition outdated memories
        outdated_mems = BehavioralMemoryService.evaluate_outdated_patterns(db, user_id)
        if outdated_mems:
            messages.append(f"Marked {len(outdated_mems)} dormant patterns as outdated.")

        total_active = db.scalar(
            select(func.count(BehavioralMemory.id)).where(
                BehavioralMemory.user_id == user_id,
                BehavioralMemory.is_disabled.is_(False),
                BehavioralMemory.validity_status.in_([
                    MemoryValidityStatus.ACTIVE,
                    MemoryValidityStatus.EMERGING,
                    MemoryValidityStatus.STRENGTHENING,
                ]),
            )
        ) or 0

        return MemorySynthesisResponse(
            created_memories_count=created,
            reinforced_memories_count=reinforced,
            weakened_memories_count=weakened,
            outdated_memories_count=len(outdated_mems),
            total_active_memories=total_active,
            synthesis_messages=messages,
        )

    # -----------------------------------------------------------------------
    # Temporal Summaries (Weekly / Monthly)
    # -----------------------------------------------------------------------

    @staticmethod
    def generate_temporal_summary(
        db: Session,
        user_id: uuid.UUID,
        period_type: str = "WEEKLY",
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
    ) -> BehavioralTemporalSummary:
        """
        Generates and stores a structured temporal roll-up of behavioral memory evolution,
        emerging tendencies, strengthening habits, and outdated patterns.
        """
        now = datetime.now(timezone.utc)
        if period_type == "MONTHLY":
            start = period_start or (now - timedelta(days=30))
        else:
            period_type = "WEEKLY"
            start = period_start or (now - timedelta(days=7))
        end = period_end or now

        # Query all memories for user
        memories = db.execute(
            select(BehavioralMemory).where(BehavioralMemory.user_id == user_id)
        ).scalars().all()

        emerging_ids: List[str] = []
        strengthened_ids: List[str] = []
        weakened_ids: List[str] = []
        outdated_ids: List[str] = []

        for m in memories:
            m_id = str(m.id)
            if m.validity_status == MemoryValidityStatus.EMERGING:
                emerging_ids.append(m_id)
            elif m.validity_status in (MemoryValidityStatus.STRENGTHENING, MemoryValidityStatus.ACTIVE) and m.reinforcement_count > 0:
                strengthened_ids.append(m_id)
            elif m.validity_status in (MemoryValidityStatus.WEAKENING, MemoryValidityStatus.CONTRADICTED):
                weakened_ids.append(m_id)
            elif m.validity_status == MemoryValidityStatus.OUTDATED:
                outdated_ids.append(m_id)

        # Retrieve profile baseline
        profile = db.execute(
            select(UserBehavioralProfile).where(UserBehavioralProfile.user_id == user_id)
        ).scalar_one_or_none()
        baselines = profile.baselines if profile else {}

        summary_metrics = {
            "total_memories": len(memories),
            "emerging_count": len(emerging_ids),
            "strengthened_count": len(strengthened_ids),
            "weakened_count": len(weakened_ids),
            "outdated_count": len(outdated_ids),
            "baseline_focus_duration": baselines.get("median_focus_duration_minutes", 0),
            "baseline_recovery_seconds": baselines.get("typical_recovery_duration_seconds", 0),
            "baseline_bfi": baselines.get("baseline_behavioral_friction_index", 0),
        }

        narrative = (
            f"{period_type.capitalize()} Behavioral Summary ({start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}): "
            f"{len(strengthened_ids)} patterns reinforced, {len(emerging_ids)} newly emerging, "
            f"and {len(outdated_ids)} dormant patterns retired."
        )

        summary_record = BehavioralTemporalSummary(
            user_id=user_id,
            period_type=period_type,
            period_start=start,
            period_end=end,
            summary_metrics=summary_metrics,
            emerging_pattern_ids=emerging_ids,
            strengthened_pattern_ids=strengthened_ids,
            weakened_pattern_ids=weakened_ids,
            outdated_pattern_ids=outdated_ids,
            narrative_summary=narrative,
        )
        db.add(summary_record)
        db.flush()
        return summary_record

    @staticmethod
    def get_temporal_summaries(
        db: Session,
        user_id: uuid.UUID,
        limit: int = 10,
    ) -> List[BehavioralTemporalSummary]:
        return list(
            db.execute(
                select(BehavioralTemporalSummary)
                .where(BehavioralTemporalSummary.user_id == user_id)
                .order_by(BehavioralTemporalSummary.period_end.desc())
                .limit(limit)
            ).scalars().all()
        )

    # -----------------------------------------------------------------------
    # Comprehensive Overview
    # -----------------------------------------------------------------------

    @staticmethod
    def get_memory_overview(
        db: Session,
        user_id: uuid.UUID,
    ) -> BehavioralMemoryOverviewRead:
        memories = db.execute(
            select(BehavioralMemory).where(
                BehavioralMemory.user_id == user_id,
                BehavioralMemory.is_disabled.is_(False),
            )
        ).scalars().all()

        profile = db.execute(
            select(UserBehavioralProfile).where(UserBehavioralProfile.user_id == user_id)
        ).scalar_one_or_none()

        category_counts: Dict[str, int] = {}
        source_type_counts: Dict[str, int] = {}
        status_counts: Dict[str, int] = {}

        active_count = 0
        emerging_count = 0
        strengthening_count = 0
        weakening_count = 0
        outdated_count = 0
        contradicted_count = 0
        explicit_count = 0
        user_corrected_count = 0
        recent_evolutions: List[Dict[str, Any]] = []

        for m in memories:
            cat_name = m.category.value if hasattr(m.category, "value") else str(m.category)
            src_name = m.source_type.value if hasattr(m.source_type, "value") else str(m.source_type)
            st_name = m.validity_status.value if hasattr(m.validity_status, "value") else str(m.validity_status)

            category_counts[cat_name] = category_counts.get(cat_name, 0) + 1
            source_type_counts[src_name] = source_type_counts.get(src_name, 0) + 1
            status_counts[st_name] = status_counts.get(st_name, 0) + 1

            if m.validity_status == MemoryValidityStatus.ACTIVE:
                active_count += 1
            elif m.validity_status == MemoryValidityStatus.EMERGING:
                emerging_count += 1
            elif m.validity_status == MemoryValidityStatus.STRENGTHENING:
                strengthening_count += 1
            elif m.validity_status == MemoryValidityStatus.WEAKENING:
                weakening_count += 1
            elif m.validity_status == MemoryValidityStatus.OUTDATED:
                outdated_count += 1
            elif m.validity_status == MemoryValidityStatus.CONTRADICTED:
                contradicted_count += 1

            if m.source_type == MemorySourceType.EXPLICIT_USER_INSTRUCTION:
                explicit_count += 1

            if m.is_user_corrected:
                user_corrected_count += 1

            for ev in (m.evolution_history or [])[-3:]:
                recent_evolutions.append({
                    "memory_id": str(m.id),
                    "memory_title": m.title,
                    "category": cat_name,
                    **ev,
                })

        recent_evolutions.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        recent_mems = list(
            db.execute(
                select(BehavioralMemory)
                .where(BehavioralMemory.user_id == user_id, BehavioralMemory.is_disabled.is_(False))
                .order_by(BehavioralMemory.updated_at.desc())
                .limit(10)
            ).scalars().all()
        )

        return BehavioralMemoryOverviewRead(
            total_memories=len(memories),
            active_patterns_count=active_count,
            emerging_patterns_count=emerging_count,
            strengthening_patterns_count=strengthening_count,
            weakening_patterns_count=weakening_count,
            outdated_patterns_count=outdated_count,
            contradicted_patterns_count=contradicted_count,
            explicit_instructions_count=explicit_count,
            user_corrected_count=user_corrected_count,
            category_counts=category_counts,
            source_type_counts=source_type_counts,
            status_counts=status_counts,
            primary_profile_status=profile.global_pattern_status if profile else "NOT_INITIALIZED",
            primary_profile_confidence=profile.global_confidence_score if profile else 0.0,
            recent_memories=[BehavioralMemoryRead.model_validate(m) for m in recent_mems],
            recent_evolutions=recent_evolutions[:20],
        )
