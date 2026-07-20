"""
Core SuprocAgent Orchestrator.
Manages the complete 8-step agentic lifecycle:
1. Requirement Understanding
2. Execution Planning
3. Dataset Search & Inspection
4. Multi-Factor Match Scoring & Ranking
5. Deterministic Ground-Truth Verification
6. Self-Correction Failure Recovery Loop (Max 3 attempts)
7. Outreach Drafting
8. Human Approval Gate
"""

import re
from typing import List, Dict, Any, Optional
from src.suproc.models import (
    StructuredRequirement, ExecutionPlan, MatchResult, ValidationReport, AgentOutput
)
from src.suproc.tools import SuprocTools
from src.suproc.validator import VerificationEngine
from src.suproc.llm_client import OllamaClient

class SuprocAgent:
    def __init__(
        self,
        tools: Optional[SuprocTools] = None,
        validator: Optional[VerificationEngine] = None,
        llm_client: Optional[OllamaClient] = None
    ):
        self.tools = tools or SuprocTools()
        self.validator = validator or VerificationEngine(tools=self.tools)
        self.llm_client = llm_client or OllamaClient()

    def process_request(self, user_query: str) -> AgentOutput:
        """
        Executes the end-to-end agent workflow.
        """
        trace = []

        # Step 0: Security Scan on User Input (Prompt Injection Defense)
        if re.search(r'IGNORE.*VALIDATION|BYPASS.*RULE|DISREGARD.*CONSTRAINT|SYSTEM OVERRIDE', user_query, re.IGNORECASE):
            trace.append({"step": "Security Check", "status": "FLAGGED", "details": "Prompt injection attempt to bypass validation rules detected."})
            return AgentOutput(
                interpreted_requirement={"raw_query": user_query, "objective": "BLOCKED"},
                hard_constraints={},
                optional_preferences={},
                plan_followed=["Security scan flagged request."],
                recommended_matches=[],
                evidence_supporting_matches=[],
                match_score_breakdowns=[],
                constraints_checked=["Security Rule Enforcement"],
                missing_information=[],
                risks_or_uncertainties=["Request attempted to bypass agent safety rules."],
                recommended_next_action="Reject query and notify administrator.",
                draft_outreach_message="",
                validation_status="FAILED",
                requires_human_approval=True,
                correction_attempts_made=0,
                execution_trace=trace
            )

        # Step 1: Requirement Understanding
        req = self.llm_client.parse_requirement(user_query)
        trace.append({
            "step": "Requirement Understanding",
            "status": "SUCCESS",
            "interpreted": req.to_dict()
        })

        # Step 2: Planning
        plan = self.llm_client.create_execution_plan(req)
        trace.append({
            "step": "Execution Planning",
            "status": "SUCCESS",
            "steps": plan.steps
        })

        # Self-Correction Loop (Up to 3 Attempts)
        max_attempts = 3
        excluded_ids = set()
        correction_attempts = 0
        final_valid_matches: List[MatchResult] = []
        final_validation_report: Optional[ValidationReport] = None

        while correction_attempts < max_attempts:
            correction_attempts += 1
            trace.append({
                "step": f"Execution Loop Attempt {correction_attempts}",
                "status": "RUNNING",
                "excluded_entities": list(excluded_ids)
            })

            # Step 3: Search candidates from dataset
            location_filter = req.hard_constraints.locations[0] if req.hard_constraints.locations else ""
            raw_candidates = self.tools.search_entities(
                query=req.objective,
                entity_type=req.entity_type,
                location=location_filter,
                limit=100
            )

            # Fallback broader search if initial query returned few records
            if len(raw_candidates) < 5:
                broad_candidates = self.tools.search_entities(
                    query="",
                    entity_type=req.entity_type,
                    limit=100
                )
                existing_ids = {c["id"] for c in raw_candidates}
                for bc in broad_candidates:
                    if bc["id"] not in existing_ids:
                        raw_candidates.append(bc)

            # Exclude entities flagged in previous validation iterations
            eligible_candidates = [c for c in raw_candidates if c["id"] not in excluded_ids]

            # Step 4: Hard Constraint Filtering
            filtered_candidates = self.tools.filter_by_constraints(eligible_candidates, req.hard_constraints)

            # Step 5: Scoring and Ranking
            scored_matches: List[MatchResult] = []
            for item in filtered_candidates:
                score_bd = self.tools.calculate_match_score(item, req.objective, req.hard_constraints)
                scored_matches.append(MatchResult(
                    entity_id=item["id"],
                    name=item["name"],
                    entity_type=item.get("entity_type", req.entity_type),
                    location=f"{item.get('location')}, {item.get('state')}",
                    score_breakdown=score_bd,
                    matched_capabilities=item.get("certifications", []),
                    raw_record=item
                ))

            # Sort by total score descending
            scored_matches.sort(key=lambda m: m.score_breakdown.total_score, reverse=True)
            top_matches = scored_matches[:req.requested_results]

            # Step 6: Verification
            val_report = self.validator.validate_recommendations(top_matches, req)
            final_validation_report = val_report

            if val_report.is_valid:
                trace.append({
                    "step": f"Verification Attempt {correction_attempts}",
                    "status": "PASSED",
                    "valid_matches_count": len(val_report.valid_entity_ids)
                })
                final_valid_matches = top_matches
                break
            else:
                trace.append({
                    "step": f"Verification Attempt {correction_attempts}",
                    "status": "FAILED",
                    "failures": val_report.failed_checks,
                    "rejected_entities": val_report.rejected_entities
                })
                # Add rejected entities to exclusion list for next attempt
                for rej_id in val_report.rejected_entities.keys():
                    excluded_ids.add(rej_id)

                # Keep only valid matches from this pass
                valid_top = [m for m in top_matches if m.entity_id in val_report.valid_entity_ids]
                if valid_top:
                    final_valid_matches = valid_top

        # Step 7: Draft Outreach & Action Preparation
        outreach_msg = ""
        recommended_action_str = ""
        if final_valid_matches:
            top_entity_id = final_valid_matches[0].entity_id
            outreach_msg = self.tools.draft_outreach(top_entity_id, req.objective)
            rec_ids = ", ".join([m.entity_id for m in final_valid_matches])
            recommended_action_str = f"Send procurement enquiry to supplier(s) {rec_ids}."
        else:
            recommended_action_str = "No valid records satisfy all hard constraints. Perform broader market research."
            outreach_msg = "N/A - No suitable valid suppliers matched your hard constraints."

        # Step 8: Build Final Structured Output
        recommended_matches_data = []
        evidence_data = []
        score_breakdowns_data = []

        for match in final_valid_matches:
            recommended_matches_data.append({
                "id": match.entity_id,
                "name": match.name,
                "type": match.entity_type,
                "location": match.location,
                "total_score": match.score_breakdown.total_score
            })
            evidence_data.append({
                "id": match.entity_id,
                "evidence": match.score_breakdown.evidence
            })
            score_breakdowns_data.append({
                "id": match.entity_id,
                "breakdown": match.score_breakdown.to_dict()
            })

        missing_info = []
        if not req.hard_constraints.max_budget:
            missing_info.append("Budget constraint was not specified in request.")
        if not req.hard_constraints.required_skills and req.entity_type == "professional":
            missing_info.append("Specific certification level for professional was omitted.")

        val_status_label = "PASSED" if (final_validation_report and final_validation_report.is_valid) else ("CORRECTED" if final_valid_matches else "NO_MATCH")

        return AgentOutput(
            interpreted_requirement=req.to_dict(),
            hard_constraints=req.hard_constraints.to_dict(),
            optional_preferences=req.preferences.to_dict(),
            plan_followed=plan.steps,
            recommended_matches=recommended_matches_data,
            evidence_supporting_matches=evidence_data,
            match_score_breakdowns=score_breakdowns_data,
            constraints_checked=[
                "Ground-truth existence in SQLite dataset",
                "100% hard constraint certification compliance",
                "Delivery lead time limits",
                "Minimum unit capacity requirements",
                "Location & regional boundary matching",
                "Duplicate entity detection",
                "Prompt-injection payload security scan"
            ],
            missing_information=missing_info,
            risks_or_uncertainties=[
                "Lead times subject to local courier availability.",
                "Prices subject to raw material market fluctuation."
            ] if final_valid_matches else ["No entity in dataset satisfied all strict hard constraints."],
            recommended_next_action=recommended_action_str,
            draft_outreach_message=outreach_msg,
            validation_status=val_status_label,
            requires_human_approval=True,
            correction_attempts_made=correction_attempts,
            execution_trace=trace
        )
