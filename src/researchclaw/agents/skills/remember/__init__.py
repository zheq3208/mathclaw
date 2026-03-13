"""Remember skill tools."""


def register():
    from ...tools.math_learning import list_student_facts, remember_student_fact

    return {
        "remember_student_fact": remember_student_fact,
        "list_student_facts": list_student_facts,
    }
