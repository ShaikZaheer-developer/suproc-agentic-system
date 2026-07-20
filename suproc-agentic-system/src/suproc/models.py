"""
Data models and schemas for the SUPROC Agentic Search, Matching & Verification System.
Supports both Pydantic v2 and standard Python dataclasses for total environment flexibility.
"""

from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, field, asdict
import json

@dataclass
class HardConstraints:
    locations: List[str] = field(default_factory=list)
    certifications: List[str] = field(default_factory=list)
    minimum_capacity: Optional[int] = None
    maximum_delivery_days: Optional[int] = None
    max_budget: Optional[float] = None
    required_skills: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None and v != []}

@dataclass
class OptionalPreferences:
    sustainable_materials: bool = False
    startup_friendly: bool = False
    min_rating: float = 0.0
    preferred_categories: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class StructuredRequirement:
    objective: str
    entity_type: str  # 'supplier', 'business', 'professional', 'opportunity'
    hard_constraints: HardConstraints = field(default_factory=HardConstraints)
    preferences: OptionalPreferences = field(default_factory=OptionalPreferences)
    requested_results: int = 3
    raw_query: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "objective": self.objective,
            "entity_type": self.entity_type,
            "hard_constraints": self.hard_constraints.to_dict(),
            "preferences": self.preferences.to_dict(),
            "requested_results": self.requested_results,
            "raw_query": self.raw_query
        }

@dataclass
class ExecutionPlan:
    steps: List[str] = field(default_factory=list)

@dataclass
class ScoreBreakdown:
    relevance_score: float = 0.0      # 30% weight
    location_score: float = 0.0       # 20% weight
    constraint_compliance_score: float = 0.0 # 25% weight
    capacity_availability_score: float = 0.0 # 15% weight
    reputation_score: float = 0.0     # 10% weight
    total_score: float = 0.0
    evidence: List[str] = field(default_factory=list)

    def calculate_total(self) -> float:
        self.total_score = round(
            (self.relevance_score * 0.30) +
            (self.location_score * 0.20) +
            (self.constraint_compliance_score * 0.25) +
            (self.capacity_availability_score * 0.15) +
            (self.reputation_score * 0.10),
            2
        )
        return self.total_score

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relevance_30%": self.relevance_score,
            "location_20%": self.location_score,
            "compliance_25%": self.constraint_compliance_score,
            "capacity_15%": self.capacity_availability_score,
            "reputation_10%": self.reputation_score,
            "total_score": self.total_score,
            "evidence": self.evidence
        }

@dataclass
class MatchResult:
    entity_id: str
    name: str
    entity_type: str
    location: str
    score_breakdown: ScoreBreakdown
    matched_capabilities: List[str] = field(default_factory=list)
    missing_capabilities: List[str] = field(default_factory=list)
    raw_record: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ValidationReport:
    is_valid: bool
    passed_checks: List[str] = field(default_factory=list)
    failed_checks: List[str] = field(default_factory=list)
    rejected_entities: Dict[str, str] = field(default_factory=dict) # entity_id -> reason
    valid_entity_ids: List[str] = field(default_factory=list)
    correction_instruction: str = ""
    prompt_injection_detected: bool = False

@dataclass
class AgentOutput:
    interpreted_requirement: Dict[str, Any]
    hard_constraints: Dict[str, Any]
    optional_preferences: Dict[str, Any]
    plan_followed: List[str]
    recommended_matches: List[Dict[str, Any]]
    evidence_supporting_matches: List[Dict[str, Any]]
    match_score_breakdowns: List[Dict[str, Any]]
    constraints_checked: List[str]
    missing_information: List[str]
    risks_or_uncertainties: List[str]
    recommended_next_action: str
    draft_outreach_message: str
    validation_status: str  # 'PASSED', 'FAILED', 'CORRECTED', 'NO_MATCH'
    requires_human_approval: bool = True
    correction_attempts_made: int = 0
    execution_trace: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)
