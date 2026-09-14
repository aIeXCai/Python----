# AI Courses backend layout

The Django app is organized by business domain. Public API paths and database
models remain owned by the `ai_courses` app; the subpackages only separate
implementation responsibilities.

## Stable Django entry points

- `models.py`: model declarations used by migrations and other apps.
- `urls.py`: public route table. URL paths and route names stay stable.
- `views.py`: legacy programming-problem, submission, score, and runner-facing
  endpoints.
- `serializers.py`: serializers used by the legacy endpoints.
- `admin.py`, `apps.py`, `migrations/`, `management/`, and `fixtures/`: standard
  Django integration points.

## Domain packages

- `problems/`: programming-problem visibility, publication, management, and
  quiz eligibility rules.
- `question_bank/`: AI units and choice-question serializers, services, and
  teacher APIs.
- `quizzes/`: quiz authoring, attempts, programming execution, settlement,
  analytics, snapshots, serializers, and APIs.
- `tests/`: all automated tests for this Django app, grouped by behavior.

Keep new code in the narrowest matching domain package. Cross-domain imports
should point to the owning package instead of adding another top-level module.
