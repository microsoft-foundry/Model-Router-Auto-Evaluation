"""Tests for src/foundry/transformer.py."""

from __future__ import annotations

import json

from src.foundry.transformer import transform, transform_with_dataset


class TestTransform:
    def test_pairs_router_and_baseline(self, tmp_path, sample_raw_results, sample_results_json):
        output = tmp_path / "output" / "foundry_input.jsonl"
        count = transform(sample_raw_results, sample_results_json, output)

        assert count == 2
        assert output.exists()

        records = []
        with open(output) as f:
            for line in f:
                records.append(json.loads(line))

        assert len(records) == 2

        # Check first record has expected fields
        rec = records[0]
        assert rec["prompt_id"] == "p001"
        assert rec["router_response"] == "Router response 1"
        assert rec["baseline_response"] == "Baseline response 1"
        assert rec["router_model"] == "gpt-4o-mini"
        assert rec["baseline_model"] == "gpt-5"
        assert rec["router_latency_ms"] == 500.0
        assert rec["baseline_latency_ms"] == 1200.0
        assert rec["router_tokens"] == 60
        assert rec["baseline_tokens"] == 90

    def test_cost_estimation(self, tmp_path, sample_raw_results, sample_results_json):
        output = tmp_path / "output" / "foundry_input.jsonl"
        transform(sample_raw_results, sample_results_json, output)

        with open(output) as f:
            rec = json.loads(f.readline())

        # Cost should be positive (derived from results.json pricing)
        assert rec["router_cost_usd"] >= 0.0
        assert rec["baseline_cost_usd"] >= 0.0

    def test_no_matching_pairs(self, tmp_path, sample_results_json):
        # Create raw results with only router records (no baseline)
        raw = tmp_path / "raw_router_only.jsonl"
        with open(raw, "w") as f:
            f.write(json.dumps({
                "request_id": "r1",
                "prompt_id": "p001",
                "endpoint": "model_router",
                "model_name": "test",
                "response_text": "test",
                "prompt_tokens": 10,
                "completion_tokens": 10,
                "total_tokens": 20,
                "latency_ms": 100.0,
                "status": "success",
                "error_message": None,
                "timestamp": "2026-04-23T00:00:00Z",
            }) + "\n")

        output = tmp_path / "output" / "foundry_input.jsonl"
        count = transform(raw, sample_results_json, output)
        assert count == 0

    def test_creates_output_directory(self, tmp_path, sample_raw_results, sample_results_json):
        output = tmp_path / "deep" / "nested" / "dir" / "foundry_input.jsonl"
        count = transform(sample_raw_results, sample_results_json, output)
        assert count == 2
        assert output.parent.exists()


class TestTransformWithDataset:
    def test_enriches_with_dataset(self, tmp_path, sample_raw_results, sample_results_json):
        # Create a dataset file
        dataset = tmp_path / "dataset.jsonl"
        with open(dataset, "w") as f:
            f.write(json.dumps({"id": "p001", "prompt": "Hello world", "category": "general"}) + "\n")
            f.write(json.dumps({"id": "p002", "prompt": "Write code", "category": "coding"}) + "\n")

        output = tmp_path / "output" / "foundry_input.jsonl"
        count = transform_with_dataset(sample_raw_results, sample_results_json, dataset, output)

        assert count == 2

        records = []
        with open(output) as f:
            for line in f:
                records.append(json.loads(line))

        assert records[0]["prompt"] == "Hello world"
        assert records[0]["category"] == "general"
        assert records[1]["prompt"] == "Write code"
        assert records[1]["category"] == "coding"


EXPECTED_FIELDS = {
    "prompt_id", "prompt", "router_response", "baseline_response",
    "router_model", "baseline_model", "router_latency_ms", "baseline_latency_ms",
    "router_tokens", "baseline_tokens", "router_cost_usd", "baseline_cost_usd",
    "category",
}


class TestTransformFivePromptFixture:
    """Tests using the 5-prompt pre-built fixture files."""

    def _load_output(self, path):
        records = []
        with open(path) as f:
            for line in f:
                records.append(json.loads(line))
        return records

    def test_pairs_all_five_prompts(self, fixture_input_dir, tmp_path):
        output = tmp_path / "out" / "foundry_input.jsonl"
        raw = fixture_input_dir / "raw_results.jsonl"
        res = fixture_input_dir / "results.json"
        count = transform(raw, res, output)

        assert count == 5
        records = self._load_output(output)
        assert len(records) == 5

    def test_all_twelve_fields_present(self, fixture_input_dir, tmp_path):
        output = tmp_path / "out" / "foundry_input.jsonl"
        count = transform(
            fixture_input_dir / "raw_results.jsonl",
            fixture_input_dir / "results.json",
            output,
        )
        assert count == 5
        for rec in self._load_output(output):
            assert set(rec.keys()) == EXPECTED_FIELDS, f"Missing fields in {rec['prompt_id']}"

    def test_empty_baseline_response_preserved(self, fixture_input_dir, tmp_path):
        """tp003 baseline has empty response_text — should appear as empty string, not dropped."""
        output = tmp_path / "out" / "foundry_input.jsonl"
        transform(
            fixture_input_dir / "raw_results.jsonl",
            fixture_input_dir / "results.json",
            output,
        )
        records = {r["prompt_id"]: r for r in self._load_output(output)}
        assert records["tp003"]["baseline_response"] == ""

    def test_cost_when_tokens_diverge(self, fixture_input_dir, tmp_path):
        """Router and baseline have different token counts — costs should differ."""
        output = tmp_path / "out" / "foundry_input.jsonl"
        transform(
            fixture_input_dir / "raw_results.jsonl",
            fixture_input_dir / "results.json",
            output,
        )
        records = {r["prompt_id"]: r for r in self._load_output(output)}
        # tp001: router 65 tokens, baseline 95 tokens — costs should both be positive
        rec = records["tp001"]
        assert rec["router_cost_usd"] > 0
        assert rec["baseline_cost_usd"] > 0
        # Different token counts → different costs
        assert rec["router_cost_usd"] != rec["baseline_cost_usd"]

    def test_dataset_enrichment_with_fixture(self, fixture_input_dir, tmp_path):
        """transform_with_dataset should populate prompt text and category."""
        output = tmp_path / "out" / "foundry_input.jsonl"
        count = transform_with_dataset(
            fixture_input_dir / "raw_results.jsonl",
            fixture_input_dir / "results.json",
            fixture_input_dir / "sample_dataset.jsonl",
            output,
        )
        assert count == 5
        records = {r["prompt_id"]: r for r in self._load_output(output)}

        assert records["tp001"]["prompt"] == "Explain the difference between TCP and UDP protocols."
        assert records["tp001"]["category"] == "technical_knowledge"
        assert records["tp002"]["category"] == "code_generation"
        assert records["tp005"]["category"] == "general_knowledge"

    def test_mixed_router_models(self, fixture_input_dir, tmp_path):
        """Fixture has 3 different router models — all should be preserved."""
        output = tmp_path / "out" / "foundry_input.jsonl"
        transform(
            fixture_input_dir / "raw_results.jsonl",
            fixture_input_dir / "results.json",
            output,
        )
        models = {r["router_model"] for r in self._load_output(output)}
        assert "gpt-5-mini-2025-08-07" in models
        assert "grok-4-fast-reasoning" in models
        assert "gpt-oss-120b" in models
