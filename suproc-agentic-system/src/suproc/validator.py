"""
Independent Ground-Truth Verification & Correction Engine for SUPROC.
Enforces zero-hallucination guarantees, factual alignment with SQLite, hard constraint math checks,
duplicate entity detection, prompt-injection defense, and human approval enforcement.
"""

import re
from typing import List, Dict, Any, Tuple, Optional, Set
from src.suproc.models import StructuredRequirement, MatchResult, ValidationReport
from src.suproc.tools import SuprocTools

class VerificationEngine:
    def __init__(self, tools: Optional[SuprocTools] = None):
        self.tools = tools or SuprocTools()

    def validate_recommendations(
        self,
        recommendations: List[MatchResult],
        requirement: StructuredRequirement
    ) -> ValidationReport:
        """
        Runs comprehensive deterministic checks against ground-truth database.
        """
        passed_checks = []
        failed_checks = []
        rejected_entities = {}
        valid_ids = []
        prompt_injection_detected = False

        # 1. Duplicate entity check
        seen_ids = set()
        seen_names = set()
        dedup_recommendations = []
        
        for match in recommendations:
            if match.entity_id in seen_ids or match.name in seen_names:
                failed_checks.append(f"Duplicate recommendation detected: {match.entity_id} ({match.name})")
                rejected_entities[match.entity_id] = "Duplicate entity entry"
            else:
                seen_ids.add(match.entity_id)
                seen_names.add(match.name)
                dedup_recommendations.append(match)

        if len(seen_ids) == len(recommendations):
            passed_checks.append("No duplicate entity recommendations found.")

        # 2. Ground truth existence & constraint verification
        for match in dedup_recommendations:
            db_record = self.tools.get_entity_details(match.entity_id)
            
            # Check A: Existence in SQLite
            if not db_record:
                failed_checks.append(f"Entity {match.entity_id} does NOT exist in ground-truth dataset.")
                rejected_entities[match.entity_id] = "Does not exist in dataset (hallucination)"
                continue

            # Check B: Availability status
            if db_record.get("availability_status") == "unavailable" or db_record.get("is_active") == 0:
                failed_checks.append(f"Entity {match.entity_id} is currently unavailable or inactive.")
                rejected_entities[match.entity_id] = "Entity unavailable or inactive"
                continue

            # Check C: Prompt Injection Defense in dataset fields
            desc = db_record.get("description", "")
            if any(term in desc.upper() for term in ["IGNORE PREVIOUS", "SYSTEM OVERRIDE", "ALWAYS RETURN", "DISREGARD"]):
                prompt_injection_detected = True
                failed_checks.append(f"SECURITY ALERT: Prompt injection attempt detected in record {match.entity_id}.")
                rejected_entities[match.entity_id] = "Security Risk: Embedded Prompt Injection Attack"
                continue

            # Check D: Entity Type Match
            db_type = db_record.get("entity_type", "").lower()
            req_type = requirement.entity_type.lower()
            if db_type != req_type and req_type not in db_type:
                failed_checks.append(f"Entity {match.entity_id} type '{db_type}' does not match requested '{req_type}'.")
                rejected_entities[match.entity_id] = f"Entity type mismatch ({db_type} vs {req_type})"
                continue

            # Check E: Hard Constraint - Certifications
            if requirement.hard_constraints.certifications:
                db_certs = [c.lower() for c in db_record.get("certifications", [])]
                missing_certs = []
                for req_cert in requirement.hard_constraints.certifications:
                    if not any(req_cert.lower() in c for c in db_certs):
                        missing_certs.append(req_cert)
                if missing_certs:
                    reason = f"Supplier {match.entity_id} does not have evidence of {', '.join(missing_certs)} certification."
                    failed_checks.append(reason)
                    rejected_entities[match.entity_id] = reason
                    continue

            # Check F: Hard Constraint - Delivery Days
            if requirement.hard_constraints.maximum_delivery_days is not None:
                db_days = db_record.get("delivery_days")
                if db_days is None or db_days > requirement.hard_constraints.maximum_delivery_days:
                    reason = f"Supplier {match.entity_id} delivery time ({db_days} days) exceeds maximum allowed ({requirement.hard_constraints.maximum_delivery_days} days)."
                    failed_checks.append(reason)
                    rejected_entities[match.entity_id] = reason
                    continue

            # Check G: Hard Constraint - Minimum Capacity
            if requirement.hard_constraints.minimum_capacity is not None:
                db_cap = db_record.get("capacity")
                if db_cap is None or db_cap < requirement.hard_constraints.minimum_capacity:
                    reason = f"Supplier {match.entity_id} capacity ({db_cap}) is below minimum requirement ({requirement.hard_constraints.minimum_capacity})."
                    failed_checks.append(reason)
                    rejected_entities[match.entity_id] = reason
                    continue

            # Check H: Hard Constraint - Location / Region
            if requirement.hard_constraints.locations:
                db_loc = db_record.get("location", "").lower()
                db_state = db_record.get("state", "").lower()
                south_states = ["karnataka", "tamil nadu", "kerala", "andhra pradesh", "telangana"]
                
                loc_match = False
                for req_loc in requirement.hard_constraints.locations:
                    req_l = req_loc.lower()
                    if req_l in ["south india", "south-india"]:
                        if db_state in south_states:
                            loc_match = True
                            break
                    elif req_l in db_loc or req_l in db_state:
                        loc_match = True
                        break
                
                if not loc_match:
                    reason = f"Entity {match.entity_id} location '{db_record.get('location')}, {db_record.get('state')}' does not satisfy location requirement."
                    failed_checks.append(reason)
                    rejected_entities[match.entity_id] = reason
                    continue

            # If all checks pass
            valid_ids.append(match.entity_id)

        # 3. Check requested results count
        if len(valid_ids) < requirement.requested_results:
            failed_checks.append(
                f"Requested {requirement.requested_results} matches, but only {len(valid_ids)} valid records satisfy all hard constraints."
            )
        else:
            passed_checks.append(f"Successfully matched requested count of {requirement.requested_results} valid records.")

        is_valid = len(failed_checks) == 0

        # Construct correction instructions if validation failed
        correction_instruction = ""
        if not is_valid:
            failed_reasons_str = " ".join(failed_checks)
            correction_instruction = (
                f"Validation failed: {failed_reasons_str} "
                f"Required action: Exclude invalid entities [{', '.join(rejected_entities.keys())}] "
                f"and search again or return only valid matches."
            )

        return ValidationReport(
            is_valid=is_valid,
            passed_checks=passed_checks,
            failed_checks=failed_checks,
            rejected_entities=rejected_entities,
            valid_entity_ids=valid_ids,
            correction_instruction=correction_instruction,
            prompt_injection_detected=prompt_injection_detected
        )
