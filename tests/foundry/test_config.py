"""Tests for src/foundry/config.py."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from src.foundry.config import load_foundry_config


class TestLoadFoundryConfig:
    def test_loads_valid_config(self, tmp_path):
        config_yaml = tmp_path / "foundry.yaml"
        config_yaml.write_text("""
foundry:
  project_endpoint: "https://test.services.ai.azure.com"
  model_deployment_name: "gpt-5"

graders:
  quality:
    enabled: true
    pass_threshold: 3
    range: [1, 5]
  cost:
    enabled: true
    evaluator_name: "mr_cost_comparison"
    pass_threshold: 0.5
  latency:
    enabled: true
    evaluator_name: "mr_latency_comparison"
    pass_threshold: 0.5

output:
  directory: "results/foundry-eval"
  formats: ["markdown", "json"]
""")

        config = load_foundry_config(config_yaml, strict=False)

        assert config.foundry.project_endpoint == "https://test.services.ai.azure.com"
        assert config.foundry.model_deployment_name == "gpt-5"
        assert config.quality.enabled is True
        assert config.quality.pass_threshold == 3
        assert config.cost.evaluator_name == "mr_cost_comparison"
        assert config.latency.evaluator_name == "mr_latency_comparison"

    def test_env_var_substitution(self, tmp_path):
        config_yaml = tmp_path / "foundry.yaml"
        config_yaml.write_text("""
foundry:
  project_endpoint: "${TEST_PROJECT_ENDPOINT}"
  model_deployment_name: "${TEST_DEPLOYMENT}"
""")

        with patch.dict(os.environ, {
            "TEST_PROJECT_ENDPOINT": "https://real.services.ai.azure.com",
            "TEST_DEPLOYMENT": "gpt-5-real",
        }):
            config = load_foundry_config(config_yaml, strict=True)

        assert config.foundry.project_endpoint == "https://real.services.ai.azure.com"
        assert config.foundry.model_deployment_name == "gpt-5-real"

    def test_missing_env_var_strict(self, tmp_path):
        config_yaml = tmp_path / "foundry.yaml"
        config_yaml.write_text("""
foundry:
  project_endpoint: "${NONEXISTENT_VAR}"
  model_deployment_name: "test"
""")

        with pytest.raises(EnvironmentError, match="NONEXISTENT_VAR"):
            load_foundry_config(config_yaml, strict=True)

    def test_missing_env_var_nonstrict(self, tmp_path):
        config_yaml = tmp_path / "foundry.yaml"
        config_yaml.write_text("""
foundry:
  project_endpoint: "${NONEXISTENT_VAR}"
  model_deployment_name: "test"
""")

        config = load_foundry_config(config_yaml, strict=False)
        assert config.foundry.project_endpoint == ""

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_foundry_config("nonexistent.yaml")

    def test_loads_real_foundry_yaml_nonstrict(self):
        """Real configs/foundry.yaml should parse in non-strict mode (env vars empty)."""
        config = load_foundry_config("configs/foundry.yaml", strict=False)
        assert config.quality.enabled is True
        assert config.cost.evaluator_name == "mr_cost_comparison"
        assert config.latency.evaluator_name == "mr_latency_comparison"
        assert config.quality.pass_threshold == 3
        assert config.quality.range == [1, 5]

    def test_graders_disabled(self, tmp_path):
        """All graders disabled should produce a valid config."""
        config_yaml = tmp_path / "foundry.yaml"
        config_yaml.write_text("""
foundry:
  project_endpoint: "https://test.services.ai.azure.com"
  model_deployment_name: "gpt-5"

graders:
  quality:
    enabled: false
    pass_threshold: 3
    range: [1, 5]
  cost:
    enabled: false
    evaluator_name: "mr_cost_comparison"
    pass_threshold: 0.5
  latency:
    enabled: false
    evaluator_name: "mr_latency_comparison"
    pass_threshold: 0.5

output:
  directory: "results/foundry-eval"
  formats: ["markdown", "json"]
""")

        config = load_foundry_config(config_yaml, strict=False)
        assert config.quality.enabled is False
        assert config.cost.enabled is False
        assert config.latency.enabled is False
