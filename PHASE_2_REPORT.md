# PHASE 2 Report — Proctoring System Implementation

**Date:** 2026-06-17  
**Prerequisite:** Phase 1 exam runtime (`PHASE_1_REPORT.md`)  
**Scope:** Real-time proctoring domain, violation engine, evidence packages, WebSocket channel, REST APIs

---

## Completed Work

### Domain model (5 tables)

| Model | Purpose |
|-------|---------|
| `ProctoringSession` | One monitoring lifecycle per `TestAttempt` (1:1) |
| `ProctoringEvent` | Low-level event log (WebSocket + REST ingestion) |
| `ProctoringViolation` | Detected suspicious behaviour with severity |
| `ProctoringEvidencePackage` | Forensic bundle for MEDIUM/HIGH violations |
| `ProctoringAuditLog` | Immutable audit trail of proctoring actions |

### Violation engine (`service/proctoring_violation_engine.py`)

Rule-based scoring with escalating severity:

| Event | Rule |
|-------|------|
| `MULTIPLE_FACES` | HIGH (+30) |
| `FACE_LOST` / `NO_FACE` | LOW; MEDIUM if lost ≥ 10s |
| `TAB_SWITCH` / `WINDOW_BLUR` | LOW → MEDIUM (≥2) → HIGH (≥5) |
| `AUDIO_ANOMALY` | MEDIUM |
| `SCREEN_INACTIVITY` | LOW |
| `SUSPICIOUS_NAVIGATION` | MEDIUM |
| `FULLSCREEN_EXIT` | MEDIUM |
| `COPY_PASTE` | HIGH |

MEDIUM/HIGH violations auto-generate evidence packages with event timelines ±30s/15s.

### Evidence & storage

- `ProctoringStorageService` with `ProctoringStorageBackend` abstraction
- Default: `LocalProctoringStorageBackend` → `uploads/proctoring/{workspace_id}/{session_id}/`
- Configurable via `PROCTORING_STORAGE_DIR` env var
- Screenshots (base64) and optional video clips supported in event payload

### WebSocket channel (mandatory)

**Endpoint:** `ws://host/ws/proctoring/tests/{test_id}/attempts/{attempt_id}?token=<JWT>&workspace_id=<id>`

**Client → server message types:** `student_joined`, `tab_switch`, `face_detected`, `face_lost`, `camera_status`, `microphone_activity`, `screen_inactivity`, `audio_anomaly`, `multiple_faces`, etc.

**Server → client:** `session_started`, `event_recorded`, `violation_triggered`, `error`

Auth reuses JWT + `SessionService.validate_access_jti` (same as REST).

### REST APIs (9 endpoints)

| Method | URL | Role |
|--------|-----|------|
| GET | `/tests/{test_id}/proctoring/sessions` | Proctor / admin |
| POST | `/tests/{test_id}/attempts/{attempt_id}/proctoring/session` | Student |
| GET | `/tests/{test_id}/attempts/{attempt_id}/proctoring/session` | Student / proctor |
| POST | `/tests/{test_id}/attempts/{attempt_id}/proctoring/events` | Student (REST fallback) |
| GET | `/tests/{test_id}/attempts/{attempt_id}/proctoring/violations` | Student (limited) / proctor |
| GET | `.../violations/{violation_id}` | Student / proctor |
| GET | `.../violations/{violation_id}/evidence` | Student / proctor |
| POST | `.../violations/{violation_id}/review` | Proctor / admin |
| GET | `.../proctoring/audit-logs` | Proctor / admin |

### Exam runtime integration

- **Attempt start:** auto-creates proctoring session when `test.settings_config.proctoring.enabled` is `true`
- **Attempt finalize:** terminates proctoring session (`COMPLETED`)
- Hooks in `AttemptService._maybe_start_proctoring` / `_maybe_terminate_proctoring`

### Enable proctoring on a test

Set via `PATCH /tests/{id}` → `settings_config`:

```json
{
  "proctoring": {
    "enabled": true
  }
}
```

---

## Modified Files

| File | Change |
|------|--------|
| `utils/enums.py` | Proctoring enums extended |
| `models/proctoring.py` | **New** — 5 models |
| `models/test.py` | `TestAttempt.proctoring_session` relationship |
| `models/__init__.py` | Export proctoring models |
| `service/attempt_service.py` | Auto start/terminate proctoring |
| `service/proctoring_service.py` | **New** — orchestration |
| `service/proctoring_violation_engine.py` | **New** — rules |
| `service/proctoring_storage.py` | **New** — storage abstraction |
| `repositories/proctoring_repository.py` | **New** |
| `schemas/proctoring_schema.py` | **New** |
| `router/proctoring_routes.py` | **New** REST |
| `router/proctoring_ws.py` | **New** WebSocket |
| `router/__init__.py` | Register proctoring blueprint |
| `router/health_routes.py` | Proctoring enums in `/api/enums` |
| `app_factory.py` | Register WebSocket |
| `config/settings.py` | `PROCTORING_STORAGE_DIR` |
| `requirements.txt` | `flask-sock`, `simple-websocket` |
| `swagger/template.yml` | Proctoring tag + endpoints |

---

## Database Changes

**Migration:** `h4c5d6e7f8a9_proctoring_domain.py` (revises `g3b4c5d6e7f8`)

### New tables

- `proctoring_sessions` — unique `test_attempt_id`
- `proctoring_events`
- `proctoring_violations`
- `proctoring_evidence_packages` — unique `violation_id`
- `proctoring_audit_logs`

### Relationships

```
TestAttempt 1──1 ProctoringSession 1──* ProctoringEvent
                              1──* ProctoringViolation 1──1 ProctoringEvidencePackage
                              1──* ProctoringAuditLog
```

---

## Architectural Decisions

1. **Separate `ProctoringService`** — extends (not duplicates) exam runtime; integrates via thin hooks in `AttemptService`.
2. **1:1 session per attempt** — simplifies proctoring lifecycle and Phase 2+ monitoring UI.
3. **Dual ingestion** — WebSocket for real-time; REST `/proctoring/events` as fallback.
4. **Evidence only for MEDIUM/HIGH** — reduces storage for minor events.
5. **Storage abstraction** — no hardcoded S3; swap backend via config.
6. **RBAC reuse** — `can_manage_test_attempts` for proctor; `verify_subject_student_access` for students.
7. **flask-sock** — lightweight WebSocket for Flask 3 without full Socket.IO stack.

---

## Breaking Changes

**None** to existing APIs. Proctoring is additive.

**New requirement:** Tests must set `settings_config.proctoring.enabled: true` for monitoring to activate.

---

## Testing

Verified:

- App imports (104 routes)
- Migration `h4c5d6e7f8a9` applied
- `GET /health` → 200
- `GET /api/enums` includes proctoring enums
- `flask-sock` installed

**Manual Swagger flow:**

1. Publish test with `settings_config.proctoring.enabled: true`
2. Student: `POST /tests/{id}/attempts`
3. Student: `POST .../proctoring/session` (or auto-started)
4. Student: `POST .../proctoring/events` with `{ "event_type": "TAB_SWITCH" }`
5. Proctor: `GET .../proctoring/violations`
6. Proctor: `POST .../violations/{id}/review`

**WebSocket:** Connect with JWT + workspace_id query params; send `{ "type": "tab_switch", "payload": {} }`.

---

## Remaining / Future Enhancements

- Live proctor dashboard WebSocket (broadcast to teachers)
- Server-side scheduled timeout sweep (currently lazy on request)
- S3/cloud storage backend implementation
- Configurable rule thresholds via `settings_config.proctoring.rules`
- Manual essay grading API (Phase 1 gap)
- Automated integration test suite

---

*Phase 2 complete. System ready for frontend proctoring UI integration.*
