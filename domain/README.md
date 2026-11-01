# domain/ — placeholder

The master spec's suggested layout (§9) puts domain logic at the repository root. This project instead implements the five bounded contexts **inside the FastAPI app**, at `apps/api/src/oscar_api/modules/`:

```text
modules/jobs/          capture, raw snapshots, parsed data, dedupe, job events
modules/career/        the career fact store
modules/cv/            generation runs, versions, grounding, export
modules/applications/  application records, status transitions, events
modules/analytics/     read-only aggregation queries
```

Reason: V1 is a modular monolith (ADR-003) with a single deployable. Root-level domain packages would mean either a second installable package or import gymnastics, for no benefit at this scale. The **boundaries** the spec asks for are enforced regardless — by `import-linter` contracts in CI, per [../docs/03_SYSTEM_ARCHITECTURE.md](../docs/03_SYSTEM_ARCHITECTURE.md) §2.

This directory is kept as a signpost so the deviation from spec §9 is discoverable rather than surprising. Recorded in [../docs/17_DECISION_LOG.md](../docs/17_DECISION_LOG.md) ADR-003.
