- name: micro_quiz
- description: Generate and grade a 2-3 item math micro-quiz to verify whether the student can solve independently after the explanation.
- emoji: ??
- requires: []

# Math Micro Quiz

Use this skill after explanation, hinting, or variant practice.

## Use the tools

- `generate_micro_quiz`: create a short mastery check tied to the current math problem or knowledge point.
- `grade_micro_quiz`: grade the student answers and optionally feed the result into mastery tracking.

## Guidance

- Keep the quiz short enough for 3-5 minutes.
- Prefer independent solving over another guided explanation.
- If the student still fails the micro-quiz, lower the difficulty or switch back to guided hints.
