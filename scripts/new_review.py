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

COMMERCIAL_MODEL = (
    ROOT
    / "commercial"
    / "ENGAGEMENT_MODEL.json"
)


OFFER_IDS = [
    "ARTIFACT_REVIEW",
    "EVIDENCE_RECONSTRUCTION",
    "PROTOCOL_STRESS_TEST",
    "FULL_VALIDATION_CYCLE",
]


PROJECT_TEMPLATE_FILES = [
    "INTAKE.md",
    "FINDINGS.md",
    "QUALIFICATION.md",
    "PROPOSAL.md",
    "ENGAGEMENT.md",
]


def slugify(value: str) -> str:
    value = value.strip().lower()

    value = re.sub(
        r"[^a-z0-9]+",
        "-",
        value,
    )

    return value.strip("-")


def next_project_number() -> int:
    nums = []

    if not PROJECTS.exists():
        return 1

    for path in PROJECTS.iterdir():
        if not path.is_dir():
            continue

        match = re.match(
            r"^(\d{3})-",
            path.name,
        )

        if match:
            nums.append(
                int(match.group(1))
            )

    return max(
        nums,
        default=0,
    ) + 1


def load_json(path: Path):
    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def load_commercial_model():
    if not COMMERCIAL_MODEL.exists():
        raise RuntimeError(
            "commercial engagement model missing: "
            + str(COMMERCIAL_MODEL)
        )

    model = load_json(
        COMMERCIAL_MODEL
    )

    states = model.get(
        "states",
        [],
    )

    if "PROSPECT" not in states:
        raise RuntimeError(
            "commercial model does not declare PROSPECT"
        )

    offers = model.get(
        "offers",
        {},
    )

    for offer_id in OFFER_IDS:
        if offer_id not in offers:
            raise RuntimeError(
                "commercial model missing offer: "
                + offer_id
            )

    return model


def commercial_offer_metadata(
    model,
    offer_id,
):
    offer = model["offers"][offer_id]

    metadata = {
        "offer_id": offer_id,
        "offer_name": offer["name"],
    }

    if "target_price_eur" in offer:
        metadata[
            "target_price_eur"
        ] = offer["target_price_eur"]

    elif "target_price_range_eur" in offer:
        metadata[
            "target_price_range_eur"
        ] = offer[
            "target_price_range_eur"
        ]

    else:
        raise RuntimeError(
            "commercial offer has no target price: "
            + offer_id
        )

    return metadata


def verify_required_templates():
    required = (
        PROJECT_TEMPLATE_FILES
        + ["CLOSURE.json"]
    )

    missing = []

    for name in required:
        path = TEMPLATES / name

        if not path.is_file():
            missing.append(name)

    if missing:
        raise RuntimeError(
            "missing project templates: "
            + ", ".join(missing)
        )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Create a new HBCE R&D Validation "
            "project workspace."
        )
    )

    parser.add_argument(
        "name",
        help="Project name",
    )

    parser.add_argument(
        "--offer",
        default="ARTIFACT_REVIEW",
        choices=OFFER_IDS,
    )

    args = parser.parse_args()

    slug = slugify(
        args.name
    )

    if not slug:
        print(
            "FAIL: invalid project name",
            file=sys.stderr,
        )
        return 1

    try:
        model = load_commercial_model()

        verify_required_templates()

        offer_metadata = (
            commercial_offer_metadata(
                model,
                args.offer,
            )
        )

    except Exception as exc:
        print(
            "FAIL_CLOSED: "
            + str(exc),
            file=sys.stderr,
        )
        return 1

    PROJECTS.mkdir(
        parents=True,
        exist_ok=True,
    )

    number = next_project_number()

    project_id = (
        f"{number:03d}-{slug}"
    )

    project_dir = (
        PROJECTS
        / project_id
    )

    if project_dir.exists():
        print(
            "FAIL: project already exists: "
            + str(project_dir),
            file=sys.stderr,
        )
        return 1

    project_dir.mkdir(
        parents=True
    )

    try:
        for name in PROJECT_TEMPLATE_FILES:
            shutil.copy(
                TEMPLATES / name,
                project_dir / name,
            )

        closure = load_json(
            TEMPLATES
            / "CLOSURE.json"
        )

        closure["project_id"] = (
            project_id
        )

        (
            project_dir
            / "CLOSURE.json"
        ).write_text(
            json.dumps(
                closure,
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )

        now = datetime.now(
            timezone.utc
        ).isoformat()

        metadata = {
            "project_id": project_id,
            "name": args.name,
            "offer": args.offer,

            "state": "INTAKE",

            "created_at": now,

            "technical": {
                "state": "INTAKE",
                "closure_state": (
                    "NOT_EVALUATED"
                ),
            },

            "commercial": {
                "model_version": model[
                    "version"
                ],

                "state": "PROSPECT",

                "commercial_relationship_validated": False,

                "paid_engagement_validated": False,

                "payment_state": "NOT_AGREED",

                "agreed_price_eur": None,

                "paid_eur": 0,

                **offer_metadata,
            },
        }

        (
            project_dir
            / "PROJECT.json"
        ).write_text(
            json.dumps(
                metadata,
                indent=2,
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )

    except Exception as exc:
        shutil.rmtree(
            project_dir,
            ignore_errors=True,
        )

        print(
            "FAIL_CLOSED: project creation "
            "rolled back: "
            + str(exc),
            file=sys.stderr,
        )

        return 1

    print(
        f"PROJECT_CREATED={project_id}"
    )

    print(
        f"PATH={project_dir}"
    )

    print(
        "TECHNICAL_STATE=INTAKE"
    )

    print(
        "COMMERCIAL_STATE=PROSPECT"
    )

    print(
        "COMMERCIAL_RELATIONSHIP_VALIDATED=false"
    )

    print(
        "PAID_ENGAGEMENT_VALIDATED=false"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
