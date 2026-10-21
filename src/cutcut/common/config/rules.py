"""Rule values per preset (Rolig/Standard/Energisk) and per-show overrides.

Values come from ``config/defaults/rules.yaml``. Standard follows the specification
(section 5); Rolig and Energisk for ``T`` follow docs/spec/03 and for the rest the
approved proposal in docs/plans/core.md (PL-08, D-046). Field names start with the rule
ID they belong to, so the log and the tuning screen can show where a value comes from.
"""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cutcut.common.models.show import RulesPreset


class RuleParams(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    # Talk (5.3, 5.12)
    T1_vad_threshold: float = Field(ge=0, le=1)
    T1_dominance_db: float = Field(ge=0, le=40)
    T2_confirm_ms: int = Field(ge=100, le=5000)
    T2_mouth_factor: float = Field(gt=0, le=1)
    T3_min_shot_s: float = Field(ge=0.5, le=30)
    T3_guest_extra_s: float = Field(ge=0, le=10)
    T4_ignore_interrupt_s: float = Field(ge=0, le=10)
    T4_host_backchannel_s: float = Field(ge=0, le=10)
    T5_crosstalk_s: float = Field(ge=0.1, le=10)
    T6_pingpong_switches: int = Field(ge=2, le=20)
    T6_window_s: float = Field(ge=2, le=60)
    T7_reaction_after_s: float = Field(ge=3, le=300)
    T7_reaction_shot_s: float = Field(ge=0.5, le=10)
    T8_silence_s: float = Field(ge=0.5, le=60)
    T9_max_wait_pause_ms: int = Field(ge=0, le=2000)
    T12_host_weight: float = Field(ge=1, le=2)
    # Bird's-eye (5.4)
    B1_open_s: float = Field(ge=0, le=30)
    B1_after_content_s: float = Field(ge=0, le=30)
    B2_crosstalk_s: float = Field(ge=0.1, le=10)
    B3_silence_s: float = Field(ge=0.5, le=60)
    B4_laugh_min_s: float = Field(ge=0.5, le=10)
    B4_laugh_max_s: float = Field(ge=0.5, le=20)
    B5_min_s: float = Field(ge=0.5, le=20)
    B5_max_s: float = Field(ge=0.5, le=30)
    B5_max_share: float = Field(ge=0, le=1)
    B5_min_gap_s: float = Field(ge=0, le=600)
    # Content (5.5)
    CT1_active_s: float = Field(ge=0, le=30)
    CT2_hold_s: float = Field(ge=0.5, le=60)
    CT3_video_max_s: float = Field(ge=1, le=600)
    CT4_return_after_s: float = Field(ge=0.5, le=120)
    CT4_revisit_enabled: bool
    CT4_revisit_s: float = Field(ge=0.5, le=30)
    CT4_revisit_every_s: float = Field(ge=5, le=600)
    # Layouts (5.6)
    L_min_s: float = Field(ge=1, le=60)
    L_no_repeat_s: float = Field(ge=0, le=600)
    L1_speaker_s: float = Field(ge=0, le=60)
    L1_content_recent_s: float = Field(ge=0, le=300)
    L3_window_s: float = Field(ge=1, le=60)
    # Safety (5.7)
    S1_still_s: float = Field(ge=0, le=5)
    S3_min_cut_gap_s: float = Field(ge=1, le=10)  # hard limit, never below 1 s
    S4_audio_lost_s: float = Field(ge=0.5, le=10)
    S6_mix_window_s: float = Field(ge=0.1, le=5)
    # Preview (5.9)
    PV1_min_preview_s: float = Field(ge=0, le=5)
    # Cut points (5.10)
    K1_pause_ms: int = Field(ge=0, le=2000)
    K2_pause_ms: int = Field(ge=0, le=2000)
    K2_falling_pause_ms: int = Field(ge=0, le=2000)
    K3_max_wait_s: float = Field(ge=0.2, le=10)
    K4_pause_ms: int = Field(ge=0, le=2000)
    # Hold and release (5.11)
    H1_factor: float = Field(ge=1, le=5)
    H1_window_s: float = Field(ge=0, le=60)
    H2_no_return_s: float = Field(ge=0, le=60)
    H3_release_s: float = Field(ge=0, le=10)
    # Override (5.2 step 1)
    manual_quiet_s: float = Field(ge=0, le=60)
    # Reactions (5.13, switch)
    R1_speaker_min_s: float = Field(ge=0, le=120)
    R1_shot_s: float = Field(ge=0.5, le=10)
    R2_min_gap_s: float = Field(ge=0, le=600)

    @model_validator(mode="after")
    def _ranges(self) -> Self:
        if self.B4_laugh_min_s > self.B4_laugh_max_s:
            raise ValueError("B4_laugh_min_s must be ≤ B4_laugh_max_s")
        if self.B5_min_s > self.B5_max_s:
            raise ValueError("B5_min_s must be ≤ B5_max_s")
        return self

    def with_overrides(self, overrides: dict[str, float]) -> RuleParams:
        unknown = sorted(set(overrides) - set(type(self).model_fields))
        if unknown:
            raise ValueError(f"unknown rule override(s): {', '.join(unknown)}")
        return type(self).model_validate({**self.model_dump(), **overrides})


class RulePresets(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = 1
    rolig: RuleParams
    standard: RuleParams
    energisk: RuleParams

    def get(self, preset: RulesPreset) -> RuleParams:
        params: RuleParams = getattr(self, preset)
        return params
