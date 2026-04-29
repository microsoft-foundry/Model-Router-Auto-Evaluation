"""Dataset loading, validation, and sampling.

Supported sources:
  - JSONL files (.jsonl)
  - CSV files (.csv)
  - SQLite databases (connection string: sqlite:///path/to/db.sqlite?table=prompts)
  - SQL databases via SQLAlchemy (any connection string SQLAlchemy accepts,
    with a ``table`` query-parameter, e.g. postgresql://user:pw@host/db?table=prompts)
"""

from __future__ import annotations

import csv
import json
import random
import re
import sqlite3
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse


@dataclass
class Prompt:
    """A single evaluation prompt."""
    id: str
    prompt: str
    category: Optional[str] = None
    difficulty: Optional[str] = None
    ground_truth: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class DatasetValidationError(Exception):
    """Raised when dataset validation fails."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_VALID_DIFFICULTIES = ("easy", "medium", "hard")


def _validate_and_append(
    record: Dict[str, Any],
    prompts: List[Prompt],
    seen_ids: set,
    label: str,
) -> None:
    """Validate a single record dict and append a Prompt to *prompts*.

    Args:
        record: Dict with at least ``id`` and ``prompt`` keys.
        prompts: Accumulator list — a new Prompt is appended on success.
        seen_ids: Set of ids already seen (mutated in-place).
        label: Human-readable location string for error messages (e.g. "Row 3").
    """
    if "id" not in record:
        raise DatasetValidationError(f"{label}: Missing required field 'id'")
    if "prompt" not in record:
        raise DatasetValidationError(f"{label}: Missing required field 'prompt'")

    prompt_id = str(record["id"])
    if prompt_id in seen_ids:
        raise DatasetValidationError(f"{label}: Duplicate id '{prompt_id}'")
    seen_ids.add(prompt_id)

    difficulty = record.get("difficulty") or None
    if difficulty is not None and difficulty not in _VALID_DIFFICULTIES:
        raise DatasetValidationError(
            f"{label}: Invalid difficulty '{difficulty}'. "
            f"Must be one of: {', '.join(_VALID_DIFFICULTIES)}"
        )

    metadata = record.get("metadata", {})
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (json.JSONDecodeError, TypeError):
            metadata = {}

    prompts.append(Prompt(
        id=prompt_id,
        prompt=record["prompt"],
        category=record.get("category") or None,
        difficulty=difficulty,
        ground_truth=record.get("ground_truth") or None,
        metadata=metadata if isinstance(metadata, dict) else {},
    ))


def _sample(
    prompts: List[Prompt],
    sample_size: Optional[int],
    random_seed: int,
) -> List[Prompt]:
    """Optionally sample a subset of prompts."""
    if sample_size is None:
        return prompts
    if sample_size <= 0:
        raise DatasetValidationError(f"sample_size must be positive, got {sample_size}")
    if sample_size > len(prompts):
        print(
            f"Warning: sample_size ({sample_size}) > dataset size ({len(prompts)}). "
            f"Using all {len(prompts)} prompts."
        )
        return prompts
    rng = random.Random(random_seed)
    return rng.sample(prompts, sample_size)


# ---------------------------------------------------------------------------
# JSONL loader
# ---------------------------------------------------------------------------

def _load_jsonl(path: Path) -> List[Prompt]:
    prompts: List[Prompt] = []
    seen_ids: set = set()

    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as e:
                raise DatasetValidationError(
                    f"Line {line_num}: Invalid JSON — {e}"
                )
            _validate_and_append(record, prompts, seen_ids, f"Line {line_num}")
    return prompts


# ---------------------------------------------------------------------------
# CSV loader
# ---------------------------------------------------------------------------

def _load_csv(path: Path) -> List[Prompt]:
    prompts: List[Prompt] = []
    seen_ids: set = set()

    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise DatasetValidationError("CSV file has no header row")
        for row_num, row in enumerate(reader, start=2):  # row 1 = header
            record: Dict[str, Any] = {k: v for k, v in row.items() if v}
            # Attempt to parse a JSON metadata column
            if "metadata" in row and row["metadata"]:
                try:
                    record["metadata"] = json.loads(row["metadata"])
                except (json.JSONDecodeError, TypeError):
                    record["metadata"] = {}
            _validate_and_append(record, prompts, seen_ids, f"Row {row_num}")
    return prompts


# ---------------------------------------------------------------------------
# Database loader
# ---------------------------------------------------------------------------

_SQLITE_RE = re.compile(r"^sqlite:///(.+)$", re.IGNORECASE)


def _parse_db_connection(connection_string: str):
    """Return (db_path_or_url, table_name, is_sqlite)."""
    parsed = urlparse(connection_string)
    qs = parse_qs(parsed.query)
    table = qs.get("table", [None])[0]
    if not table:
        raise DatasetValidationError(
            "Database connection string must include a 'table' query parameter, "
            "e.g. sqlite:///data.db?table=prompts"
        )

    # Strip the ?table=... from the connection string for SQLAlchemy / sqlite3
    base_url = connection_string.split("?")[0]

    m = _SQLITE_RE.match(base_url)
    if m:
        return m.group(1), table, True
    return base_url, table, False


def _load_from_database(
    connection_string: str,
) -> List[Prompt]:
    """Load prompts from a SQL database.

    Connection string formats:
      - SQLite (stdlib):  sqlite:///path/to/db.sqlite?table=prompts
      - Other DBs (requires sqlalchemy): postgresql://user:pw@host/db?table=prompts
    """
    db_path_or_url, table, is_sqlite = _parse_db_connection(connection_string)

    if is_sqlite:
        return _load_sqlite(db_path_or_url, table)
    return _load_sqlalchemy(connection_string.split("?")[0], table)


def _load_sqlite(db_path: str, table: str) -> List[Prompt]:
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(f"SQLite database not found: {path}")

    # Sanitise table name — only allow alphanumeric and underscores
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", table):
        raise DatasetValidationError(f"Invalid table name: {table!r}")

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(f'SELECT * FROM "{table}"')  # noqa: S608
        rows = cursor.fetchall()
    except sqlite3.OperationalError as e:
        raise DatasetValidationError(f"SQLite error: {e}") from e
    finally:
        conn.close()

    prompts: List[Prompt] = []
    seen_ids: set = set()
    for idx, row in enumerate(rows, start=1):
        record = dict(row)
        _validate_and_append(record, prompts, seen_ids, f"DB row {idx}")
    return prompts


def _load_sqlalchemy(url: str, table: str) -> List[Prompt]:
    try:
        import sqlalchemy  # noqa: F401
    except ImportError:
        raise DatasetValidationError(
            "sqlalchemy is required for non-SQLite database connections. "
            "Install it with:  pip install sqlalchemy"
        )

    # Sanitise table name
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", table):
        raise DatasetValidationError(f"Invalid table name: {table!r}")

    from sqlalchemy import create_engine, text

    engine = create_engine(url)
    with engine.connect() as conn:
        result = conn.execute(text(f'SELECT * FROM "{table}"'))  # noqa: S608
        columns = list(result.keys())
        rows = result.fetchall()

    prompts: List[Prompt] = []
    seen_ids: set = set()
    for idx, row in enumerate(rows, start=1):
        record = dict(zip(columns, row))
        _validate_and_append(record, prompts, seen_ids, f"DB row {idx}")
    return prompts


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_dataset(
    dataset_path: str | Path,
    sample_size: Optional[int] = None,
    random_seed: int = 42,
) -> List[Prompt]:
    """Load and validate a dataset from JSONL, CSV, or a database.

    Args:
        dataset_path: Path to a .jsonl / .csv file, or a database connection
            string (e.g. ``sqlite:///data.db?table=prompts``).
        sample_size: If set, randomly sample this many prompts. None = use all.
        random_seed: Seed for reproducible sampling.

    Returns:
        List of validated Prompt objects.

    Raises:
        FileNotFoundError: If the dataset file / database doesn't exist.
        DatasetValidationError: If any record fails validation.
    """
    path_str = str(dataset_path)

    # Database connection string
    if "://" in path_str:
        prompts = _load_from_database(path_str)
    else:
        path = Path(path_str)
        if not path.exists():
            raise FileNotFoundError(f"Dataset file not found: {path}")

        suffix = path.suffix.lower()
        if suffix == ".csv":
            prompts = _load_csv(path)
        elif suffix in (".jsonl", ".json", ".ndjson"):
            prompts = _load_jsonl(path)
        else:
            # Default to JSONL for unknown extensions
            prompts = _load_jsonl(path)

    if not prompts:
        raise DatasetValidationError("Dataset is empty — no valid records found")

    return _sample(prompts, sample_size, random_seed)
