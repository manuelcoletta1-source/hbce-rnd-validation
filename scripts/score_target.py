#!/usr/bin/env python3

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))

def classify(score):
    if score >= 80:
        return "PRIORITY_A"
    if score >= 65:
        return "PRIORITY_B"
    if score >= 50:
        return "WATCH"
    return "REJECT"

def main():
    parser = argparse.ArgumentParser(
        description="Score a potential HBCE R&D Validation target."
    )

    parser.add_argument("name")
    parser.add_argument("--repo", required=True)

    parser.add_argument("--technical-fit", type=int, default=0)
    parser.add_argument("--evidence-surface", type=int, default=0)
    parser.add_argument("--maintainer-activity", type=int, default=0)
    parser.add_argument("--review-need", type=int, default=0)
    parser.add_argument("--commercial-signal", type=int, default=0)

    args = parser.parse_args()

    scores = {
        "technical_fit": clamp(args.technical_fit, 0, 30),
        "evidence_surface": clamp(args.evidence_surface, 0, 25),
        "maintainer_activity": clamp(args.maintainer_activity, 0, 15),
        "review_need": clamp(args.review_need, 0, 20),
        "commercial_signal": clamp(args.commercial_signal, 0, 10)
    }

    total = sum(scores.values())

    result = {
        "name": args.name,
        "repository": args.repo,
        "scores": scores,
        "total_score": total,
        "classification": classify(total),
        "commercial_state": "NOT_CONTACTED"
    }

    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
