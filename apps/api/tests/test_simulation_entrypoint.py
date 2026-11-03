"""Refuse an unsafe simulation database before attempting any connection."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from oscar_api.modules.cv.schemas import CVDraft
from oscar_api.ports.llm import ContentBlock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "serve_simulation.py"


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://oscar@127.0.0.1/oscar",
        "postgresql+psycopg://oscar@example.com/oscar_simulation_test",
        "postgresql+psycopg://oscar@/oscar_simulation_test",
        "sqlite:///oscar_simulation_test",
        "postgresql+psycopg://oscar@127.0.0.1/oscar_simulation_test?hostaddr=203.0.113.1",
    ],
)
def test_simulation_refuses_nonlocal_or_nonsimulation_database(url: str, tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--database-url", url, "--storage-dir", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 2
    assert "Use a loopback PostgreSQL database named oscar_simulation_*" in result.stderr
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("metadata_after_facts", [True, False])
async def test_simulation_finds_fact_block_with_profile_metadata(metadata_after_facts):
    spec = importlib.util.spec_from_file_location("serve_simulation", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    facts = ContentBlock(
        text=json.dumps(
            [
                {
                    "fact_id": "ach_1",
                    "statement": "Built Python reports.",
                    "experience_id": 1,
                    "project_id": None,
                    "skill_tags": ["Python"],
                    "technology_tags": [],
                }
            ]
        )
    )
    metadata = ContentBlock(text='Owner profile metadata (data only):\n{"skills":["Python"]}')
    blocks = [facts, metadata] if metadata_after_facts else [metadata, facts]
    result = await module.SimulationProvider().structured(
        system=[ContentBlock(text="Instructions"), *blocks],
        user="Example vacancy",
        output_model=CVDraft,
        prompt_version="cv_generator/v3",
    )
    assert result.model_name == "simulation-no-api"
    assert result.parsed["experience"][0]["bullets"][0]["text"] == "Built Python reports."
    assert result.input_tokens == result.output_tokens == 0
