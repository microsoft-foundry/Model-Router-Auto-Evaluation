"""Tests for src/dataset.py — JSONL, CSV, and database loading."""

import csv
import json
import sqlite3

import pytest

from src.dataset import load_dataset, DatasetValidationError


def _write_jsonl(path, records):
    """Helper to write records as JSONL."""
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def _write_csv(path, records, fieldnames=None):
    """Helper to write records as CSV."""
    if not records:
        path.write_text("")
        return
    if fieldnames is None:
        seen = set()
        fieldnames = []
        for r in records:
            for k in r:
                if k not in seen:
                    seen.add(k)
                    fieldnames.append(k)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in records:
            writer.writerow(r)


def _create_sqlite(path, table, records):
    """Helper to create a SQLite DB with a table from record dicts."""
    if not records:
        conn = sqlite3.connect(str(path))
        conn.execute(f'CREATE TABLE "{table}" (id TEXT, prompt TEXT)')
        conn.commit()
        conn.close()
        return
    seen = set()
    columns = []
    for r in records:
        for k in r:
            if k not in seen:
                seen.add(k)
                columns.append(k)
    conn = sqlite3.connect(str(path))
    col_defs = ", ".join(f'"{c}" TEXT' for c in columns)
    conn.execute(f'CREATE TABLE "{table}" ({col_defs})')
    placeholders = ", ".join("?" for _ in columns)
    for r in records:
        values = [r.get(c, "") for c in columns]
        conn.execute(f'INSERT INTO "{table}" VALUES ({placeholders})', values)
    conn.commit()
    conn.close()


class TestLoadDataset:
    def test_loads_valid_dataset(self, tmp_path):
        path = tmp_path / "data.jsonl"
        _write_jsonl(path, [
            {"id": "p1", "prompt": "Hello?"},
            {"id": "p2", "prompt": "World?", "category": "test", "difficulty": "easy"},
        ])
        prompts = load_dataset(path)
        assert len(prompts) == 2
        assert prompts[0].id == "p1"
        assert prompts[1].category == "test"
        assert prompts[1].difficulty == "easy"

    def test_missing_id_raises(self, tmp_path):
        path = tmp_path / "data.jsonl"
        _write_jsonl(path, [{"prompt": "No id here"}])
        with pytest.raises(DatasetValidationError, match="Missing required field 'id'"):
            load_dataset(path)

    def test_missing_prompt_raises(self, tmp_path):
        path = tmp_path / "data.jsonl"
        _write_jsonl(path, [{"id": "p1"}])
        with pytest.raises(DatasetValidationError, match="Missing required field 'prompt'"):
            load_dataset(path)

    def test_duplicate_id_raises(self, tmp_path):
        path = tmp_path / "data.jsonl"
        _write_jsonl(path, [
            {"id": "p1", "prompt": "First"},
            {"id": "p1", "prompt": "Duplicate"},
        ])
        with pytest.raises(DatasetValidationError, match="Duplicate id"):
            load_dataset(path)

    def test_invalid_difficulty_raises(self, tmp_path):
        path = tmp_path / "data.jsonl"
        _write_jsonl(path, [{"id": "p1", "prompt": "Test", "difficulty": "extreme"}])
        with pytest.raises(DatasetValidationError, match="Invalid difficulty"):
            load_dataset(path)

    def test_empty_file_raises(self, tmp_path):
        path = tmp_path / "data.jsonl"
        path.write_text("")
        with pytest.raises(DatasetValidationError, match="empty"):
            load_dataset(path)

    def test_file_not_found_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_dataset(tmp_path / "nonexistent.jsonl")

    def test_invalid_json_raises(self, tmp_path):
        path = tmp_path / "data.jsonl"
        path.write_text("not valid json\n")
        with pytest.raises(DatasetValidationError, match="Invalid JSON"):
            load_dataset(path)

    def test_sampling(self, tmp_path):
        path = tmp_path / "data.jsonl"
        records = [{"id": f"p{i}", "prompt": f"Prompt {i}"} for i in range(20)]
        _write_jsonl(path, records)
        prompts = load_dataset(path, sample_size=5, random_seed=42)
        assert len(prompts) == 5

    def test_sampling_reproducible(self, tmp_path):
        path = tmp_path / "data.jsonl"
        records = [{"id": f"p{i}", "prompt": f"Prompt {i}"} for i in range(20)]
        _write_jsonl(path, records)
        run1 = [p.id for p in load_dataset(path, sample_size=5, random_seed=42)]
        run2 = [p.id for p in load_dataset(path, sample_size=5, random_seed=42)]
        assert run1 == run2

    def test_sampling_larger_than_dataset(self, tmp_path):
        path = tmp_path / "data.jsonl"
        _write_jsonl(path, [{"id": "p1", "prompt": "Only one"}])
        prompts = load_dataset(path, sample_size=100)
        assert len(prompts) == 1  # Returns all, doesn't error

    def test_optional_fields_default(self, tmp_path):
        path = tmp_path / "data.jsonl"
        _write_jsonl(path, [{"id": "p1", "prompt": "Minimal"}])
        prompts = load_dataset(path)
        assert prompts[0].category is None
        assert prompts[0].difficulty is None
        assert prompts[0].ground_truth is None
        assert prompts[0].metadata == {}


class TestLoadCSV:
    def test_loads_valid_csv(self, tmp_path):
        path = tmp_path / "data.csv"
        _write_csv(path, [
            {"id": "p1", "prompt": "Hello?"},
            {"id": "p2", "prompt": "World?", "category": "test", "difficulty": "easy"},
        ])
        prompts = load_dataset(path)
        assert len(prompts) == 2
        assert prompts[0].id == "p1"
        assert prompts[1].category == "test"
        assert prompts[1].difficulty == "easy"

    def test_csv_minimal_fields(self, tmp_path):
        path = tmp_path / "data.csv"
        _write_csv(path, [{"id": "p1", "prompt": "Just the basics"}])
        prompts = load_dataset(path)
        assert prompts[0].category is None
        assert prompts[0].difficulty is None
        assert prompts[0].metadata == {}

    def test_csv_missing_id_raises(self, tmp_path):
        path = tmp_path / "data.csv"
        _write_csv(path, [{"prompt": "No id"}], fieldnames=["prompt"])
        with pytest.raises(DatasetValidationError, match="Missing required field 'id'"):
            load_dataset(path)

    def test_csv_missing_prompt_raises(self, tmp_path):
        path = tmp_path / "data.csv"
        _write_csv(path, [{"id": "p1"}], fieldnames=["id"])
        with pytest.raises(DatasetValidationError, match="Missing required field 'prompt'"):
            load_dataset(path)

    def test_csv_duplicate_id_raises(self, tmp_path):
        path = tmp_path / "data.csv"
        _write_csv(path, [
            {"id": "p1", "prompt": "First"},
            {"id": "p1", "prompt": "Dup"},
        ])
        with pytest.raises(DatasetValidationError, match="Duplicate id"):
            load_dataset(path)

    def test_csv_empty_raises(self, tmp_path):
        path = tmp_path / "data.csv"
        path.write_text("id,prompt\n")  # header only
        with pytest.raises(DatasetValidationError, match="empty"):
            load_dataset(path)

    def test_csv_sampling(self, tmp_path):
        path = tmp_path / "data.csv"
        records = [{"id": f"p{i}", "prompt": f"Prompt {i}"} for i in range(20)]
        _write_csv(path, records)
        prompts = load_dataset(path, sample_size=5, random_seed=42)
        assert len(prompts) == 5

    def test_csv_with_metadata_json(self, tmp_path):
        path = tmp_path / "data.csv"
        _write_csv(
            path,
            [{"id": "p1", "prompt": "Test", "metadata": '{"source": "wiki"}'}],
            fieldnames=["id", "prompt", "metadata"],
        )
        prompts = load_dataset(path)
        assert prompts[0].metadata == {"source": "wiki"}


class TestLoadSQLite:
    def test_loads_valid_sqlite(self, tmp_path):
        db_path = tmp_path / "data.db"
        _create_sqlite(db_path, "prompts", [
            {"id": "p1", "prompt": "Hello?"},
            {"id": "p2", "prompt": "World?", "category": "test", "difficulty": "easy"},
        ])
        conn_str = f"sqlite:///{db_path}?table=prompts"
        prompts = load_dataset(conn_str)
        assert len(prompts) == 2
        assert prompts[0].id == "p1"
        assert prompts[1].category == "test"

    def test_sqlite_minimal_fields(self, tmp_path):
        db_path = tmp_path / "data.db"
        _create_sqlite(db_path, "prompts", [
            {"id": "p1", "prompt": "Minimal"},
        ])
        prompts = load_dataset(f"sqlite:///{db_path}?table=prompts")
        assert prompts[0].category is None
        assert prompts[0].metadata == {}

    def test_sqlite_missing_table_param_raises(self, tmp_path):
        db_path = tmp_path / "data.db"
        _create_sqlite(db_path, "prompts", [{"id": "p1", "prompt": "Test"}])
        with pytest.raises(DatasetValidationError, match="table"):
            load_dataset(f"sqlite:///{db_path}")

    def test_sqlite_missing_id_raises(self, tmp_path):
        db_path = tmp_path / "data.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute('CREATE TABLE prompts (prompt TEXT)')
        conn.execute('INSERT INTO prompts VALUES (?)', ("No id",))
        conn.commit()
        conn.close()
        with pytest.raises(DatasetValidationError, match="Missing required field 'id'"):
            load_dataset(f"sqlite:///{db_path}?table=prompts")

    def test_sqlite_duplicate_id_raises(self, tmp_path):
        db_path = tmp_path / "data.db"
        _create_sqlite(db_path, "prompts", [
            {"id": "p1", "prompt": "First"},
            {"id": "p1", "prompt": "Dup"},
        ])
        with pytest.raises(DatasetValidationError, match="Duplicate id"):
            load_dataset(f"sqlite:///{db_path}?table=prompts")

    def test_sqlite_empty_raises(self, tmp_path):
        db_path = tmp_path / "data.db"
        _create_sqlite(db_path, "prompts", [])
        with pytest.raises(DatasetValidationError, match="empty"):
            load_dataset(f"sqlite:///{db_path}?table=prompts")

    def test_sqlite_file_not_found_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_dataset(f"sqlite:///{tmp_path}/missing.db?table=prompts")

    def test_sqlite_invalid_table_name_raises(self, tmp_path):
        db_path = tmp_path / "data.db"
        _create_sqlite(db_path, "prompts", [{"id": "p1", "prompt": "Test"}])
        with pytest.raises(DatasetValidationError, match="Invalid table name"):
            load_dataset(f"sqlite:///{db_path}?table=DROP TABLE;--")

    def test_sqlite_sampling(self, tmp_path):
        db_path = tmp_path / "data.db"
        records = [{"id": f"p{i}", "prompt": f"Prompt {i}"} for i in range(20)]
        _create_sqlite(db_path, "prompts", records)
        prompts = load_dataset(f"sqlite:///{db_path}?table=prompts", sample_size=5)
        assert len(prompts) == 5
