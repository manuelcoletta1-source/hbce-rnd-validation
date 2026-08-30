#!/usr/bin/env python3

from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ROOT / "projects"
TEMPLATES = ROOT / "templates"

def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")

def next_project_number() -> int:
    nums = []

    for path in PROJECTS.iterdir():
        if not path.is_dir():
            continue

        match = re.match(r"^(\d{3})-", path.name)
        if match:
            nums.append(int(match.group(1)))

    return max(nums, default=0) + 1

def main():
    parser = argparse.ArgumentParser(
        description="Create a new HBCE R&D Validation project workspace."
    )
    parser.add_argument("name", help="Project name")
    parser.add_argument(
        "--offer",
        default="ARTIFACT_REVIEW",
        choices=[
            "ARTIFACT_REVIEW",
            "EVIDENCE_RECONSTRUCTION",
            "PROTOCOL_STRESS_TEST",
            "FULL_VALIDATION_CYCLE"
        ]
    )

    args = parser.parse_args()

    slug = slugify(args.name)

    if not slug:
        print("FAIL: invalid project name", file=sys.stderr)
        return 1

    number = next_project_number()
    project_id = f"{number:03d}-{slug}"
    project_dir = PROJECTS / project_id

    if project_dir.exists():
        print(f"FAIL: project already exists: {project_dir}", file=sys.stderr)
        return 1

    project_dir.mkdir(parents=True)

    shutil.copy(
        TEMPLATES / "INTAKE.md",
        project_dir / "INTAKE.md"
    )

    shutil.copy(
        TEMPLATES / "FINDINGS.md",
        project_dir / "FINDINGS.md"
    )

    closure = json.loads(
        (TEMPLATES / "CLOSURE.json").read_text(encoding="utf-8")
    )

    closure["project_id"] = project_id

    (project_dir / "CLOSURE.json").write_text(
        json.dumps(closure, indent=2) + "\n",
        encoding="utf-8"
    )

    metadata = {
        "project_id": project_id,
        "name": args.name,
        "offer": args.offer,
        "state": "INTAKE",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "commercial": {
            "payment_state": "NOT_AGREED",
            "paid_eur": 0
        }
    }

    (project_dir / "PROJECT.json").write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8"
    )

    print(f"PROJECT_CREATED={project_id}")
    print(f"PATH={project_dir}")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
