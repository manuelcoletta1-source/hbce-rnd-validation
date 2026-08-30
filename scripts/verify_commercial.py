#!/usr/bin/env python3

from pathlib import Path
import argparse
import hashlib
import json
import sys


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


def require_nonempty(
    value,
    field,
):
    if value is None:
        raise RuntimeError(
            field
            + " missing"
        )

    if not str(value).strip():
        raise RuntimeError(
            field
            + " empty"
        )


def load_model():
    if not MODEL_PATH.is_file():
        raise RuntimeError(
            "commercial model missing"
        )

    model = load_json(
        MODEL_PATH
    )

    for key in (
        "version",
        "states",
        "state_rules",
        "allowed_transitions",
        "offers",
    ):
        if key not in model:
            raise RuntimeError(
                "commercial model missing key: "
                + key
            )

    states = model["states"]

    if "PROSPECT" not in states:
        raise RuntimeError(
            "commercial model missing PROSPECT"
        )

    if set(model["state_rules"]) != set(states):
        raise RuntimeError(
            "commercial model state_rules coverage mismatch"
        )

    if set(
        model["allowed_transitions"]
    ) != set(states):
        raise RuntimeError(
            "commercial model transition coverage mismatch"
        )

    for source, destinations in (
        model[
            "allowed_transitions"
        ].items()
    ):
        for destination in destinations:
            if destination not in states:
                raise RuntimeError(
                    "commercial model unknown transition: "
                    + source
                    + " -> "
                    + destination
                )

    return model


def load_project(
    project_id,
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
            "PROJECT.json missing"
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
            "commercial projection missing"
        )

    return (
        project_dir,
        project,
        commercial,
    )


def load_events(
    project_dir,
):
    event_path = (
        project_dir
        / EVENT_FILE_NAME
    )

    if not event_path.exists():
        return []

    if not event_path.is_file():
        raise RuntimeError(
            "commercial event path is not a file"
        )

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
                    "invalid event JSON at line "
                    + str(line_number)
                    + ": "
                    + str(exc)
                )

            events.append(
                event
            )

    return events


def verify_offer_projection(
    commercial,
    project,
    model,
):
    offer_id = project.get(
        "offer"
    )

    if offer_id not in model[
        "offers"
    ]:
        raise RuntimeError(
            "unknown project offer"
        )

    offer = model[
        "offers"
    ][offer_id]

    if commercial.get(
        "model_version"
    ) != model.get(
        "version"
    ):
        raise RuntimeError(
            "commercial model version mismatch"
        )

    if commercial.get(
        "offer_id"
    ) != offer_id:
        raise RuntimeError(
            "commercial offer_id mismatch"
        )

    if commercial.get(
        "offer_name"
    ) != offer.get(
        "name"
    ):
        raise RuntimeError(
            "commercial offer name mismatch"
        )

    if "target_price_eur" in offer:

        if commercial.get(
            "target_price_eur"
        ) != offer[
            "target_price_eur"
        ]:
            raise RuntimeError(
                "target price mismatch"
            )

    elif (
        "target_price_range_eur"
        in offer
    ):

        if commercial.get(
            "target_price_range_eur"
        ) != offer[
            "target_price_range_eur"
        ]:
            raise RuntimeError(
                "target price range mismatch"
            )

    else:
        raise RuntimeError(
            "offer has no target price"
        )


def verify_event_hash_and_chain(
    events,
    project_id,
):
    previous_hash = None

    for expected_sequence, event in enumerate(
        events,
        start=1,
    ):
        if event.get(
            "project_id"
        ) != project_id:
            raise RuntimeError(
                "event project_id mismatch "
                f"at sequence {expected_sequence}"
            )

        if event.get(
            "sequence"
        ) != expected_sequence:
            raise RuntimeError(
                "event sequence mismatch "
                f"at sequence {expected_sequence}"
            )

        if event.get(
            "event_type"
        ) != "COMMERCIAL_STATE_TRANSITION":
            raise RuntimeError(
                "unexpected event type "
                f"at sequence {expected_sequence}"
            )

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
                f"at sequence {expected_sequence}"
            )

        if body.get(
            "previous_event_sha256"
        ) != previous_hash:
            raise RuntimeError(
                "event chain mismatch "
                f"at sequence {expected_sequence}"
            )

        previous_hash = (
            stored_hash
        )

    return previous_hash


def reconstruct_commercial_state(
    events,
    model,
):
    state = "PROSPECT"

    rule = model[
        "state_rules"
    ][state]

    reconstructed = {
        "state": state,

        "commercial_relationship_validated":
            rule[
                "commercial_relationship"
            ],

        "paid_engagement_validated":
            rule[
                "paid_engagement"
            ],

        "payment_state":
            "NOT_AGREED",

        "agreed_price_eur":
            None,

        "paid_eur":
            0,
    }

    for expected_sequence, event in enumerate(
        events,
        start=1,
    ):
        from_state = event.get(
            "from_state"
        )

        to_state = event.get(
            "to_state"
        )

        if from_state != state:
            raise RuntimeError(
                "event state continuity mismatch "
                f"at sequence {expected_sequence}"
            )

        if to_state not in model[
            "states"
        ]:
            raise RuntimeError(
                "unknown event target state "
                f"at sequence {expected_sequence}"
            )

        allowed = model[
            "allowed_transitions"
        ][state]

        if to_state not in allowed:
            raise RuntimeError(
                "illegal recorded transition "
                + state
                + " -> "
                + to_state
            )

        evidence_ref = event.get(
            "evidence_ref"
        )

        if to_state == "COMMERCIAL_ACCEPTED":

            require_nonempty(
                evidence_ref,
                "commercial acceptance evidence",
            )

            agreed = event.get(
                "agreed_price_eur"
            )

            if not isinstance(
                agreed,
                (int, float),
            ):
                raise RuntimeError(
                    "accepted price is not numeric"
                )

            if agreed <= 0:
                raise RuntimeError(
                    "accepted price must be positive"
                )

            reconstructed[
                "agreed_price_eur"
            ] = agreed

            reconstructed[
                "payment_state"
            ] = "NOT_REQUESTED"

        elif to_state == "PAYMENT_PENDING":

            require_nonempty(
                evidence_ref,
                "payment pending evidence",
            )

            if reconstructed[
                "agreed_price_eur"
            ] in (
                None,
                0,
            ):
                raise RuntimeError(
                    "payment pending without agreed price"
                )

            reconstructed[
                "payment_state"
            ] = "PENDING"

        elif to_state == "PAID":

            require_nonempty(
                evidence_ref,
                "payment evidence",
            )

            paid = event.get(
                "paid_eur"
            )

            if not isinstance(
                paid,
                (int, float),
            ):
                raise RuntimeError(
                    "paid amount is not numeric"
                )

            if paid <= 0:
                raise RuntimeError(
                    "paid amount must be positive"
                )

            agreed = reconstructed[
                "agreed_price_eur"
            ]

            if agreed is None:
                raise RuntimeError(
                    "payment without agreed price"
                )

            if paid > agreed:
                raise RuntimeError(
                    "paid amount exceeds agreed price"
                )

            reconstructed[
                "paid_eur"
            ] = paid

            reconstructed[
                "payment_state"
            ] = "PAID"

        elif to_state in (
            "DELIVERED",
            "CLOSED",
        ):

            require_nonempty(
                evidence_ref,
                (
                    to_state.lower()
                    + " evidence"
                ),
            )

        state = to_state

        target_rule = model[
            "state_rules"
        ][state]

        reconstructed[
            "state"
        ] = state

        reconstructed[
            "commercial_relationship_validated"
        ] = target_rule[
            "commercial_relationship"
        ]

        reconstructed[
            "paid_engagement_validated"
        ] = target_rule[
            "paid_engagement"
        ]

    return reconstructed


def verify_projection(
    commercial,
    reconstructed,
    events,
):
    required_projection_fields = [
        "state",
        "commercial_relationship_validated",
        "paid_engagement_validated",
        "payment_state",
        "agreed_price_eur",
        "paid_eur",
    ]

    for field in required_projection_fields:

        if commercial.get(
            field
        ) != reconstructed[
            field
        ]:
            raise RuntimeError(
                "commercial projection mismatch: "
                + field
            )

    if events:

        last_event = events[
            -1
        ]

        last_transition = commercial.get(
            "last_transition"
        )

        if not isinstance(
            last_transition,
            dict,
        ):
            raise RuntimeError(
                "last_transition missing"
            )

        expected = {
            "sequence":
                last_event[
                    "sequence"
                ],

            "event_sha256":
                last_event[
                    "event_sha256"
                ],

            "occurred_at":
                last_event[
                    "occurred_at"
                ],
        }

        if last_transition != expected:
            raise RuntimeError(
                "last_transition projection mismatch"
            )

    else:

        if commercial.get(
            "state"
        ) != "PROSPECT":
            raise RuntimeError(
                "empty event log must project PROSPECT"
            )

        if commercial.get(
            "last_transition"
        ) not in (
            None,
            {},
        ):
            raise RuntimeError(
                "unexpected last_transition "
                "without events"
            )


def verify_project(
    project_id,
):
    model = load_model()

    (
        project_dir,
        project,
        commercial,
    ) = load_project(
        project_id
    )

    verify_offer_projection(
        commercial,
        project,
        model,
    )

    events = load_events(
        project_dir
    )

    chain_tip = (
        verify_event_hash_and_chain(
            events,
            project_id,
        )
    )

    reconstructed = (
        reconstruct_commercial_state(
            events,
            model,
        )
    )

    verify_projection(
        commercial,
        reconstructed,
        events,
    )

    return {
        "project_id":
            project_id,

        "verification_status":
            "PASS",

        "event_count":
            len(events),

        "event_chain_valid":
            True,

        "event_chain_tip_sha256":
            chain_tip,

        "current_state":
            reconstructed[
                "state"
            ],

        "commercial_relationship_validated":
            reconstructed[
                "commercial_relationship_validated"
            ],

        "paid_engagement_validated":
            reconstructed[
                "paid_engagement_validated"
            ],

        "payment_state":
            reconstructed[
                "payment_state"
            ],

        "agreed_price_eur":
            reconstructed[
                "agreed_price_eur"
            ],

        "paid_eur":
            reconstructed[
                "paid_eur"
            ],
    }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Independently verify an HBCE "
            "commercial engagement projection "
            "against its event genealogy."
        )
    )

    parser.add_argument(
        "project_id"
    )

    args = parser.parse_args()

    try:
        result = verify_project(
            args.project_id
        )

        print(
            "VERIFICATION_STATUS=PASS"
        )

        print(
            "PROJECT_ID="
            + result[
                "project_id"
            ]
        )

        print(
            "EVENT_COUNT="
            + str(
                result[
                    "event_count"
                ]
            )
        )

        print(
            "EVENT_CHAIN_VALID=true"
        )

        print(
            "EVENT_CHAIN_TIP_SHA256="
            + str(
                result[
                    "event_chain_tip_sha256"
                ]
            )
        )

        print(
            "CURRENT_STATE="
            + result[
                "current_state"
            ]
        )

        print(
            "COMMERCIAL_RELATIONSHIP_VALIDATED="
            + str(
                result[
                    "commercial_relationship_validated"
                ]
            ).lower()
        )

        print(
            "PAID_ENGAGEMENT_VALIDATED="
            + str(
                result[
                    "paid_engagement_validated"
                ]
            ).lower()
        )

        print(
            "PAYMENT_STATE="
            + str(
                result[
                    "payment_state"
                ]
            )
        )

        print(
            "AGREED_PRICE_EUR="
            + str(
                result[
                    "agreed_price_eur"
                ]
            )
        )

        print(
            "PAID_EUR="
            + str(
                result[
                    "paid_eur"
                ]
            )
        )

        return 0

    except Exception as exc:

        print(
            "VERIFICATION_STATUS=FAIL"
        )

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
