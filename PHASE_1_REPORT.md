# PHASE 1 Report — Exam Runtime Completion & Architecture Preparation

**Date:** 2026-06-17  
**Scope:** Complete exam attempt runtime; prepare backend for Phase 2 (Proctoring).  
**Proctoring:** Not implemented in this phase.

---

## Completed Work

### 1. AttemptAnswer relationship refactor (justified)

**Problem:** `attempt_answers.question_id` referenced the live `questions` table. Exam delivery uses `test_questions` snapshots where `question_id` is often `NULL` (AI/manual items). Students could not answer snapshot-only questions.

**Solution:** Replaced `question_id` with `test_question_id` (FK → `test_questions.id`). Replaced `selected_choice_id` (FK → `question_choices`) with `selected_choice_indices` (JSON array of zero-based indices into `snapshot_choices_json`).

This aligns answers with the immutable exam snapshot shown to students.

### 2. TestAttempt runtime fields

Added to `test_attempts`:

| Column | Purpose |
|--------|---------|
| `last_activity_at` | Resume / autosave tracking |
| `submission_source` | `STUDENT`, `TIMEOUT`, or `FORCE` |

### 3. AttemptService — full runtime

New `service/attempt_service.py` implements:

| Feature | Behavior |
|---------|----------|
| **Start attempt** | `POST /tests/{id}/attempts` — creates attempt, sets `expires_at` from `duration_minutes` |
| **Resume attempt** | Same endpoint returns 200 if `IN_PROGRESS` exists; `GET .../attempts/current` |
| **Autosave** | `PUT .../answers` (bulk upsert) |
| **Update answer** | `PATCH .../answers/{test_question_id}` |
| **Submit** | `POST .../submit` — auto-grades MCQ/TRUE_FALSE/MULTI_SELECT |
| **Force submit** | `POST .../force-submit` — teacher/admin/creator |
| **Timeout** | `POST .../timeout` + automatic on any read/write when `expires_at` passed |
| **Finalization** | Status → `SUBMITTED`; → `GRADED` when no manual (ESSAY) items remain |
| **One attempt rule** | Cannot start new attempt after `SUBMITTED`/`GRADED` |

### 4. REST APIs (10 new endpoints)

| Method | URL | Audience |
|--------|-----|----------|
| GET | `/tests/available` | Student / admin |
| POST | `/tests/{test_id}/attempts` | Student |
| GET | `/tests/{test_id}/attempts/current` | Student |
| GET | `/tests/{test_id}/attempts` | Teacher / admin |
| GET | `/tests/{test_id}/attempts/{attempt_id}` | Student (own) / teacher |
| PUT | `/tests/{test_id}/attempts/{attempt_id}/answers` | Student |
| PATCH | `/tests/{test_id}/attempts/{attempt_id}/answers/{test_question_id}` | Student |
| POST | `/tests/{test_id}/attempts/{attempt_id}/submit` | Student |
| POST | `/tests/{test_id}/attempts/{attempt_id}/force-submit` | Teacher / admin |
| POST | `/tests/{test_id}/attempts/{attempt_id}/timeout` | Student / system |

### 5. Authorization

Extended `utils/academic_rbac.py`:

- `can_take_published_test()` — student enrolled in subject (or admin)
- `can_manage_test_attempts()` — teacher, admin, or test creator

All endpoints use existing `require_workspace_membership` + `handle_service_errors`.

### 6. Swagger

All attempt endpoints documented in `swagger/template.yml` with definitions: `TestAttempt`, `TestAttemptRuntime`, `AttemptAnswer`, `SaveAnswerItem`, etc.

### 7. Enum

`AttemptSubmissionSource` added to `utils/enums.py`; exposed via `GET /api/enums`.

### 8. Logging

Runtime actions logged via `logging.getLogger(__name__)` in `AttemptService` (start, resume, autosave, submit, timeout).

### 9. Verification

- Migration `g3b4c5d6e7f8` applied successfully
- App imports cleanly (94 routes)
- `GET /health` → 200
- `GET /api/enums` includes `attempt_submission_source`
- All attempt routes registered under `/tests`

---

## Modified Files

| File | Change |
|------|--------|
| `models/attempt_answer.py` | `test_question_id`, `selected_choice_indices`, `TimestampMixin`; removed `question_id` / `selected_choice_id` |
| `models/test.py` | `last_activity_at`, `submission_source` on `TestAttempt` |
| `models/question.py` | `TestQuestion.attempt_answers`; removed `Question`/`QuestionChoice` attempt relations |
| `utils/enums.py` | `AttemptSubmissionSource` enum |
| `utils/academic_rbac.py` | `can_take_published_test`, `can_manage_test_attempts` |
| `repositories/attempt_repository.py` | **New** — attempt/answer/test-question queries |
| `service/attempt_service.py` | **New** — full runtime logic |
| `router/attempt_routes.py` | **New** — HTTP layer |
| `router/__init__.py` | Register `attempt_bp` under `/tests` |
| `schemas/attempt_schema.py` | Updated for `test_question_id`, bulk save schemas |
| `schemas/test_schema.py` | `TestAttemptSchema` extended |
| `schemas/__init__.py` | Updated exports |
| `router/health_routes.py` | Expose `attempt_submission_source` in `/api/enums` |
| `swagger/template.yml` | Attempt endpoint + definition documentation |
| `migrations/versions/g3b4c5d6e7f8_attempt_runtime_refactor.py` | **New** migration |

---

## Database Changes

### Modified table: `test_attempts`

- `last_activity_at` TIMESTAMPTZ NULL
- `submission_source` VARCHAR(30) NULL

### Modified table: `attempt_answers`

| Before | After |
|--------|-------|
| `question_id` FK → `questions` | **Removed** |
| `selected_choice_id` FK → `question_choices` | **Removed** |
| — | `test_question_id` FK → `test_questions` NOT NULL |
| — | `selected_choice_indices` TEXT NULL (JSON array) |
| — | `created_at`, `updated_at` TIMESTAMPTZ |

### Constraints

- Dropped: `unique_attempt_question`
- Added: `unique_attempt_test_question` on `(attempt_id, test_question_id)`

### Migration

- **Revision:** `g3b4c5d6e7f8`
- **Revises:** `f2a3b4c5d6e7`
- **Note:** Pre-existing `attempt_answers` rows deleted (table was unused before Phase 1)

### Relationships

```
TestAttempt 1──* AttemptAnswer *──1 TestQuestion
```

`AttemptAnswer` no longer references `Question` or `QuestionChoice`.

---

## Architectural Decisions

### 1. Separate `AttemptService` vs extending `TestService`

`TestService` already handles authoring (~689 lines). Runtime concerns (autosave, grading, timeout) live in dedicated `AttemptService` to keep single responsibility and avoid a monolithic service.

### 2. `test_question_id` instead of `question_id`

Required for snapshot-based exams. Documented in model docstring. This is the primary architectural fix for Phase 1.

### 3. Choice answers as indices

Snapshot choices are JSON; indices are stable for the student session and work for AI/manual questions without DB choice rows.

### 4. Timeout handling

Checked on every attempt read/write (`_check_and_apply_timeout`). Client may also call `POST .../timeout`. `submission_source=TIMEOUT`.

### 5. Auto-grading

Objective types (`MCQ`, `TRUE_FALSE`, `MULTI_SELECT`) graded on submit from snapshot `is_correct` flags. `ESSAY` left `is_correct=null` → attempt stays `SUBMITTED` until manual grading (future phase).

### 6. Student question view

`is_correct` stripped from choices in student-facing serialization.

### 7. One submission per student per test

`find_completed_for_student()` blocks duplicate attempts after submit.

### 8. Routes under existing `/tests` prefix

New `attempt_bp` registered at `/tests` alongside `test_bp` — nested URL structure without duplicating test authoring routes.

---

## Breaking Changes

| Change | Impact |
|--------|--------|
| `attempt_answers.question_id` removed | Any external integration referencing `question_id` on answers must use `test_question_id` |
| `attempt_answers.selected_choice_id` removed | Clients must send `selected_choice_indices` (integer array) |
| Pre-Phase-1 `attempt_answers` data deleted in migration | Safe — no runtime existed before |

**API consumers:** No previously published attempt APIs existed; this is net-new surface area.

---

## Remaining Work (Ready for Phase 2 — Proctoring)

### Ready now

- `TestAttempt` with `IN_PROGRESS` lifecycle, `expires_at`, `last_activity_at`
- Autosave answer pipeline (PUT/PATCH)
- Submit / force-submit / timeout finalization hooks
- Student session identity via `student_membership_id` + `user_id`
- `Test.settings_config` JSON column for future proctoring policy
- `ProctoringEventType` enum (unused, ready for events)
- Logging infrastructure in attempt service

### Not in Phase 1 (future)

- Manual essay grading API
- ~~Scheduled test auto-publish background job~~ → **Implemented** (see `jobs/scheduled_test_publisher.py`, `PROJECT_STATUS_REPORT.md` §4)
- ~~WebSocket / real-time event stream~~ → **Implemented in Phase 2** (`router/proctoring_ws.py`)
- ~~Proctoring session & event models~~ → **Implemented in Phase 2**
- Retake policy configuration
- Background job for server-side timeout sweep (currently lazy on request)

### Recommended Phase 2 integration points

1. **WebSocket module:** `router/proctoring_ws.py` + `service/proctoring_service.py`
2. **Hook into:** `start_or_resume_attempt`, `save_answers`, `submit_attempt`, `_finalize_attempt`
3. **Reuse:** `TestAttempt.id` as proctoring session foreign key
4. **Extend:** `Test.settings_config` for proctoring rules (tab switch limits, etc.)

---

## API Examples

### Start attempt

```http
POST /tests/5/attempts
Authorization: Bearer <token>
X-Workspace-Id: 1
```

```json
{
  "message": "Attempt started",
  "resumed": false,
  "attempt": {
    "id": 12,
    "test_id": 5,
    "status": "IN_PROGRESS",
    "expires_at": "2026-06-17T13:30:00+00:00",
    "questions": [
      {
        "test_question_id": 101,
        "snapshot_question_text": "What is 2+2?",
        "snapshot_type_code": "MCQ",
        "choices": [
          { "index": 0, "body": "3" },
          { "index": 1, "body": "4" }
        ]
      }
    ]
  }
}
```

### Autosave

```http
PUT /tests/5/attempts/12/answers
Content-Type: application/json

{
  "answers": [
    { "test_question_id": 101, "selected_choice_indices": [1] }
  ]
}
```

### Submit

```http
POST /tests/5/attempts/12/submit
```

```json
{
  "message": "Attempt submitted",
  "attempt": {
    "id": 12,
    "status": "GRADED",
    "submission_source": "STUDENT",
    "raw_score": 10.0,
    "final_score": 10.0
  }
}
```

---

*Phase 1 complete. Awaiting Phase 2 (Proctoring) specification.*
