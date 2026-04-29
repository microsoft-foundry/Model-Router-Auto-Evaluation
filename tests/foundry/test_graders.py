"""Tests for src/foundry/graders.py."""

from __future__ import annotations

from src.foundry.graders import build_custom_evaluator_criteria, build_quality_criteria


class TestBuildQualityCriteria:
    def test_produces_three_criteria(self):
        criteria = build_quality_criteria(
            model_deployment="gpt-5",
            absolute_template_path="configs/grader_prompts/quality_absolute.yaml",
            pairwise_template_path="configs/grader_prompts/quality_pairwise.yaml",
        )
        assert len(criteria) == 3

    def test_criteria_names(self):
        criteria = build_quality_criteria(
            model_deployment="gpt-5",
            absolute_template_path="configs/grader_prompts/quality_absolute.yaml",
            pairwise_template_path="configs/grader_prompts/quality_pairwise.yaml",
        )
        names = [c["name"] for c in criteria]
        assert "quality_absolute_router" in names
        assert "quality_absolute_baseline" in names
        assert "quality_pairwise" in names

    def test_criteria_types(self):
        criteria = build_quality_criteria(
            model_deployment="gpt-5",
            absolute_template_path="configs/grader_prompts/quality_absolute.yaml",
            pairwise_template_path="configs/grader_prompts/quality_pairwise.yaml",
        )
        for c in criteria:
            assert c["type"] == "score_model"
            assert c["model"] == "gpt-5"
            assert c["range"] == [1, 5]
            assert c["pass_threshold"] == 3

    def test_router_criteria_uses_router_response(self):
        criteria = build_quality_criteria(
            model_deployment="gpt-5",
            absolute_template_path="configs/grader_prompts/quality_absolute.yaml",
            pairwise_template_path="configs/grader_prompts/quality_pairwise.yaml",
        )
        router_criterion = [c for c in criteria if c["name"] == "quality_absolute_router"][0]
        user_content = router_criterion["input"][-1]["content"]
        assert "{{item.router_response}}" in user_content

    def test_baseline_criteria_uses_baseline_response(self):
        criteria = build_quality_criteria(
            model_deployment="gpt-5",
            absolute_template_path="configs/grader_prompts/quality_absolute.yaml",
            pairwise_template_path="configs/grader_prompts/quality_pairwise.yaml",
        )
        baseline_criterion = [c for c in criteria if c["name"] == "quality_absolute_baseline"][0]
        user_content = baseline_criterion["input"][-1]["content"]
        assert "{{item.baseline_response}}" in user_content

    def test_custom_range_and_threshold(self):
        criteria = build_quality_criteria(
            model_deployment="gpt-5",
            absolute_template_path="configs/grader_prompts/quality_absolute.yaml",
            pairwise_template_path="configs/grader_prompts/quality_pairwise.yaml",
            pass_threshold=4,
            score_range=[1, 10],
        )
        for c in criteria:
            assert c["range"] == [1, 10]
            assert c["pass_threshold"] == 4


class TestBuildCustomEvaluatorCriteria:
    def test_python_grader_type(self):
        code = "def grade(sample, item) -> float:\n    return 0.5\n"
        criterion = build_custom_evaluator_criteria("mr_cost_comparison", code, 0.5)
        assert criterion["type"] == "python"
        assert criterion["name"] == "mr_cost_comparison"
        assert criterion["source"] == code
        assert criterion["pass_threshold"] == 0.5
