"""LLM-as-a-judge quality evaluation with anti-bias measures.

Supports two scoring modes:
  - **Pairwise**: Compare two responses, pick a winner (with dual-ordering to cancel position bias).
  - **Absolute**: Score each response independently on a 1-5 scale across multiple dimensions.
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from openai import AsyncAzureOpenAI, AsyncOpenAI

from .config import EndpointConfig


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class AbsoluteScore:
    """Score for a single response on multiple dimensions (1-5 each)."""
    accuracy: int
    completeness: int
    clarity: int
    helpfulness: int

    @property
    def overall(self) -> float:
        """Weighted average — equal weights by default."""
        return (self.accuracy + self.completeness + self.clarity + self.helpfulness) / 4.0


@dataclass
class PairwiseVerdict:
    """Result of a single pairwise comparison (one ordering)."""
    winner: str  # "A" | "B" | "TIE"
    raw_output: str


@dataclass
class JudgeResult:
    """Complete judge evaluation for one prompt."""
    prompt_id: str

    # Pairwise (dual-ordering: router_first + baseline_first)
    pairwise_router_first: Optional[PairwiseVerdict] = None
    pairwise_baseline_first: Optional[PairwiseVerdict] = None
    pairwise_winner: Optional[str] = None  # "model_router" | "baseline" | "tie"

    # Absolute scores
    router_score: Optional[AbsoluteScore] = None
    baseline_score: Optional[AbsoluteScore] = None

    # Metadata
    judge_model: str = ""
    latency_ms: float = 0.0
    error: Optional[str] = None


# ── Prompt template loading ──────────────────────────────────────────────────

@dataclass
class PromptTemplate:
    """A judge prompt template with system + user parts."""
    system: str
    user: str


def load_prompt_template(path: str | Path) -> PromptTemplate:
    """Load a YAML judge prompt template."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Judge prompt template not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return PromptTemplate(
        system=data.get("system", "").strip(),
        user=data.get("user", "").strip(),
    )


# ── Parsing helpers ──────────────────────────────────────────────────────────

_VERDICT_PATTERN = re.compile(r"VERDICT:\s*(A_BETTER|B_BETTER|TIE)", re.IGNORECASE)
_SCORES_PATTERN = re.compile(
    r"SCORES:\s*accuracy=(\d)\s+completeness=(\d)\s+clarity=(\d)\s+helpfulness=(\d)",
    re.IGNORECASE,
)


def _parse_pairwise_verdict(text: str) -> PairwiseVerdict:
    """Parse a pairwise judge response into a verdict."""
    match = _VERDICT_PATTERN.search(text)
    if not match:
        raise ValueError("Judge response did not contain a valid VERDICT line")
    raw = match.group(1).upper()
    winner = {"A_BETTER": "A", "B_BETTER": "B", "TIE": "TIE"}[raw]
    return PairwiseVerdict(winner=winner, raw_output=text)


def _parse_absolute_scores(text: str) -> Optional[AbsoluteScore]:
    """Parse an absolute scoring judge response into scores."""
    match = _SCORES_PATTERN.search(text)
    if not match:
        return None

    def _clamp(v: int) -> int:
        return max(1, min(5, v))

    return AbsoluteScore(
        accuracy=_clamp(int(match.group(1))),
        completeness=_clamp(int(match.group(2))),
        clarity=_clamp(int(match.group(3))),
        helpfulness=_clamp(int(match.group(4))),
    )


def _resolve_dual_ordering(
    router_first: PairwiseVerdict,
    baseline_first: PairwiseVerdict,
) -> str:
    """Resolve final winner from dual-ordering pairwise results.

    Anti-bias logic:
      - If both orderings agree, that's the winner.
      - If they disagree (position bias detected), call it a tie.
    """
    # Map verdicts back to endpoint names
    # router_first ordering: A=router, B=baseline
    if router_first.winner == "A":
        verdict_1 = "model_router"
    elif router_first.winner == "B":
        verdict_1 = "baseline"
    else:
        verdict_1 = "tie"

    # baseline_first ordering: A=baseline, B=router
    if baseline_first.winner == "A":
        verdict_2 = "baseline"
    elif baseline_first.winner == "B":
        verdict_2 = "model_router"
    else:
        verdict_2 = "tie"

    # Both must agree for a non-tie result
    if verdict_1 == verdict_2:
        return verdict_1
    return "tie"


# ── Judge client ─────────────────────────────────────────────────────────────

def _build_judge_client(config: EndpointConfig) -> AsyncAzureOpenAI | AsyncOpenAI:
    """Build an async client for the judge model."""
    if config.type == "azure_openai":
        return AsyncAzureOpenAI(
            azure_endpoint=config.endpoint_url,
            api_key=config.api_key,
            api_version="2024-12-01-preview",
        )
    elif config.type == "openai_compatible":
        return AsyncOpenAI(
            base_url=config.endpoint_url,
            api_key=config.api_key,
        )
    else:
        raise ValueError(f"Unknown judge endpoint type: '{config.type}'")


class Judge:
    """LLM-as-a-judge evaluator with pairwise + absolute scoring."""

    def __init__(
        self,
        judge_config: EndpointConfig,
        pairwise_template: PromptTemplate,
        absolute_template: PromptTemplate,
        max_parallel: int = 3,
        timeout_seconds: int = 90,
        max_retries: int = 2,
    ):
        self._config = judge_config
        self._client = _build_judge_client(judge_config)
        self._pairwise_tpl = pairwise_template
        self._absolute_tpl = absolute_template
        self._semaphore = asyncio.Semaphore(max_parallel)
        self._timeout = timeout_seconds
        self._max_retries = max_retries

    async def evaluate(
        self,
        prompt_id: str,
        prompt_text: str,
        router_response: str,
        baseline_response: str,
    ) -> JudgeResult:
        """Run full judge evaluation: pairwise (dual-ordering) + absolute scoring.

        Args:
            prompt_id: Prompt identifier.
            prompt_text: The original user prompt.
            router_response: Response from model router.
            baseline_response: Response from baseline model.

        Returns:
            JudgeResult with pairwise verdict and absolute scores.
        """
        result = JudgeResult(
            prompt_id=prompt_id,
            judge_model=self._config.deployment_name,
        )

        start = time.perf_counter()

        try:
            # Run all 4 judge calls in parallel:
            # - Pairwise: router first, baseline first (dual-ordering)
            # - Absolute: router score, baseline score
            pw_rf, pw_bf, abs_r, abs_b = await asyncio.gather(
                self._pairwise_call(prompt_text, router_response, baseline_response),
                self._pairwise_call(prompt_text, baseline_response, router_response),
                self._absolute_call(prompt_text, router_response),
                self._absolute_call(prompt_text, baseline_response),
            )

            result.pairwise_router_first = _parse_pairwise_verdict(pw_rf)
            result.pairwise_baseline_first = _parse_pairwise_verdict(pw_bf)
            result.pairwise_winner = _resolve_dual_ordering(
                result.pairwise_router_first,
                result.pairwise_baseline_first,
            )

            result.router_score = _parse_absolute_scores(abs_r)
            result.baseline_score = _parse_absolute_scores(abs_b)

        except Exception as e:
            result.error = str(e)

        result.latency_ms = (time.perf_counter() - start) * 1000
        return result

    async def _pairwise_call(
        self,
        prompt_text: str,
        response_a: str,
        response_b: str,
    ) -> str:
        """Make a single pairwise comparison call."""
        user_msg = self._pairwise_tpl.user.format(
            prompt=prompt_text,
            response_a=response_a,
            response_b=response_b,
        )
        return await self._call_judge(self._pairwise_tpl.system, user_msg)

    async def _absolute_call(
        self,
        prompt_text: str,
        response: str,
    ) -> str:
        """Make a single absolute scoring call."""
        user_msg = self._absolute_tpl.user.format(
            prompt=prompt_text,
            response=response,
        )
        return await self._call_judge(self._absolute_tpl.system, user_msg)

    async def _call_judge(self, system_msg: str, user_msg: str) -> str:
        """Call the judge model with retry logic."""
        async with self._semaphore:
            last_error = None
            for attempt in range(self._max_retries):
                try:
                    create_kwargs: Dict[str, Any] = {
                        "model": self._config.deployment_name,
                        "messages": [
                            {"role": "system", "content": system_msg},
                            {"role": "user", "content": user_msg},
                        ],
                        "max_completion_tokens": 1024,
                    }
                    # Only pass temperature if the config explicitly sets it
                    params = self._config.parameters or {}
                    if "temperature" in params:
                        create_kwargs["temperature"] = params["temperature"]
                    response = await asyncio.wait_for(
                        self._client.chat.completions.create(**create_kwargs),
                        timeout=self._timeout,
                    )
                    choice = response.choices[0] if response.choices else None
                    return choice.message.content or "" if choice else ""

                except Exception as e:
                    last_error = e
                    if attempt < self._max_retries - 1:
                        await asyncio.sleep(2 ** attempt)

            raise last_error or RuntimeError("Judge call failed with no error details")

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.close()
