"""Review scheduler skill tools."""


def register():
    from ...tools.math_learning import (
        cancel_review_reminder,
        list_review_reminders,
        schedule_review_reminder,
    )

    return {
        "schedule_review_reminder": schedule_review_reminder,
        "list_review_reminders": list_review_reminders,
        "cancel_review_reminder": cancel_review_reminder,
    }
