"""
LLM Client Interface for SUPROC.
Connects to Ollama REST API (Qwen3 4B / Qwen3 1.7B / Qwen2.5) with automatic fallback parser
to ensure zero-downtime execution and deterministic test verification.
"""

import json
import urllib.request
import urllib.error
import re
from typing import Dict, Any, Optional
from src.suproc.models import StructuredRequirement, HardConstraints, OptionalPreferences, ExecutionPlan

OLLAMA_API_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "qwen3:4b"

class OllamaClient:
    def __init__(self, model_name: str = DEFAULT_MODEL, host_url: str = OLLAMA_API_URL):
        self.model_name = model_name
        self.host_url = host_url

    def _call_ollama(self, prompt: str, system_prompt: str = "") -> Optional[str]:
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "format": "json"
        }
        try:
            req = urllib.request.Request(
                self.host_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=8) as response:
                if response.status == 200:
                    res_body = json.loads(response.read().decode("utf-8"))
                    return res_body.get("response", "")
        except Exception:
            return None
        return None

    def parse_requirement(self, raw_query: str) -> StructuredRequirement:
        """
        Parses natural language query into a StructuredRequirement object.
        Uses Ollama if running, otherwise uses high-accuracy heuristic natural language extractor.
        """
        system_prompt = (
            "You are a business requirement parsing AI. Convert the user's business request into JSON matching: "
            "objective, entity_type (supplier/business/professional/opportunity), hard_constraints "
            "(locations, certifications, minimum_capacity, maximum_delivery_days), preferences, requested_results."
        )
        
        response_str = self._call_ollama(raw_query, system_prompt)
        if response_str:
            try:
                data = json.loads(response_str)
                hc = data.get("hard_constraints", {})
                pref = data.get("preferences", {})
                return StructuredRequirement(
                    objective=data.get("objective", raw_query),
                    entity_type=data.get("entity_type", "supplier"),
                    hard_constraints=HardConstraints(
                        locations=hc.get("locations", []),
                        certifications=hc.get("certifications", []),
                        minimum_capacity=hc.get("minimum_capacity"),
                        maximum_delivery_days=hc.get("maximum_delivery_days"),
                        max_budget=hc.get("max_budget"),
                        required_skills=hc.get("required_skills", [])
                    ),
                    preferences=OptionalPreferences(
                        sustainable_materials=pref.get("sustainable_materials", False),
                        startup_friendly=pref.get("startup_friendly", False)
                    ),
                    requested_results=data.get("requested_results", 3),
                    raw_query=raw_query
                )
            except Exception:
                pass

        # Fallback Engine (Robust NLP pattern extraction)
        return self._heuristic_parse(raw_query)

    def _heuristic_parse(self, query: str) -> StructuredRequirement:
        q_lower = query.lower()

        # Entity type detection
        entity_type = "supplier"
        if any(w in q_lower for w in ["professional", "auditor", "consultant", "lawyer", "architect", "expert", "agent"]):
            entity_type = "professional"
        elif any(w in q_lower for w in ["rfp", "bounty", "project", "opportunity", "order requirement"]):
            entity_type = "opportunity"
        elif "business" in q_lower:
            entity_type = "business"

        # Requested count
        requested_results = 3
        count_match = re.search(r'\b(one|two|three|four|five|1|2|3|4|5)\b', q_lower)
        if count_match:
            word_map = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
            val = count_match.group(1)
            requested_results = word_map.get(val, int(val) if val.isdigit() else 3)

        # Objective extraction
        objective = query
        if "need" in q_lower:
            parts = re.split(r'\bneed\b', query, flags=re.IGNORECASE, maxsplit=1)
            if len(parts) > 1:
                objective = parts[1].strip().split(".")[0]
        elif "find" in q_lower:
            parts = re.split(r'\bfind\b', query, flags=re.IGNORECASE, maxsplit=1)
            if len(parts) > 1:
                objective = parts[1].strip().split(".")[0]

        # Location extraction
        locations = []
        if "south india" in q_lower:
            locations.append("South India")
        for state in ["karnataka", "tamil nadu", "kerala", "andhra pradesh", "telangana", "bengaluru", "chennai", "hyderabad", "mumbai", "delhi"]:
            if state in q_lower and state.title() not in locations:
                locations.append(state.title())

        # Hard constraints extraction
        certifications = []
        if "food-grade" in q_lower or "food grade" in q_lower:
            certifications.append("food-grade")
        if "iso" in q_lower:
            certifications.append("ISO")

        min_capacity = None
        cap_match = re.search(r'(\d+[\d,]*)\s*(units|capacity|order|pieces|boxes)', q_lower)
        if cap_match:
            num_str = cap_match.group(1).replace(",", "")
            if num_str.isdigit():
                min_capacity = int(num_str)

        max_delivery_days = None
        delivery_match = re.search(r'within\s*(\d+)\s*days', q_lower)
        if delivery_match:
            max_delivery_days = int(delivery_match.group(1))

        # Preferences
        sustainable = "sustainable" in q_lower or "biodegradable" in q_lower or "eco" in q_lower
        startup_friendly = "startup" in q_lower or "small batch" in q_lower

        return StructuredRequirement(
            objective=objective.strip().capitalize(),
            entity_type=entity_type,
            hard_constraints=HardConstraints(
                locations=locations,
                certifications=certifications,
                minimum_capacity=min_capacity,
                maximum_delivery_days=max_delivery_days
            ),
            preferences=OptionalPreferences(
                sustainable_materials=sustainable,
                startup_friendly=startup_friendly
            ),
            requested_results=requested_results,
            raw_query=query
        )

    def create_execution_plan(self, req: StructuredRequirement) -> ExecutionPlan:
        """
        Generates step-by-step execution plan prior to data search.
        """
        steps = [
            f"1. Interpret request and extract hard constraints: Locations={req.hard_constraints.locations}, Certifications={req.hard_constraints.certifications}.",
            f"2. Query dataset for {req.entity_type}s matching category and region.",
            "3. Inspect ground-truth records for capacity, lead times, and required certifications.",
            "4. Filter out any candidate records that fail hard constraints.",
            "5. Compute evidence-backed multi-factor match score for remaining entities.",
            "6. Execute independent verification engine to check ground-truth factual claims.",
            "7. Perform self-correction loop if any recommendation fails verification.",
            "8. Prepare outreach message and flag for human approval."
        ]
        return ExecutionPlan(steps=steps)
