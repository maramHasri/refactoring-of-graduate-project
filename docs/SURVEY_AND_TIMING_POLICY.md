# Survey & Timing Policy (Phase 1)

## Availability modes

| Mode | Deadline | Duration | Offline grace (policy for Frontend) |
|------|----------|----------|-------------------------------------|
| `SCHEDULED` | `starts_at + duration_minutes` (global) | required at take time | 5 minutes (proctored or not) |
| `FLEXIBLE` + proctoring | `started_at + duration` | required | 5 minutes |
| `FLEXIBLE` without proctoring | `started_at + duration` | required | none |
| `SURVEY` | `closed_at` only | **must be null** | none (open until close) |

**Active-Time Duration is not part of QuizHub.** Elapsed time always continues while the browser is closed / offline for Flexible exams.

## Offline Grace (authoritative split)

- **Frontend:** detects offline, runs the 5-minute grace timer, freezes local answers when grace **or** real deadline hits (whichever is earlier), syncs on reconnect.
- **Backend:** stores `settings_config.offline_policy.grace_period_minutes` for the Frontend to read; **does not** run a competing grace counter. On every request it validates attempt/test state and **server deadlines**. Grace never extends a deadline.

Effective stop for the student UI:

```text
min(offline_grace_expiry, attempt/global deadline, closed_at, hard close)
```

## Hard close (`closed_at` / `CLOSED`)

When `now >= closed_at` or `status in {CLOSED, ARCHIVED}`:

- No new attempts
- No resume
- No autosave / answer updates
- All `IN_PROGRESS` attempts are finalized (`TIMEOUT`) via request path or background job
- `POST /tests/{id}/close` also finalizes in-progress attempts

## `POST /tests/{id}/attempts`

1. If an `IN_PROGRESS` attempt exists → apply timeout/hard-close finalize first  
2. If still `IN_PROGRESS` → resume  
3. Else → create a new attempt only if `max_attempts` allows  

## Creating a Survey

```json
{
  "name": "Course Feedback",
  "subject_id": 24,
  "availability_time_mode": "SURVEY",
  "closed_at": "2026-08-10T23:59:00",
  "total_score": 100,
  "passing_score": 0
}
```

- Do **not** send `duration_minutes` (must be null).
- Proctoring must stay disabled.
- Timezone for `closed_at` is the app timezone (`APP_TIMEZONE`, default `Asia/Damascus`).
