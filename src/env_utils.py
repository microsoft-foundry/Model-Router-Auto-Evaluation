"""Shared utilities for environment variable substitution in YAML configs.

Used by both ``src.config`` and ``src.foundry.config`` to keep the
``${VAR_NAME}`` substitution logic in one place.
"""

from __future__ import annotations

import os
import re
from typing import Any


_ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


def substitute_env_vars(value: Any) -> Any:
    """Recursively substitute ``${VAR_NAME}`` patterns with environment variable values.

    Raises ``EnvironmentError`` if a referenced variable is not set.
    """
    if isinstance(value, str):
        def _replace(match: re.Match) -> str:
            var_name = match.group(1)
            env_val = os.environ.get(var_name)
            if env_val is None:
                raise EnvironmentError(
                    f"Environment variable '{var_name}' is not set. "
                    f"See .env.example for required variables."
                )
            return env_val
        return _ENV_VAR_PATTERN.sub(_replace, value)
    if isinstance(value, dict):
        return {k: substitute_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [substitute_env_vars(item) for item in value]
    return value


def substitute_env_vars_optional(value: Any) -> Any:
    """Like :func:`substitute_env_vars` but returns an empty string for missing vars.

    Useful for dry-run / validation flows where missing credentials should not
    abort config parsing.
    """
    if isinstance(value, str):
        def _replace(match: re.Match) -> str:
            return os.environ.get(match.group(1), "")
        return _ENV_VAR_PATTERN.sub(_replace, value)
    if isinstance(value, dict):
        return {k: substitute_env_vars_optional(v) for k, v in value.items()}
    if isinstance(value, list):
        return [substitute_env_vars_optional(item) for item in value]
    return value
