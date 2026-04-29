"""Integration tests for Foundry cloud evaluation pipeline.

These tests call real Azure APIs and require:
  - pip install -e ".[foundry]"
  - az login
  - AZURE_AI_PROJECT_ENDPOINT in .env

Run with:  pytest tests/foundry/test_integration.py -v -m integration
Skip with: pytest -m "not integration"
"""

from __future__ import annotations

import json
import os

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.live]


def _has_foundry_env() -> bool:
    """Check if Foundry env vars are available."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    return bool(os.environ.get("AZURE_AI_PROJECT_ENDPOINT"))


skip_no_env = pytest.mark.skipif(
    not _has_foundry_env(),
    reason="AZURE_AI_PROJECT_ENDPOINT not set — skipping live Foundry tests",
)


@skip_no_env
class TestFoundryLiveConnection:
    """Verify live connection to Microsoft Foundry."""

    def test_client_connects(self):
        """FoundryEvalClient can connect with DefaultAzureCredential."""
        from src.foundry.client import FoundryEvalClient
        from src.foundry.config import load_foundry_config

        config = load_foundry_config("configs/foundry.yaml")
        client = FoundryEvalClient(config)
        # If this doesn't raise, connection is valid
        assert client.project_client is not None

    def test_file_upload_and_delete(self):
        """Can upload a small test file and verify the file ID is returned."""
        import tempfile
        from pathlib import Path

        from src.foundry.client import FoundryEvalClient
        from src.foundry.config import load_foundry_config

        config = load_foundry_config("configs/foundry.yaml")
        client = FoundryEvalClient(config)

        # Create a tiny test JSONL
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            f.write(json.dumps({"prompt_id": "test_001", "prompt": "test"}) + "\n")
            tmp_path = Path(f.name)

        try:
            file_id = client.upload_data(tmp_path)
            assert file_id.startswith("file-"), f"Unexpected file ID format: {file_id}"
        finally:
            tmp_path.unlink(missing_ok=True)


@skip_no_env
class TestFoundryLivePipeline:
    """End-to-end pipeline test with a single prompt.

    This creates a real eval run in Foundry with 1 item.
    Only run when you want to validate the full pipeline.
    """

    def test_dry_run(self):
        """Dry run: transform + validate without calling Foundry API."""
        from pathlib import Path

        from src.foundry.config import load_foundry_config
        from src.foundry.transformer import transform_results

        config = load_foundry_config("configs/foundry.yaml")
        input_dir = Path("results/full-eval")

        if not (input_dir / "raw_results.jsonl").exists():
            pytest.skip("No local eval results — run local eval first")

        records, output_path = transform_results(input_dir, config.output.directory)
        assert len(records) > 0, "Transform produced no records"
        assert output_path.exists(), "Foundry input JSONL not created"
