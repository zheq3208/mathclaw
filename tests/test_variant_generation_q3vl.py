from pathlib import Path

from mathclaw.agents.tools import variant_generation_q3vl as mod


def test_build_variant_generation_case_parses_count_and_focus() -> None:
    result = mod.build_variant_generation_case(
        problem_text='Solve x^2 - 5x + 6 = 0',
        variant_request='给我两道更难的变式题，针对因式分解',
    )

    assert result['requested_count'] == 2
    assert '因式分解' in result['target_skill']


def test_run_problem_variant_agent_writes_artifacts(monkeypatch, tmp_path: Path) -> None:
    draft = {
        'variant_set_title': 'Quadratic Variant Set',
        'variants': [
            {
                'variant_type': 'isomorphic',
                'problem_text': 'Solve x^2 - 7x + 12 = 0',
                'changes': ['Changed coefficients while preserving factorization.'],
                'intent': 'same_concept_same_solution_frame',
                'difficulty_goal': 'same',
                'coach_note': 'Practice the same factoring frame.',
                'answer_outline': ['Factor the quadratic.', 'Set each factor to zero.'],
            },
            {
                'variant_type': 'easier',
                'problem_text': 'Solve x^2 - 3x + 2 = 0',
                'changes': ['Used smaller integers.'],
                'intent': 'reduced_prerequisite_load',
                'difficulty_goal': 'easier',
                'coach_note': 'Use this to warm up the same method.',
                'answer_outline': ['Factor the quadratic.', 'Solve each linear factor.'],
            },
            {
                'variant_type': 'harder',
                'problem_text': 'Solve x^2 - 5x + 6 = 0 and justify the roots by substitution.',
                'changes': ['Added one justification step.'],
                'intent': 'deeper_transfer_or_extra_constraint',
                'difficulty_goal': 'harder',
                'coach_note': 'Add one verification step after solving.',
                'answer_outline': ['Factor the quadratic.', 'Find the roots.', 'Check both roots by substitution.'],
            },
        ],
        'design_notes': ['Keep the factoring knowledge point stable.'],
    }

    monkeypatch.setattr(mod, '_call_qwen_json', lambda **kwargs: draft)
    monkeypatch.setattr(mod, '_load_solver_config', lambda: {'model_name': 'qwen3-vl-plus', 'planner_enable_thinking': True})

    def fake_run_dir(seed_text: str) -> Path:
        run_dir = tmp_path / 'run'
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    monkeypatch.setattr(mod, '_new_run_dir', fake_run_dir)

    result = mod.run_problem_variant_agent(
        problem_text='Solve x^2 - 5x + 6 = 0',
        variant_request='Generate targeted follow-up practice variants.',
    )

    assert result['status'] == 'generated'
    assert result['variant_count'] == 3
    assert Path(result['VariantSet_md_path']).exists()
    assert Path(result['VariantBundle_json_path']).exists()
    assert Path(result['VariantAudit_json_path']).exists()


def test_generate_problem_variants_keeps_legacy_shape(monkeypatch) -> None:
    monkeypatch.setattr(
        mod,
        'verify_problem_variants',
        lambda **kwargs: {
            'case_brief': {'question_type': 'equation', 'target_skill': 'factoring'},
            'variants': [
                {
                    'variant_type': 'isomorphic',
                    'problem_text': 'Solve x^2 - 7x + 12 = 0',
                    'changes': ['Changed coefficients while preserving factorization.'],
                    'intent': 'same_concept_same_solution_frame',
                }
            ],
        },
    )

    result = mod.generate_problem_variants('Solve x^2 - 5x + 6 = 0', target_skill='factoring')

    assert result['question_type'] == 'equation'
    assert result['target_skill'] == 'factoring'
    assert result['variants'][0]['variant_type'] == 'isomorphic'


def test_build_variant_generation_case_prioritizes_memory_target(monkeypatch) -> None:
    monkeypatch.setattr(
        mod,
        'get_global_learning_memory',
        lambda student_id='': {
            'memory': {
                'knowledge_points': {
                    'linear equation': {
                        'risk_score': 0.82,
                        'history_count': 4,
                        'weakness_links': ['symbolic_manipulation_gap'],
                    }
                },
                'weaknesses': {},
            }
        },
    )

    result = mod.build_variant_generation_case(
        problem_text='Find the mean of 2, 4, 6',
        variant_request='给我一些后续变式题',
        student_id='stu-memory',
    )

    assert result['memory_context']['variant_source'] == 'global_memory'
    assert result['memory_context']['targeted_knowledge_point'] == 'linear equation'
    assert result['target_skill'] == 'linear equation'
    assert result['question_type'] == 'equation'


def test_generate_problem_variants_returns_memory_context(monkeypatch) -> None:
    monkeypatch.setattr(
        mod,
        'verify_problem_variants',
        lambda **kwargs: {
            'case_brief': {
                'question_type': 'equation',
                'target_skill': 'factoring',
                'memory_context': {
                    'variant_source': 'global_memory',
                    'targeted_knowledge_point': 'linear equation',
                    'targeted_weaknesses': ['symbolic_manipulation_gap'],
                },
            },
            'variants': [
                {
                    'variant_type': 'isomorphic',
                    'problem_text': 'Solve x^2 - 7x + 12 = 0',
                    'changes': ['Changed coefficients while preserving factorization.'],
                    'intent': 'same_concept_same_solution_frame',
                }
            ],
        },
    )

    result = mod.generate_problem_variants('Solve x^2 - 5x + 6 = 0', target_skill='factoring')

    assert result['memory_context']['variant_source'] == 'global_memory'
    assert result['memory_context']['targeted_knowledge_point'] == 'linear equation'
