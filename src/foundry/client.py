"""Foundry Evaluation SDK client wrapper.

Wraps AIProjectClient and the OpenAI evals API to provide a clean interface
for creating evaluations, running them, polling for completion, and
retrieving results.

Requires: pip install -e ".[foundry]"
Requires: az login (DefaultAzureCredential)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class EvalRunResult:
    """Result of a completed Foundry evaluation run."""
    eval_id: str
    run_id: str
    status: str
    report_url: Optional[str] = None
    output_items: List[Dict[str, Any]] = field(default_factory=list)
    result_counts: Dict[str, int] = field(default_factory=dict)


class FoundryEvalClient:
    """Client for Microsoft Foundry Evaluation SDK.

    Wraps the AIProjectClient → OpenAI evals API flow:
    1. Upload data source (JSONL)
    2. Create eval with testing criteria
    3. Create and run eval
    4. Poll for completion
    5. Retrieve results
    """

    def __init__(
        self,
        project_endpoint: str,
        model_deployment_name: str,
    ):
        self._endpoint = project_endpoint
        self._deployment = model_deployment_name
        self._project_client = None
        self._openai_client = None

    def connect(self) -> None:
        """Establish connection to Microsoft Foundry.

        Uses DefaultAzureCredential — requires `az login`.
        """
        from azure.ai.projects import AIProjectClient
        from azure.identity import DefaultAzureCredential

        self._project_client = AIProjectClient(
            endpoint=self._endpoint,
            credential=DefaultAzureCredential(),
        )
        self._openai_client = self._project_client.get_openai_client()

    @property
    def project_client(self):
        """Access the underlying AIProjectClient."""
        if self._project_client is None:
            raise RuntimeError("Not connected. Call connect() first.")
        return self._project_client

    @property
    def openai_client(self):
        """Access the underlying OpenAI client (evals API)."""
        if self._openai_client is None:
            raise RuntimeError("Not connected. Call connect() first.")
        return self._openai_client

    def upload_file(self, file_path: Path, max_size_bytes: int = 100 * 1024 * 1024) -> str:
        """Upload a JSONL file for use as eval data source.

        Args:
            file_path: Path to the JSONL file.
            max_size_bytes: Maximum allowed upload size (default 100 MiB) to guard
                against accidentally uploading huge files. Raise a friendlier error
                before the SDK call than waiting for a server-side rejection.

        Returns:
            The file ID from the upload.

        Raises:
            FileNotFoundError: If ``file_path`` does not exist.
            ValueError: If the file is empty or exceeds ``max_size_bytes``.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Upload file not found: {file_path}")
        size = file_path.stat().st_size
        if size == 0:
            raise ValueError(f"Upload file is empty: {file_path}")
        if size > max_size_bytes:
            raise ValueError(
                f"Upload file {file_path} is {size:,} bytes, "
                f"exceeds limit of {max_size_bytes:,} bytes"
            )
        client = self.openai_client
        with open(file_path, "rb") as f:
            uploaded = client.files.create(file=f, purpose="evals")
        return uploaded.id

    def create_eval(
        self,
        name: str,
        testing_criteria: List[Dict[str, Any]],
    ) -> str:
        """Create an evaluation with testing criteria.

        Args:
            name: Name for the evaluation.
            testing_criteria: List of grader/evaluator configurations.

        Returns:
            The eval ID.
        """
        client = self.openai_client
        eval_obj = client.evals.create(
            name=name,
            data_source_config={
                "type": "custom",
                "item_schema": {
                    "type": "object",
                    "properties": {
                        "prompt_id": {"type": "string"},
                        "prompt": {"type": "string"},
                        "router_response": {"type": "string"},
                        "baseline_response": {"type": "string"},
                        "router_model": {"type": "string"},
                        "baseline_model": {"type": "string"},
                        "router_latency_ms": {"type": "number"},
                        "baseline_latency_ms": {"type": "number"},
                        "router_tokens": {"type": "integer"},
                        "baseline_tokens": {"type": "integer"},
                        "router_cost_usd": {"type": "number"},
                        "baseline_cost_usd": {"type": "number"},
                        "category": {"type": "string"},
                    },
                },
            },
            testing_criteria=testing_criteria,
        )
        return eval_obj.id

    def create_run(
        self,
        eval_id: str,
        run_name: str,
        file_id: str,
    ) -> str:
        """Create and start an eval run.

        Args:
            eval_id: The evaluation to run.
            run_name: A descriptive name for this run.
            file_id: The uploaded data file ID.

        Returns:
            The run ID.
        """
        client = self.openai_client
        run = client.evals.runs.create(
            eval_id=eval_id,
            name=run_name,
            data_source={
                "type": "jsonl",
                "source": {
                    "type": "file_id",
                    "id": file_id,
                },
            },
        )
        return run.id

    def poll_run(
        self,
        eval_id: str,
        run_id: str,
        poll_interval: float = 5.0,
        max_wait: float = 600.0,
    ) -> str:
        """Poll an eval run until it completes or times out.

        Args:
            eval_id: The evaluation ID.
            run_id: The run ID.
            poll_interval: Seconds between polls.
            max_wait: Maximum seconds to wait.

        Returns:
            The final run status string.
        """
        client = self.openai_client
        elapsed = 0.0
        while elapsed < max_wait:
            run = client.evals.runs.retrieve(eval_id=eval_id, run_id=run_id)
            status = run.status
            if status in ("completed", "failed", "cancelled"):
                return status
            time.sleep(poll_interval)
            elapsed += poll_interval
        return "timeout"

    def get_results(self, eval_id: str, run_id: str) -> EvalRunResult:
        """Retrieve results from a completed eval run.

        Args:
            eval_id: The evaluation ID.
            run_id: The run ID.

        Returns:
            EvalRunResult with output items and metadata.
        """
        client = self.openai_client
        run = client.evals.runs.retrieve(eval_id=eval_id, run_id=run_id)

        output_items = []
        page = client.evals.runs.output_items.list(eval_id=eval_id, run_id=run_id)
        for item in page:
            output_items.append(_output_item_to_dict(item))

        raw_counts = getattr(run, "result_counts", None)
        if raw_counts is not None and not isinstance(raw_counts, dict):
            # SDK returns a ResultCounts object — convert to dict
            if hasattr(raw_counts, "model_dump"):
                counts = raw_counts.model_dump()
            elif hasattr(raw_counts, "__dict__"):
                counts = {k: v for k, v in raw_counts.__dict__.items() if not k.startswith("_")}
            else:
                counts = {}
        else:
            counts = raw_counts or {}

        return EvalRunResult(
            eval_id=eval_id,
            run_id=run_id,
            status=run.status,
            report_url=getattr(run, "report_url", None),
            output_items=output_items,
            result_counts=counts,
        )

    def register_evaluator(
        self,
        evaluator_name: str,
        code: str,
        deployment_name: str,
        pass_threshold: float,
    ) -> str:
        """Register a code-based custom evaluator.

        Uses the beta.evaluators.create_version API (azure-ai-projects >= 2.1.0).

        Args:
            evaluator_name: Unique name for the evaluator.
            code: Python source code for the evaluator.
            deployment_name: Model deployment name (required init param).
            pass_threshold: Score threshold for pass/fail.

        Returns:
            The evaluator ID.
        """
        evaluator = self.project_client.beta.evaluators.create_version(
            name=evaluator_name,
            evaluator_version={
                "display_name": f"Model Router {evaluator_name}",
                "description": f"Model Router {evaluator_name} comparison evaluator",
                "evaluator_type": "custom",
                "categories": [],
                "definition": {
                    "type": "code",
                    "code_text": code,
                    "init_parameters": {
                        "type": "object",
                        "properties": {
                            "deployment_name": {
                                "type": "string",
                                "default": deployment_name,
                            },
                            "pass_threshold": {
                                "type": "number",
                                "default": pass_threshold,
                            },
                        },
                    },
                    "metrics": {
                        "score": {
                            "type": "continuous",
                            "desirable_direction": "increase",
                            "min_value": 0.0,
                            "max_value": 1.0,
                            "threshold": pass_threshold,
                            "is_primary": True,
                        },
                    },
                },
            },
        )
        return getattr(evaluator, "id", evaluator_name)


def _output_item_to_dict(item: Any) -> Dict[str, Any]:
    """Convert an output item to a plain dict, handling SDK objects."""
    if hasattr(item, "model_dump"):
        return item.model_dump()
    elif hasattr(item, "__dict__"):
        return {k: v for k, v in item.__dict__.items() if not k.startswith("_")}
    return {"raw": str(item)}
