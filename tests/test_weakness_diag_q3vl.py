from pathlib import Path

from researchclaw.agents.tools import weakness_diag_q3vl as mod


def test_run_math_weakness_diagnosis_agent_writes_artifacts(monkeypatch, tmp_path: Path) -> None:
    verification_path = tmp_path / "VerificationReport.json"
    verification_path.write_text(
        '{"arbiter": {"status": "conflict", "final_answer": "x=2"}, "critic": {"conflict_summary": ["student answer mismatched"]}, "tool_checks": {}}',
        encoding="utf-8",
    )

    combined_output = {
        "process": {
            "primary_error_stage": "final_answer",
            "wrong_answer": True,
            "process_incomplete": True,
            "missing_steps": ["The first derivation step is missing."],
            "evidence_items": ["Student final answer conflicts with the verified answer or exact check."],
            "likely_error_causes": ["symbolic_manipulation_gap"],
            "confidence": 0.88,
        },
        "learning": {
            "primary_weakness": "symbolic_manipulation_gap",
            "secondary_weaknesses": ["incomplete_reasoning"],
            "knowledge_points": ["linear equation"],
            "prerequisite_gaps": ["inverse operations"],
            "recommended_practice_focus": ["show the isolation step"],
            "teacher_watchouts": ["Check whether the student can isolate x without guessing."],
            "confidence": 0.81,
        },
        "arbiter": {
            "status": "diagnosed",
            "problem_summary": "solve a linear equation",
            "primary_weakness": "symbolic_manipulation_gap",
            "secondary_weaknesses": ["incomplete_reasoning"],
            "wrong_answer": True,
            "process_incomplete": True,
            "missing_steps": ["The first derivation step is missing."],
            "evidence_items": ["Student final answer conflicts with the verified answer or exact check."],
            "chapter": "Algebra",
            "question_type": "equation",
            "knowledge_points": ["linear equation"],
            "prerequisite_gaps": ["inverse operations"],
            "likely_error_causes": ["symbolic_manipulation_gap"],
            "recommended_practice_focus": ["show the isolation step"],
            "teacher_feedback_markdown": "# Weakness Diagnosis\n\n- Primary weakness: symbolic_manipulation_gap",
            "mastery_update_suggestion": {"result": "incorrect", "knowledge_points": ["linear equation"], "note": "symbolic_manipulation_gap"},
            "confidence": 0.88,
        },
    }

    monkeypatch.setattr(
        mod,
        "run_math_solve_verify_agent",
        lambda **kwargs: {
            "VerificationReport_json_path": str(verification_path),
            "final_answer": "x=2",
        },
    )
    monkeypatch.setattr(mod, "_call_qwen_json", lambda **kwargs: combined_output)

    def fake_run_dir(seed_text: str) -> Path:
        run_dir = tmp_path / "run"
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    monkeypatch.setattr(mod, "_new_run_dir", fake_run_dir)
    monkeypatch.setattr(
        mod,
        "_load_solver_config",
        lambda: {
            "model_name": "qwen3-vl-plus",
            "planner_enable_thinking": True,
            "critic_enable_thinking": True,
            "arbiter_enable_thinking": False,
        },
    )

    result = mod.run_math_weakness_diagnosis_agent(
        problem_text="?? 2x + 3 = 7",
        student_answer="x=5",
        student_work="???5",
    )

    assert result["status"] == "diagnosed"
    assert Path(result["TeacherFeedback_md_path"]).exists()
    assert Path(result["WeaknessReport_json_path"]).exists()
    assert Path(result["DiagnosisAudit_json_path"]).exists()


def test_build_math_weakness_case_skips_bootstrap_when_reference_exists_in_context(monkeypatch) -> None:
    called = False

    def fake_bootstrap(**kwargs):
        nonlocal called
        called = True
        raise AssertionError("bootstrap should not run when answer is already in context")

    monkeypatch.setattr(mod, "run_math_solve_verify_agent", fake_bootstrap)

    result = mod.build_math_weakness_case(
        problem_text="??? x^2 - 5x + 6 = 0",
        student_answer="x=4",
        conversation_excerpt="assistant: Answer: x=2, x=3",
    )

    assert called is False
    assert result["reference_answer"] == "x=2, x=3"
    assert result["bootstrap_result"] == {}


def test_diagnose_math_weakness_keeps_legacy_shape(monkeypatch, tmp_path: Path) -> None:
    report_path = tmp_path / "WeaknessReport.json"
    report_path.write_text(
        '{"case_brief": {"difficulty_band": "medium"}, "arbiter": {"chapter": "Algebra", "question_type": "equation", "knowledge_points": ["linear equation"], "prerequisite_gaps": ["inverse operations"], "likely_error_causes": ["symbolic_manipulation_gap"], "primary_weakness": "symbolic_manipulation_gap", "secondary_weaknesses": ["incomplete_reasoning"], "wrong_answer": true, "process_incomplete": true, "missing_steps": ["The first derivation step is missing."], "evidence_items": ["Student final answer conflicts with the verified answer or exact check."], "recommended_practice_focus": ["show the isolation step"], "status": "diagnosed"}}',
        encoding="utf-8",
    )
    feedback_path = tmp_path / "TeacherFeedback.md"
    feedback_path.write_text("# Weakness Diagnosis", encoding="utf-8")

    monkeypatch.setattr(
        mod,
        "run_math_weakness_diagnosis_agent",
        lambda **kwargs: {
            "TeacherFeedback_md_path": str(feedback_path),
            "WeaknessReport_json_path": str(report_path),
            "DiagnosisAudit_json_path": str(tmp_path / "DiagnosisAudit.json"),
            "status": "diagnosed",
        },
    )

    result = mod.diagnose_math_weakness("?? 2x + 3 = 7", student_answer="x=5")

    assert result["knowledge_point"] == "linear equation"
    assert result["primary_weakness"] == "symbolic_manipulation_gap"
    assert result["status"] == "diagnosed"
