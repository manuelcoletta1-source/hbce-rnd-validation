#!/usr/bin/env python3

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUERY_FILE = ROOT / "targets" / "search_queries.json"
OUTPUT_FILE = ROOT / "data" / "github_candidates.json"

TECH_SIGNALS = {
    "robotics": 6,
    "robot": 5,
    "ros2": 6,
    "simulation": 5,
    "simulator": 5,
    "autonomous": 6,
    "agent": 4,
    "execution": 5,
    "provenance": 6,
    "evidence": 6,
    "verification": 5,
    "digital twin": 5,
    "control": 3
}

EVIDENCE_PATH_SIGNALS = {
    "schema": 4,
    "schemas": 4,
    "test": 4,
    "tests": 4,
    "trace": 4,
    "traces": 4,
    "protocol": 4,
    "state_machine": 4,
    "statemachine": 4,
    "adapter": 4,
    "adapters": 4,
    "verification": 4,
    "verifier": 5,
    "evidence": 5
}

def headers():
    h = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "hbce-rnd-validation/0.1"
    }

    token = os.getenv("GITHUB_TOKEN")
    if token:
        h["Authorization"] = f"Bearer {token}"

    return h

def github_get(url):
    req = urllib.request.Request(url, headers=headers())

    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))

def clamp(value, low, high):
    return max(low, min(high, value))

def technical_score(repo):
    text = " ".join([
        repo.get("name") or "",
        repo.get("description") or "",
        " ".join(repo.get("topics") or [])
    ]).lower()

    score = 0
    matched = []

    for signal, points in TECH_SIGNALS.items():
        if signal in text:
            score += points
            matched.append(signal)

    return clamp(score, 0, 30), sorted(set(matched))

def activity_score(pushed_at):
    if not pushed_at:
        return 0

    pushed = datetime.fromisoformat(
        pushed_at.replace("Z", "+00:00")
    )

    days = (
        datetime.now(timezone.utc) - pushed
    ).days

    if days <= 30:
        return 15
    if days <= 90:
        return 12
    if days <= 180:
        return 9
    if days <= 365:
        return 5

    return 1

def fetch_tree(full_name, default_branch):
    branch = urllib.parse.quote(default_branch, safe="")
    url = (
        f"https://api.github.com/repos/{full_name}/"
        f"git/trees/{branch}?recursive=1"
    )

    try:
        data = github_get(url)
    except Exception:
        return []

    return [
        item.get("path", "")
        for item in data.get("tree", [])
        if item.get("type") == "blob"
    ]

def evidence_score(paths):
    lowered = [p.lower() for p in paths]

    score = 0
    matched = []

    for signal, points in EVIDENCE_PATH_SIGNALS.items():
        if any(signal in path for path in lowered):
            score += points
            matched.append(signal)

    return clamp(score, 0, 25), sorted(set(matched))

def classify_observed(score):
    if score >= 60:
        return "OBSERVED_HIGH_FIT"
    if score >= 45:
        return "OBSERVED_MEDIUM_FIT"
    if score >= 30:
        return "OBSERVED_WATCH"

    return "OBSERVED_LOW_FIT"

def discover(limit_per_query):
    config = json.loads(
        QUERY_FILE.read_text(encoding="utf-8")
    )

    repos = {}

    for query in config["queries"]:
        params = urllib.parse.urlencode({
            "q": query,
            "sort": "updated",
            "order": "desc",
            "per_page": limit_per_query
        })

        url = (
            "https://api.github.com/search/repositories?"
            + params
        )

        try:
            result = github_get(url)
        except urllib.error.HTTPError as exc:
            print(
                f"WARN query failed HTTP={exc.code}: {query}",
                file=sys.stderr
            )
            continue
        except Exception as exc:
            print(
                f"WARN query failed: {query}: {exc}",
                file=sys.stderr
            )
            continue

        for repo in result.get("items", []):
            if repo.get("fork"):
                continue

            if repo.get("archived"):
                continue

            repos[repo["full_name"]] = repo

        time.sleep(1)

    results = []

    for full_name, repo in repos.items():
        tech, tech_signals = technical_score(repo)

        paths = fetch_tree(
            full_name,
            repo.get("default_branch") or "main"
        )

        evidence, evidence_signals = evidence_score(paths)
        activity = activity_score(repo.get("pushed_at"))

        observed_total = tech + evidence + activity

        results.append({
            "repository": full_name,
            "url": repo.get("html_url"),
            "description": repo.get("description"),
            "language": repo.get("language"),
            "stars": repo.get("stargazers_count", 0),
            "open_issues": repo.get("open_issues_count", 0),
            "pushed_at": repo.get("pushed_at"),
            "default_branch": repo.get("default_branch"),

            "observed_scores": {
                "technical_fit": tech,
                "evidence_surface": evidence,
                "maintainer_activity": activity
            },

            "observed_total_max_70": observed_total,

            "observed_signals": {
                "technical": tech_signals,
                "evidence": evidence_signals
            },

            "observed_classification":
                classify_observed(observed_total),

            "human_review": {
                "review_need_max_20": None,
                "commercial_signal_max_10": None,
                "state": "NOT_REVIEWED"
            },

            "commercial_state": "NOT_CONTACTED"
        })

    results.sort(
        key=lambda x: (
            x["observed_total_max_70"],
            x["stars"]
        ),
        reverse=True
    )

    return results

def self_test():
    repo = {
        "name": "robot-evidence-agent",
        "description":
            "Robotics simulation execution provenance verification",
        "topics": [
            "robotics",
            "simulation",
            "provenance"
        ],
        "pushed_at":
            datetime.now(timezone.utc).isoformat()
    }

    tech, signals = technical_score(repo)

    paths = [
        "schemas/action.schema.json",
        "tests/test_execution.py",
        "adapter/robot.py",
        "evidence/trace.json",
        "verifier/check.py"
    ]

    evidence, evidence_signals = evidence_score(paths)
    activity = activity_score(repo["pushed_at"])

    result = {
        "technical_fit": tech,
        "evidence_surface": evidence,
        "maintainer_activity": activity,
        "observed_total": tech + evidence + activity,
        "technical_signals": signals,
        "evidence_signals": evidence_signals
    }

    print(json.dumps(result, indent=2))

    if result["observed_total"] < 45:
        print("SELF_TEST_PASS=false")
        return 1

    print("SELF_TEST_PASS=true")
    return 0

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--limit-per-query",
        type=int,
        default=4
    )

    parser.add_argument(
        "--self-test",
        action="store_true"
    )

    args = parser.parse_args()

    if args.self_test:
        return self_test()

    results = discover(
        max(1, min(args.limit_per_query, 10))
    )

    payload = {
        "generated_at":
            datetime.now(timezone.utc).isoformat(),

        "source": "GITHUB_PUBLIC_API",

        "scoring": {
            "observed_max": 70,
            "human_review_max": 30,
            "commercial_willingness_inferred": False
        },

        "candidate_count": len(results),
        "candidates": results
    }

    OUTPUT_FILE.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8"
    )

    print(f"CANDIDATE_COUNT={len(results)}")
    print(f"OUTPUT={OUTPUT_FILE}")

    for index, candidate in enumerate(
        results[:10],
        start=1
    ):
        print(
            f"{index:02d} "
            f"{candidate['observed_total_max_70']:02d}/70 "
            f"{candidate['observed_classification']} "
            f"{candidate['repository']}"
        )

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
