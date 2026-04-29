"""Tests for src/config.py — YAML loading and env var substitution."""

import pytest
import yaml

from src.config import load_config, _substitute_env_vars


class TestEnvVarSubstitution:
    def test_simple_substitution(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "hello")
        assert _substitute_env_vars("${TEST_VAR}") == "hello"

    def test_nested_dict(self, monkeypatch):
        monkeypatch.setenv("KEY1", "val1")
        monkeypatch.setenv("KEY2", "val2")
        result = _substitute_env_vars({"a": "${KEY1}", "b": {"c": "${KEY2}"}})
        assert result == {"a": "val1", "b": {"c": "val2"}}

    def test_list_substitution(self, monkeypatch):
        monkeypatch.setenv("ITEM", "value")
        result = _substitute_env_vars(["${ITEM}", "static"])
        assert result == ["value", "static"]

    def test_missing_env_var_raises(self):
        with pytest.raises(EnvironmentError, match="not set"):
            _substitute_env_vars("${DEFINITELY_NOT_SET_12345}")

    def test_non_string_passthrough(self):
        assert _substitute_env_vars(42) == 42
        assert _substitute_env_vars(True) is True
        assert _substitute_env_vars(None) is None


class TestLoadConfig:
    def _write_config(self, path, config_dict):
        with open(path, "w") as f:
            yaml.dump(config_dict, f)

    def _minimal_config(self):
        return {
            "evaluation": {
                "name": "test",
                "dataset": "data.jsonl",
                "sample_size": None,
                "random_seed": 42,
            },
            "endpoints": {
                "model_router": {
                    "type": "azure_openai",
                    "endpoint_url": "https://test.openai.azure.com",
                    "api_key": "test-key",
                    "deployment_name": "model-router",
                },
                "baseline": {
                    "type": "azure_openai",
                    "endpoint_url": "https://test.openai.azure.com",
                    "api_key": "test-key",
                    "deployment_name": "gpt-4o",
                },
            },
            "pricing": {
                "model_router": {"input": 0.5, "output": 1.5},
                "gpt-4o": {"input": 2.5, "output": 10.0},
            },
            "concurrency": {
                "max_parallel_requests": 5,
                "request_timeout_seconds": 60,
                "max_retries": 3,
            },
            "output": {
                "directory": "results",
                "formats": ["markdown", "csv"],
            },
        }

    def test_loads_valid_config(self, tmp_path):
        path = tmp_path / "config.yaml"
        self._write_config(path, self._minimal_config())
        config = load_config(path)
        assert config.name == "test"
        assert config.model_router.deployment_name == "model-router"
        assert config.baseline.deployment_name == "gpt-4o"

    def test_file_not_found_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nonexistent.yaml")

    def test_missing_section_raises(self, tmp_path):
        path = tmp_path / "config.yaml"
        config = self._minimal_config()
        del config["endpoints"]
        self._write_config(path, config)
        with pytest.raises(ValueError, match="Missing required config section"):
            load_config(path)

    def test_missing_endpoint_raises(self, tmp_path):
        path = tmp_path / "config.yaml"
        config = self._minimal_config()
        del config["endpoints"]["baseline"]
        self._write_config(path, config)
        with pytest.raises(ValueError, match="Missing required endpoint"):
            load_config(path)

    def test_env_var_in_config(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TEST_ENDPOINT", "https://resolved.openai.azure.com")
        monkeypatch.setenv("TEST_KEY", "resolved-key")

        config_dict = self._minimal_config()
        config_dict["endpoints"]["model_router"]["endpoint_url"] = "${TEST_ENDPOINT}"
        config_dict["endpoints"]["model_router"]["api_key"] = "${TEST_KEY}"

        path = tmp_path / "config.yaml"
        self._write_config(path, config_dict)
        config = load_config(path)
        assert config.model_router.endpoint_url == "https://resolved.openai.azure.com"
        assert config.model_router.api_key == "resolved-key"

    def test_default_values(self, tmp_path):
        path = tmp_path / "config.yaml"
        config_dict = self._minimal_config()
        # Remove optional fields to test defaults
        del config_dict["evaluation"]["name"]
        self._write_config(path, config_dict)
        config = load_config(path)
        assert config.name == "unnamed-eval"
