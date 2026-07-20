"""
Command Line Interface (CLI) for SUPROC Agentic System.
Provides detailed step-by-step execution traces, colored logging, and human approval simulation.
"""

import sys
import json
from src.suproc.agent import SuprocAgent

def print_header(title: str):
    print("\n" + "=" * 80)
    print(f"  {title.upper()}")
    print("=" * 80)

def main():
    print_header("SUPROC Local Agentic Search, Matching & Verification System")
    agent = SuprocAgent()

    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = (
            "We are a sustainable food-packaging startup based in Bengaluru. "
            "We need three suppliers from South India that can provide food-grade "
            "biodegradable containers, support an initial order of 10,000 units and "
            "deliver within 30 days. Explain why each supplier is suitable, "
            "identify any missing information and prepare an outreach message."
        )

    print(f"\n[USER INPUT]: \"{query}\"\n")
    print("--> Executing Agentic Search & Ground-Truth Verification Loop...")

    output = agent.process_request(query)

    print_header("1. Interpreted Business Requirement")
    print(json.dumps(output.interpreted_requirement, indent=2))

    print_header("2. Execution Plan Followed")
    for step in output.plan_followed:
        print(f"  {step}")

    print_header("3. Execution Trace & Verification Loop")
    for tr in output.execution_trace:
        print(f" -> Step: {tr.get('step')} | Status: {tr.get('status')}")
        if "failures" in tr:
            for f in tr["failures"]:
                print(f"    [FAILURE DETECTED]: {f}")

    print_header("4. Recommended Ground-Truth Matches")
    if output.recommended_matches:
        for m in output.recommended_matches:
            print(f"  [ID: {m['id']}] {m['name']} ({m['location']}) - Total Score: {m['total_score']}/100")
    else:
        print("  NO VALID MATCHES SATISFIED ALL HARD CONSTRAINTS.")

    print_header("5. Evidence & Score Breakdown")
    for ev in output.evidence_supporting_matches:
        print(f"\n  Entity {ev['id']} Supporting Evidence:")
        for line in ev['evidence']:
            print(f"   - {line}")

    print_header("6. Recommended Next Action & Approval Status")
    print(f"  Action: {output.recommended_next_action}")
    print(f"  Status: {'AWAITING USER APPROVAL' if output.requires_human_approval else 'AUTO-APPROVED'}")

    print_header("7. Draft Outreach Message")
    print(output.draft_outreach_message)
    print("\n" + "=" * 80 + "\n")

if __name__ == "__main__":
    main()
