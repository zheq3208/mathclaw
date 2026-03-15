from pathlib import Path

from researchclaw.agents.tools import solve_verify_q3vl as mod


def test_candidate_exact_check_passes_simple_equation() -> None:
    candidate = {
        "solver_role": "solver_a",
        "final_answer": "x=2, x=3",
        "final_expression": "x=2, x=3",
    }
    result = mod._candidate_exact_check(
        problem_text="??? x^2 - 5x + 6 = 0",
        candidate=candidate,
        expected_answer="x=2, x=3",
        variable="x",
    )
    assert result["verification"]["status"] == "pass"
    assert result["solver_role"] == "solver_a"


def test_run_math_solve_verify_agent_writes_artifacts(monkeypatch, tmp_path: Path) -> None:
    outputs = iter(
        [
            {
                "problem_summary": "solve a quadratic",
                "givens": ["x^2-5x+6=0"],
                "target": "solve x",
                "question_type": "algebra",
                "candidate_methods": ["factorization", "substitution check"],
                "exact_check_targets": {"equation": "x^2 - 5x + 6 = 0", "expressions": [], "answer_format": "roots"},
                "risks": [],
                "preferred_variable": "x",
                "requires_visual_reasoning": False,
            },
            {
                "solver_role": "solver_a",
                "method": "factorization",
                "reasoning_outline": ["factor the polynomial"],
                "key_steps": ["(x-2)(x-3)=0"],
                "final_answer": "x=2, x=3",
                "final_expression": "x=2, x=3",
                "assumptions": [],
                "confidence": 0.93,
            },
            {
                "solver_role": "solver_b",
                "method": "substitution check",
                "reasoning_outline": ["test the roots"],
                "key_steps": ["2 and 3 both satisfy the equation"],
                "final_answer": "x=2, x=3",
                "final_expression": "x=2, x=3",
                "assumptions": [],
                "confidence": 0.89,
            },
            {
                "candidate_reviews": [
                    {"solver_role": "solver_a", "verdict": "pass", "strengths": ["matches exact solver"], "issues": [], "first_conflicting_step": ""},
                    {"solver_role": "solver_b", "verdict": "pass", "strengths": ["independent confirmation"], "issues": [], "first_conflicting_step": ""},
                ],
                "consensus_answer": "x=2, x=3",
                "consensus_expression": "x=2, x=3",
                "conflict_summary": [],
                "recommended_winner": "solver_a",
                "revision_needed": False,
            },
            {
                "status": "pass",
                "final_answer": "x=2, x=3",
                "final_expression": "x=2, x=3",
                "concise_solution_markdown": "???????? $(x-2)(x-3)=0$??? $x=2$ ? $x=3$?",
                "verification_summary": ["SymPy exact solve matched both roots."],
                "unresolved_risks": [],
                "recommended_follow_up": "",
            },
        ]
    )

    monkeypatch.setattr(mod, "_call_qwen_json", lambda **kwargs: next(outputs))
    monkeypatch.setattr(mod, "_new_run_dir", lambda problem_text: tmp_path / "run")
    monkeypatch.setattr(mod, "_load_solver_config", lambda: {"model_name": "qwen3-vl-plus", "planner_enable_thinking": True, "solver_enable_thinking": True, "critic_enable_thinking": True, "arbiter_enable_thinking": False})

    result = mod.run_math_solve_verify_agent("??? x^2 - 5x + 6 = 0", expected_answer="x=2, x=3")

    assert result["status"] == "pass"
    assert Path(result["Solved_md_path"]).exists()
    assert Path(result["VerificationReport_json_path"]).exists()
    assert Path(result["SolutionAudit_json_path"]).exists()


def test_build_math_solution_brief_uses_local_defaults(monkeypatch) -> None:
    payload = {
        "problem_summary": "summary",
        "givens": ["a triangle"],
        "target": "find angle A",
        "question_type": "geometry",
        "candidate_methods": ["angle sum"],
        "exact_check_targets": {"equation": "", "expressions": [], "answer_format": "degree"},
        "risks": ["diagram dependence"],
        "preferred_variable": "x",
        "requires_visual_reasoning": True,
    }
    monkeypatch.setattr(mod, "_call_qwen_json", lambda **kwargs: payload)
    monkeypatch.setattr(mod, "_load_solver_config", lambda: {"model_name": "qwen3-vl-plus", "planner_enable_thinking": True})

    result = mod.build_math_solution_brief("????ABC????A", supporting_images="")

    assert result["problem_summary"] == "summary"
    assert "local_brief" in result
    assert result["local_brief"]["target"]
