# Teacher Dashboard — Behavior Report

**Endpoint:** `GET /workspaces/teacher-dashboard`  
**Date:** 2026-07-24  
**Status:** Implemented and verified with focused unit tests

---

## 1. What was implemented

| Layer | File |
|-------|------|
| Repository | `repositories/teacher_dashboard_repository.py` |
| Service | `service/teacher_dashboard_service.py` |
| Route | `router/workspace_routes.py` → `/teacher-dashboard` |
| Swagger | `swagger/template.yml` (Workspaces tag) |
| Message | `Messages.TEACHER_OR_WORKSPACE_ADMIN_ACCESS_REQUIRED` |
| Tests | `tests/test_teacher_dashboard.py` |

**Not reused (by design):** `WorkspaceDashboardService.get_dashboard()` and public `StudentAnalyticsService` entrypoints.  
**Reused:** `list_teacher_subject_ids`, attempt topic-weighted queries, `_classify` / `_attempt_is_passed`, `can_manage_subjects`, upcoming-test filter patterns, query schema limits.

---

## 2. Canonical metric definitions (as shipped)

| Metric | Definition |
|--------|------------|
| **total_students** | `COUNT(DISTINCT membership_id)` of active STUDENT enrollments across teacher subjects |
| **average_performance** | Mean of GRADED attempt `percentage` values (attempt-weighted), e.g. (80+90+60)/3 = **76.67** |
| **students_enrolled** | Per-subject active STUDENT `SubjectMembership` (`ACTIVE`, `deleted_at IS NULL`) |
| **graded_tests_count** | Distinct PUBLISHED, non-archived tests with ≥1 GRADED attempt |
| **success_rate** | Passed graded / total graded × 100; pass = `final_score >= passing_score` |
| **weak_topics** | Cohort difficulty-weighted mastery classified as `NEEDS_IMPROVEMENT` or `WEAKNESS` (same thresholds as student analytics: &lt;70). Includes `mastery_percentage`, `attempts_count`, `students_affected` |
| **upcoming_tests** | SCHEDULED/PUBLISHED in teacher `subject_ids` only |
| **recent_tests** | Created by current membership (`created_by_membership_id`), newest first |

### Graded / test filters (consistent with existing analytics)

- Attempt status: `GRADED` with non-null `percentage`
- Test status: `PUBLISHED` (for graded analytics)
- Archived tests excluded (`archived_at IS NULL`)
- Subject link: `Test.subject_id`

### Authorization

- Assigned **TEACHER** → subjects from active TEACHER `SubjectMembership`
- Owner/ADMIN (`can_manage_subjects`) → all active workspace subjects
- **STUDENT** → 403
- Workspace kinds: INSTITUTION or SOLO

---

## 3. Example response shape

```json
{
  "success": true,
  "summary": {
    "average_performance": 76.67,
    "total_students": 2,
    "weak_topics": [
      {
        "topic_id": 41,
        "topic_name": "Recursion",
        "mastery_percentage": 42.0,
        "attempts_count": 3,
        "students_affected": 2,
        "subject_id": 1,
        "subject_name": "Programming"
      }
    ]
  },
  "subjects": [
    {
      "subject_id": 1,
      "subject_name": "Programming",
      "students_enrolled": 2,
      "graded_tests_count": 1,
      "average_performance": 76.67,
      "success_rate": 100.0,
      "weak_topics": [...]
    }
  ],
  "upcoming_tests": [...],
  "recent_tests": [...]
}
```

---

## 4. Test results

Command:

```bash
python tests/test_teacher_dashboard.py
python tests/test_workspace_dashboard.py
```

| Suite | Result |
|-------|--------|
| `tests/test_teacher_dashboard.py` | **all teacher dashboard checks passed** |
| `tests/test_workspace_dashboard.py` | **all workspace dashboard checks passed** (no regression) |

### Covered behaviors

| Check | Result |
|-------|--------|
| Attempt-weighted average performance `(80+90+60)/3 → 76.67` | PASS |
| Empty average → `0.0` | PASS |
| Success rate with `passing_score` | PASS |
| No `passing_score` → treated as passed (existing rule) | PASS |
| Teacher scope = assigned subject ids only | PASS |
| Admin/owner scope = all workspace subjects | PASS |
| Student → ForbiddenError | PASS |
| Teacher role allowed | PASS |
| Other subject data does not appear in cards | PASS |
| DISTINCT student count contract | PASS |
| `graded_tests_count` = distinct tests, not attempts | PASS |
| Upcoming tests scoped to teacher subjects | PASS |
| Recent tests use creator membership id | PASS |
| Upcoming serialize date/time parts | PASS |

---

## 5. How to call

```http
GET /workspaces/teacher-dashboard?recent_limit=5&upcoming_limit=10
Authorization: Bearer <token>
X-Workspace-Id: <workspace_id>
```

Swagger: **Workspaces → Teacher-scoped workspace dashboard**.
