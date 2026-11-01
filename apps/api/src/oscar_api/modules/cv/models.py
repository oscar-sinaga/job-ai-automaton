"""ORM models for the CV domain (docs/04_DATA_MODEL.md §5).

`cv_versions` rows are immutable once created -- an edit inserts a new version
(ADR-014), which is what lets US-4 ("which exact CV did I send") hold forever.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from oscar_api.db import Base


class CVVersion(Base):
    __tablename__ = "cv_versions"
    __table_args__ = (
        UniqueConstraint("job_id", "version_number", name="uq_cv_versions_job_version"),
        Index(
            "uq_one_submitted_cv_per_job",
            "job_id",
            unique=True,
            postgresql_where="is_submitted",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    version_number: Mapped[int] = mapped_column(Integer)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    sections: Mapped[dict[str, Any]] = mapped_column(JSONB)
    is_submitted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default="now()"
    )

    artifacts: Mapped[list[CVArtifact]] = relationship(back_populates="cv_version")

    @property
    def label(self) -> str:
        return f"CV_J{self.job_id:03d}_v{self.version_number}"


class CVGenerationRun(Base):
    __tablename__ = "cv_generation_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    cv_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("cv_versions.id", ondelete="SET NULL"), nullable=True
    )
    model_name: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20))  # succeeded | rejected_claims | failed
    grounding_report: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default="now()"
    )


class CVArtifact(Base):
    __tablename__ = "cv_artifacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    cv_version_id: Mapped[int] = mapped_column(ForeignKey("cv_versions.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20), default="pdf")
    storage_uri: Mapped[str] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default="now()"
    )

    cv_version: Mapped[CVVersion] = relationship(back_populates="artifacts")
