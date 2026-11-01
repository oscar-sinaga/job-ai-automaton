"""baseline: empty schema

Milestone 0 intentionally creates no tables. This revision exists so the migration
toolchain is proven end-to-end (upgrade *and* downgrade, in CI) before the first
domain table lands in M1 -- an untested downgrade is a rollback that fails exactly
when it is needed. See docs/04_DATA_MODEL.md §9.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-08-28

"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
