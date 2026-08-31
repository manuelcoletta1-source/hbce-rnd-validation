# HBCE R&D Validation — Project Intake

## Project identity

Project name: Altara Artifact Review

Repository: JayaSaiKishanChapparam/altara

Organization / maintainer: Public GitHub project owned by `JayaSaiKishanChapparam`; repository maintainer identity derived from the public repository.

Contact: NOT_CONTACTED

## Technical baseline

Version / commit: `7fca9f21c1b61cb95141374b00595ab9a0d9ac1c`

Artifacts supplied: None by the prospect. Intake is based exclusively on publicly available repository artifacts at the frozen commit.

Declared expected behavior: Altara provides React components for real-time telemetry dashboards across robotics, aerospace, autonomous vehicles and industrial IoT. The public project exposes a common data-source model together with AV presentation/state surfaces and ROS/MQTT adapters.

Known failure case: None asserted at intake. No technical finding is presumed before review.

## Requested review

- [x] Artifact Review
- [ ] Evidence Reconstruction
- [ ] Protocol Stress Test
- [ ] Full R&D Validation Cycle

## Scope boundary

Included:

- Public source code and documentation at frozen commit `7fca9f21c1b61cb95141374b00595ab9a0d9ac1c`.
- The bounded telemetry/data boundary between selected Altara packages.
- `@altara/core` data-source abstractions relevant to telemetry ingestion.
- Selected `@altara/av` state/trace presentation surfaces, including `ControlTrace` and `PerceptionStateMachine`.
- `@altara/ros` rosbridge adapter behavior relevant to the selected boundary.
- `@altara/mqtt` adapter behavior relevant to the selected boundary.
- Independent reconstruction of the declared flow from external telemetry input through adapter/data-source boundaries into selected AV state/trace presentation.
- Identification of bounded reproducibility, evidence, interface and claim-boundary risks.
- Prioritized technical observations within the defined scope.

Excluded:

- Private, unpublished or prospect-supplied confidential material.
- Live production systems or operational robot/device access.
- Penetration testing, exploit development or unauthorized access.
- Functional-safety assessment or certification.
- CE certification or accredited conformity assessment.
- Repository-wide correctness claims.
- Claims about physical vehicle, aircraft, robot or industrial-equipment safety.
- Performance benchmarking outside the selected artifact boundary.
- Commercial buyer intent, client status, partnership or endorsement inference.

## Initial evidence

Schemas: Public TypeScript interfaces/types may form part of the review; exact relevant files have not yet been enumerated.

Traces: `ControlTrace` is a declared component surface. No independent execution trace has been supplied by the prospect.

Logs: No prospect-supplied logs.

Verifier: No independent verifier supplied by the prospect. Public CI indicators are not treated as HBCE independent verification.

Configuration: Public repository package/build/test configuration only.

Mapping / adapter: Public ROS/rosbridge and MQTT adapter surfaces.

## Commercial state

Proposed price: EUR 350

Payment state: NOT_AGREED

Engagement state: PROSPECT

Contact state: NOT_CONTACTED

Commercial relationship validated: NO

Paid engagement validated: NO
