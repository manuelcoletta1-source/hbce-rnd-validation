#!/usr/bin/env python3

from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]

PROJECTS = ROOT / "projects"

MODEL_PATH = (
    ROOT
    / "commercial"
    / "ENGAGEMENT_MODEL.json"
)

EVENT_FILE_NAME = (
    "COMMERCIAL_EVENTS.jsonl"
)


def load_json(path: Path):
    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def canonical_bytes(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_hex(value):
    return hashlib.sha256(
        value
    ).hexdigest()


def atomic_write_json(
    path: Path,
    value,
):
    content = (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    fd, temp_name = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
        text=True,
    )

    try:
        with os.fdopen(
            fd,
            "w",
            encoding="utf-8",
        ) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(
                handle.fileno()
            )

        os.replace(
            temp_name,
            path,
        )

    except Exception:
        try:
            os.unlink(
                temp_name
            )
        except FileNotFoundError:
            pass

        raise


def load_model():
    if not MODEL_PATH.is_file():
        raise RuntimeError(
            "commercial model missing: "
            + str(MODEL_PATH)
        )

    model = load_json(
        MODEL_PATH
    )

    required = [
        "states",
        "state_rules",
        "allowed_transitions",
    ]

    for key in required:
        if key not in model:
            raise RuntimeError(
                "commercial model missing key: "
                + key
            )

    return model


def load_project(
    project_id: str,
):
    project_dir = (
        PROJECTS
        / project_id
    )

    project_path = (
        project_dir
        / "PROJECT.json"
    )

    if not project_dir.is_dir():
        raise RuntimeError(
            "project not found: "
            + project_id
        )

    if not project_path.is_file():
        raise RuntimeError(
            "PROJECT.json missing: "
            + str(project_path)
        )

    project = load_json(
        project_path
    )

    if project.get(
        "project_id"
    ) != project_id:
        raise RuntimeError(
            "project_id mismatch"
        )

    commercial = project.get(
        "commercial"
    )

    if not isinstance(
        commercial,
        dict,
    ):
        raise RuntimeError(
            "commercial state missing"
        )

    return (
        project_dir,
        project_path,
        project,
        commercial,
    )


def load_existing_events(
    event_path: Path,
):
    if not event_path.exists():
        return []

    events = []

    with event_path.open(
        "r",
        encoding="utf-8",
    ) as handle:

        for line_number, line in enumerate(
            handle,
            start=1,
        ):
            line = line.strip()

            if not line:
                continue

            try:
                event = json.loads(
                    line
                )

            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    "invalid event log JSON "
                    f"at line {line_number}: "
                    + str(exc)
                )

            events.append(
                event
            )

    return events


def validate_event_chain(
    events,
):
    previous_hash = None

    for index, event in enumerate(
        events,
        start=1,
    ):
        stored_hash = event.get(
            "event_sha256"
        )

        body = dict(
            event
        )

        body.pop(
            "event_sha256",
            None,
        )

        calculated_hash = sha256_hex(
            canonical_bytes(
                body
            )
        )

        if stored_hash != calculated_hash:
            raise RuntimeError(
                "event hash mismatch "
                f"at sequence {index}"
            )

        expected_previous = (
            previous_hash
        )

        if body.get(
            "previous_event_sha256"
        ) != expected_previous:
            raise RuntimeError(
                "event chain mismatch "
                f"at sequence {index}"
            )

        if body.get(
            "sequence"
        ) != index:
            raise RuntimeError(
                "event sequence mismatch "
                f"at sequence {index}"
            )

        previous_hash = (
            stored_hash
        )

    return previous_hash


def validate_projection(
    commercial,
    model,
):
    state = commercial.get(
        "state"
    )

    if state not in model[
        "states"
    ]:
        raise RuntimeError(
            "unknown current commercial state: "
            + repr(state)
        )

    rule = model[
        "state_rules"
    ][state]

    if (
        commercial.get(
            "commercial_relationship_validated"
        )
        is not rule[
            "commercial_relationship"
        ]
    ):
        raise RuntimeError(
            "commercial relationship projection "
            "does not match model state"
        )

    if (
        commercial.get(
            "paid_engagement_validated"
        )
        is not rule[
            "paid_engagement"
        ]
    ):
        raise RuntimeError(
            "paid engagement projection "
            "does not match model state"
        )

    return state


def require_nonempty(
    value,
    field,
):
    if value is None:
        raise RuntimeError(
            field
            + " is required"
        )

    value = str(
        value
    ).strip()

    if not value:
        raise RuntimeError(
            field
            + " is required"
        )

    return value


def build_projection(
    commercial,
    target_state,
    model,
    args,
):
    updated = dict(
        commercial
    )

    target_rule = model[
        "state_rules"
    ][target_state]

    updated["state"] = (
        target_state
    )

    updated[
        "commercial_relationship_validated"
    ] = target_rule[
        "commercial_relationship"
    ]

    updated[
        "paid_engagement_validated"
    ] = target_rule[
        "paid_engagement"
    ]

    if target_state == "COMMERCIAL_ACCEPTED":

        if args.agreed_price_eur is None:
            raise RuntimeError(
                "--agreed-price-eur is required "
                "for COMMERCIAL_ACCEPTED"
            )

        if args.agreed_price_eur <= 0:
            raise RuntimeError(
                "agreed price must be greater than zero"
            )

        require_nonempty(
            args.evidence_ref,
            "--evidence-ref",
        )

        updated[
            "agreed_price_eur"
        ] = args.agreed_price_eur

        updated[
            "payment_state"
        ] = "NOT_REQUESTED"

    elif target_state == "PAYMENT_PENDING":

        require_nonempty(
            args.evidence_ref,
            "--evidence-ref",
        )

        if updated.get(
            "agreed_price_eur"
        ) in (
            None,
            0,
        ):
            raise RuntimeError(
                "agreed price missing before "
                "PAYMENT_PENDING"
            )

        updated[
            "payment_state"
        ] = "PENDING"

    elif target_state == "PAID":

        require_nonempty(
            args.evidence_ref,
            "--evidence-ref",
        )

        if args.paid_eur is None:
            raise RuntimeError(
                "--paid-eur is required for PAID"
            )

        if args.paid_eur <= 0:
            raise RuntimeError(
                "paid amount must be greater than zero"
            )

        agreed = updated.get(
            "agreed_price_eur"
        )

        if agreed is None:
            raise RuntimeError(
                "agreed price missing before PAID"
            )

        if args.paid_eur > agreed:
            raise RuntimeError(
                "paid amount exceeds agreed price"
            )

        updated[
            "paid_eur"
        ] = args.paid_eur

        updated[
            "payment_state"
        ] = "PAID"

    elif target_state in (
        "DELIVERED",
        "CLOSED",
    ):

        require_nonempty(
            args.evidence_ref,
            "--evidence-ref",
        )

    return updated


def append_event(
    event_path: Path,
    event,
):
    encoded = (
        json.dumps(
            event,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n"
    )

    with event_path.open(
        "a",
        encoding="utf-8",
    ) as handle:
        handle.write(
            encoded
        )

        handle.flush()

        os.fsync(
            handle.fileno()
        )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Transition an HBCE project through "
            "the commercial engagement state machine."
        )
    )

    parser.add_argument(
        "project_id",
    )

    parser.add_argument(
        "target_state",
    )

    parser.add_argument(
        "--evidence-ref",
        default=None,
    )

    parser.add_argument(
        "--note",
        default=None,
    )

    parser.add_argument(
        "--agreed-price-eur",
        type=float,
        default=None,
    )

    parser.add_argument(
        "--paid-eur",
        type=float,
        default=None,
    )

    args = parser.parse_args()

    try:
        model = load_model()

        (
            project_dir,
            project_path,
            project,
            commercial,
        ) = load_project(
            args.project_id
        )

        #
        # Existing genealogy is an integrity gate.
        # Validate it before evaluating any requested
        # transition, including requests that will later
        # be rejected as illegal.
        #
        event_path = (
            project_dir
            / EVENT_FILE_NAME
        )

        events = load_existing_events(
            event_path
        )

        previous_hash = (
            validate_event_chain(
                events
            )
        )

        current_state = (
            validate_projection(
                commercial,
                model,
            )
        )

        if events:
            last_to_state = events[
                -1
            ].get(
                "to_state"
            )

            if last_to_state != current_state:
                raise RuntimeError(
                    "event log and PROJECT.json "
                    "projection disagree"
                )

        target_state = (
            args.target_state
            .strip()
            .upper()
        )

        if target_state not in model[
            "states"
        ]:
            raise RuntimeError(
                "unknown target state: "
                + target_state
            )

        allowed = model[
            "allowed_transitions"
        ][current_state]

        if target_state not in allowed:
            raise RuntimeError(
                "illegal commercial transition: "
                + current_state
                + " -> "
                + target_state
            )

        updated_commercial = (
            build_projection(
                commercial,
                target_state,
                model,
                args,
            )
        )

        sequence = (
            len(events)
            + 1
        )

        event_body = {
            "event_type": (
                "COMMERCIAL_STATE_TRANSITION"
            ),

            "project_id": (
                args.project_id
            ),

            "sequence": sequence,

            "occurred_at": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),

            "from_state": (
                current_state
            ),

            "to_state": (
                target_state
            ),

            "previous_event_sha256": (
                previous_hash
            ),

            "evidence_ref": (
                args.evidence_ref
            ),

            "note": (
                args.note
            ),

            "agreed_price_eur": (
                args.agreed_price_eur
            ),

            "paid_eur": (
                args.paid_eur
            ),
        }

        event_hash = sha256_hex(
            canonical_bytes(
                event_body
            )
        )

        event = dict(
            event_body
        )

        event[
            "event_sha256"
        ] = event_hash

        updated_project = dict(
            project
        )

        updated_project[
            "commercial"
        ] = updated_commercial

        updated_project[
            "commercial"
        ][
            "last_transition"
        ] = {
            "sequence": sequence,
            "event_sha256": event_hash,
            "occurred_at": (
                event_body[
                    "occurred_at"
                ]
            ),
        }

        #
        # Event is written first. PROJECT.json is
        # merely the current projection.
        #
        append_event(
            event_path,
            event,
        )

        try:
            atomic_write_json(
                project_path,
                updated_project,
            )

        except Exception as exc:
            raise RuntimeError(
                "event committed but projection update "
                "failed; manual recovery required: "
                + str(exc)
            )

        print(
            "TRANSITION_APPLIED=true"
        )

        print(
            "PROJECT_ID="
            + args.project_id
        )

        print(
            "FROM_STATE="
            + current_state
        )

        print(
            "TO_STATE="
            + target_state
        )

        print(
            "EVENT_SEQUENCE="
            + str(sequence)
        )

        print(
            "EVENT_SHA256="
            + event_hash
        )

        print(
            "COMMERCIAL_RELATIONSHIP_VALIDATED="
            + str(
                updated_commercial[
                    "commercial_relationship_validated"
                ]
            ).lower()
        )

        print(
            "PAID_ENGAGEMENT_VALIDATED="
            + str(
                updated_commercial[
                    "paid_engagement_validated"
                ]
            ).lower()
        )

        return 0

    except Exception as exc:
        print(
            "FAIL_CLOSED: "
            + str(exc),
            file=sys.stderr,
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
