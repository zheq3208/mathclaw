from mathclaw.agents.skills.mastery_updater import register as mastery_register
from mathclaw.agents.skills.micro_quiz import register as micro_quiz_register
from mathclaw.agents.skills.review_scheduler import register as review_scheduler_register
from mathclaw.agents.skills.problem_json_normalizer import (
    register as normalizer_register,
)
from mathclaw.agents.tools import math_learning
from mathclaw.agents.tools.math_input import normalize_problem_json
from mathclaw.agents.tools.math_learning import (
    cancel_review_reminder,
    choose_hint_level,
    diagnose_math_weakness,
    generate_micro_quiz,
    get_math_mastery_snapshot,
    grade_micro_quiz,
    list_review_reminders,
    map_problem_to_curriculum,
    schedule_review_reminder,
    update_math_mastery,
)
from mathclaw.agents.tools.math_reasoning import (
    sympy_check_equivalence,
    sympy_simplify_expression,
    sympy_solve_equation,
    verify_math_solution,
)


def test_normalize_problem_json_extracts_core_fields() -> None:
    result = normalize_problem_json("已知 2x + 3 = 7，求 x 的值。")
    assert result["question_type"] in {"equation", "algebra"}
    assert result["target"]
    assert any(
        "2x + 3 = 7" in item or "2x+3=7" in item
        for item in result["formula_expressions"]
    )


def test_sympy_tools_and_verifier() -> None:
    simplified = sympy_simplify_expression("(x+1)^2 - (x^2 + 2*x + 1)")
    assert simplified["simplified"] == "0"

    solved = sympy_solve_equation("2*x + 3 = 7")
    assert solved["solutions"] == ["2"]

    equivalent = sympy_check_equivalence("2*(x+1)", "2*x + 2")
    assert equivalent["equivalent"] is True

    passed = verify_math_solution("解方程 2x + 3 = 7", "x=2")
    assert passed["status"] == "pass"

    failed = verify_math_solution("解方程 2x + 3 = 7", "x=3")
    assert failed["status"] == "conflict"


def test_curriculum_and_diagnosis() -> None:
    curriculum = map_problem_to_curriculum(
        "已知一次函数 y = 2x + 1，求当 x = 3 时的 y 值。"
    )
    assert curriculum["chapter"] in {
        "function",
        "equations_and_inequalities",
        "algebra",
    }
    assert curriculum["knowledge_points"]

    diagnosis = diagnose_math_weakness(
        "解方程 2x + 3 = 7",
        student_answer="x=3",
        correct_answer="x=2",
        error_description="移项时符号看错了",
    )
    assert diagnosis["likely_error_causes"]


def test_update_math_mastery_persists(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(math_learning, "MEMORY_DIR", str(tmp_path))
    event = update_math_mastery(
        student_id="stu-1",
        knowledge_point="linear_equation",
        result="correct",
        evidence=["solved"],
        note="first pass",
    )
    assert event["after_score"] > event["before_score"]

    snapshot = get_math_mastery_snapshot("stu-1", "linear_equation")
    assert snapshot["record"]["score"] == event["after_score"]


def test_hint_policy_and_skill_registers() -> None:
    hint = choose_hint_level(current_level=1, attempts=3)
    assert hint["next_level"] == 2

    assert "normalize_problem_json" in normalizer_register()
    assert "update_math_mastery" in mastery_register()


def test_micro_quiz_generation_and_grading(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(math_learning, "MEMORY_DIR", str(tmp_path))

    quiz = generate_micro_quiz(
        "?? 2x + 3 = 7?? x ???",
        student_id="stu-1",
    )
    assert len(quiz["items"]) == 3
    assert quiz["quiz_id"].startswith("mq-")

    answers = [entry["answer"] for entry in quiz["answer_key"]]
    graded = grade_micro_quiz(
        quiz_id=quiz["quiz_id"],
        student_answers=answers,
        student_id="stu-1",
        update_mastery_record=True,
    )
    assert graded["ok"] is True
    assert graded["result"] == "quiz_pass"
    assert graded["mastery_event"] is not None


def test_review_scheduler_wrappers(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(math_learning, "MEMORY_DIR", str(tmp_path))

    def fake_create_job(**kwargs):
        return {
            "ok": True,
            "data": {
                "id": "job-1",
                "name": kwargs["name"],
                "enabled": True,
                "schedule": {"cron": kwargs["cron"], "timezone": kwargs["timezone"]},
            },
        }

    def fake_list_jobs(base_url: str = ""):
        return {
            "ok": True,
            "count": 1,
            "jobs": [
                {
                    "id": "job-1",
                    "name": "math-review::stu-1::linear_equation",
                    "enabled": True,
                    "schedule": {"cron": "0 20 * * *", "timezone": "Asia/Shanghai"},
                }
            ],
        }

    def fake_delete_job(job_id: str, base_url: str = ""):
        return {"ok": True, "data": {"deleted": True}, "job_id": job_id}

    monkeypatch.setattr(math_learning, "cron_create_job", fake_create_job)
    monkeypatch.setattr(math_learning, "cron_list_jobs", fake_list_jobs)
    monkeypatch.setattr(math_learning, "cron_delete_job", fake_delete_job)

    scheduled = schedule_review_reminder(
        student_id="stu-1",
        knowledge_point="linear_equation",
        target_user_id="stu-1",
        target_session_id="stu-1",
        channel="wecom",
    )
    assert scheduled["ok"] is True
    assert scheduled["job_id"] == "job-1"

    listed = list_review_reminders(student_id="stu-1")
    assert listed["count"] == 1
    assert listed["reminders"][0]["job_id"] == "job-1"

    cancelled = cancel_review_reminder("job-1")
    assert cancelled["ok"] is True


def test_new_skill_registers() -> None:
    assert "generate_micro_quiz" in micro_quiz_register()
    assert "schedule_review_reminder" in review_scheduler_register()
