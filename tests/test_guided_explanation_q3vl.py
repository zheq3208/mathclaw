from pathlib import Path

from mathclaw.agents.tools import guided_explanation_q3vl as mod


def test_run_guided_explanation_agent_writes_artifacts(monkeypatch, tmp_path: Path) -> None:
    outputs = iter(
        [
            {
                "hint_level": 1,
                "teaching_mode": "notice",
                "teacher_focus": "??????????????????",
                "immediate_goal": "?????????",
                "diagnostic_focus": ["first_missing_step"],
                "misconceptions_to_probe": ["symbolic_manipulation_gap"],
                "must_avoid": ["Do not dump the final answer before the student engages."],
                "allowed_reveal": "????????????????",
                "first_question": "????????????",
                "checkpoint_rubric": ["Can the student restate the target?"],
                "escalation_rule": "If the student remains stuck after two attempts, raise the hint level by one.",
                "allow_full_solution": False,
                "confidence": 0.86,
            },
            {
                "hint_level": 1,
                "teacher_response_markdown": "??????????\n\n?????????????",
                "student_checkpoint_question": "????????????",
                "expected_student_action": "restate_goal",
                "if_student_stuck_then": "Raise the hint level by one.",
                "revealed_step": "",
                "progress_signal": "Student can restate the goal.",
                "stop_condition": "Stop when the student can restate the goal.",
                "confidence": 0.84,
            },
        ]
    )

    monkeypatch.setattr(mod, "_call_qwen_json", lambda **kwargs: next(outputs))
    monkeypatch.setattr(
        mod,
        "_load_solver_config",
        lambda: {
            "model_name": "qwen3-vl-plus",
            "planner_enable_thinking": True,
            "solver_enable_thinking": True,
        },
    )

    def fake_run_dir(seed_text: str) -> Path:
        run_dir = tmp_path / "run"
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    monkeypatch.setattr(mod, "_new_run_dir", fake_run_dir)

    result = mod.run_guided_explanation_agent(
        problem_text="??? 2x + 3 = 7",
        learning_goal="??????????????",
    )

    assert result["status"] == "guided"
    assert result["hint_level"] == 1
    assert Path(result["TeacherReply_md_path"]).exists()
    assert Path(result["TeachingCase_json_path"]).exists()
    assert Path(result["TeachingPlan_json_path"]).exists()
    assert Path(result["TutorTurn_json_path"]).exists()
    assert Path(result["TeachingAudit_json_path"]).exists()


def test_compose_guided_explanation_turn_patches_answer_leak(monkeypatch) -> None:
    verification_payload = {"arbiter": {"final_answer": "x=2"}}
    outputs = iter(
        [
            {
                "hint_level": 1,
                "teaching_mode": "notice",
                "teacher_focus": "??????????",
                "immediate_goal": "?????????",
                "diagnostic_focus": ["first_missing_step"],
                "misconceptions_to_probe": [],
                "must_avoid": ["Do not dump the final answer before the student engages."],
                "allowed_reveal": "????????????????",
                "first_question": "??????????",
                "checkpoint_rubric": ["Can the student restate the target?"],
                "escalation_rule": "Raise the hint level after two failed attempts.",
                "allow_full_solution": False,
                "confidence": 0.81,
            },
            {
                "hint_level": 1,
                "teacher_response_markdown": "??? x=2????????????",
                "student_checkpoint_question": "??????",
                "expected_student_action": "acknowledge",
                "if_student_stuck_then": "Raise the hint level by one.",
                "revealed_step": "",
                "progress_signal": "Student can say the answer.",
                "stop_condition": "Stop when the student accepts the answer.",
                "confidence": 0.6,
            },
        ]
    )
    monkeypatch.setattr(mod, "_call_qwen_json", lambda **kwargs: next(outputs))
    monkeypatch.setattr(
        mod,
        "_load_solver_config",
        lambda: {
            "model_name": "qwen3-vl-plus",
            "planner_enable_thinking": True,
            "solver_enable_thinking": True,
        },
    )

    result = mod.compose_guided_explanation_turn(
        problem_text="??? 2x + 3 = 7",
        learning_goal="????????????",
        verification_report=verification_payload,
    )

    tutor_turn = result["tutor_turn"]
    assert tutor_turn["patched_for_answer_leak"] is True
    assert "??? x=2" not in tutor_turn["teacher_response_markdown"]
    assert "?????????" in tutor_turn["teacher_response_markdown"]


def test_choose_hint_level_keeps_legacy_shape() -> None:
    result = mod.choose_hint_level(current_level=2, attempts=3, requested_full_solution=False, student_progress="", student_reply="I am still stuck here")

    assert result == {
        "current_level": 2,
        "next_level": 3,
        "reason": "multiple_attempts_without_progress",
    }
