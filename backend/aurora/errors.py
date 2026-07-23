"""Structured error model (spec §27).

Every failure carries a machine-readable code plus context, never a bare 500.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

ERROR_CODES = [
    "INVALID_DATASET", "SCHEMA_VALIDATION_FAILED", "SOURCE_DATE_MISSING",
    "SOURCE_DUPLICATE", "ENTITY_RESOLUTION_AMBIGUOUS", "FUTURE_DATA_LEAKAGE",
    "INSUFFICIENT_SOURCE_DIVERSITY", "CLUSTER_UNSTABLE", "TAXONOMY_VERSION_MISSING",
    "RUN_NOT_REPRODUCIBLE", "GROUND_TRUTH_ACCESS_VIOLATION", "INVALID_SCORING_CONFIG",
    "INVALID_CUTOFF_DATE", "NO_HYPOTHESIS_FORMED", "IMPORT_FAILED",
]


@dataclass
class AuroraError(Exception):
    error_code: str
    message: str
    stage: str = ""
    entity_ids: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    run_id: Optional[str] = None
    details: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.error_code not in ERROR_CODES:
            raise ValueError(f"unknown error_code {self.error_code!r}")
        super().__init__(f"[{self.error_code}] {self.message}")

    def to_dict(self) -> dict:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "stage": self.stage,
            "entity_ids": self.entity_ids,
            "source_ids": self.source_ids,
            "run_id": self.run_id,
            "details": self.details,
        }


@dataclass
class RowError:
    """Non-fatal per-row import error (spec §7): bad rows are reported, not
    silently dropped, and never silently accepted."""
    row_number: int
    field: str
    error_code: str
    message: str
    raw_value: str
