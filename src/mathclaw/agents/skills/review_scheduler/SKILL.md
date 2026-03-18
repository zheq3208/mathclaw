- name: review_scheduler
- description: Schedule, inspect, and cancel spaced-review reminders for math knowledge points using the live cron backend.
- emoji: ?
- requires: [cron]

# Math Review Scheduler

Use this skill after diagnosis, mastery update, or micro-quiz grading.

## Use the tools

- `schedule_review_reminder`: create a real scheduled reminder for a knowledge point.
- `list_review_reminders`: inspect existing review reminders.
- `cancel_review_reminder`: stop a reminder that is no longer needed.

## Guidance

- Prefer using the mastery score to choose review spacing.
- Target the actual student chat/session when possible.
- Keep reminder prompts focused: one concept, one common error, one tiny practice item.
