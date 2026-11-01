# adapters/ — Future ATS automation (not implemented, P3)

Reserved for **site automation** adapters — Greenhouse, Lever, Ashby, Workday, SmartRecruiters, generic forms. Priority **P3**, well after V1. See master spec §20 and [../docs/03_SYSTEM_ARCHITECTURE.md](../docs/03_SYSTEM_ARCHITECTURE.md) §8.

Not to be confused with `apps/api/src/oscar_api/adapters/`, which holds the LLM and storage port implementations used from Milestone 3.

## Why the empty directory exists

To declare the boundary before anything is built: when adapters arrive they depend on `applications` and `career` through their service APIs. Site-specific code must never become core domain logic (Decision Rule 15).

## Bar for adding one

Adapters are built from **measured** usage data — which ATS actually consumes the most time — not from a list of vendors. Each requires fixtures, unit tests, telemetry, a version, and failure classification (master spec §20). None of this is scheduled, and building it before Milestone 6 produces usage data would be exactly the speculative infrastructure the decision rules forbid.

Also non-negotiable, at any priority: no CAPTCHA solving, no anti-bot circumvention, no fingerprint spoofing. Blocked or ambiguous flows pause for the human ([../docs/01_PRD.md](../docs/01_PRD.md) §6).
