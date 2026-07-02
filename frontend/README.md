# Monitoring Debug Module (DEV ONLY)

Standalone developer interface for validating the **edu_forms** proctoring/monitoring backend before integrating it into the exam flow.

> This module is **not** part of the production product. It is blocked in production builds (`import.meta.env.DEV`).

## Prerequisites

- Backend running: `python run.py` (default `http://127.0.0.1:5000`)
- A test with `settings_config.proctoring.enabled: true`
- An **IN_PROGRESS** attempt for the student token you use
- JWT from `POST /auth/login` and workspace ID (`X-Workspace-Id`)

## Quick start

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**

## Configuration

Use the **Developer Configuration** panel:

| Field | Example |
|-------|---------|
| API Base URL | Leave empty to use Vite proxy, or `http://127.0.0.1:5000` |
| WebSocket Base URL | `ws://127.0.0.1:5000` |
| Workspace ID | From login / workspace list |
| Test ID | e.g. `27` |
| Attempt ID | e.g. `6` |
| Access Token | JWT from login |

Click **Save Configuration** (stored in `localStorage`).

## Backend APIs consumed

| Method | Endpoint |
|--------|----------|
| GET | `/health` |
| POST | `/tests/{test_id}/attempts/{attempt_id}/proctoring/session` |
| GET | `/tests/{test_id}/attempts/{attempt_id}/proctoring/session` |
| POST | `/tests/{test_id}/attempts/{attempt_id}/proctoring/events` |
| GET | `/tests/{test_id}/attempts/{attempt_id}/proctoring/violations` |
| GET | `/tests/{test_id}/attempts/{attempt_id}/proctoring/audit-logs` |
| GET | `/tests/{test_id}/attempts/{attempt_id}` |

**WebSocket:** `ws://{host}/ws/proctoring/tests/{test_id}/attempts/{attempt_id}?token={JWT}&workspace_id={id}`

## Not implemented on backend (shown in UI)

- Dedicated **terminate session** REST endpoint (stop disconnects WS only)
- **Reset session** (clears local debug state only)
- **GET proctoring/events** list (logs use audit-logs + live events)

## Architecture

```
frontend/src/
  components/monitoring-debug/   # UI sections
  components/ui/                 # Shared cards, status dots
  context/                       # MonitoringDebugProvider
  hooks/                         # useCamera, useMicrophone
  services/                      # apiClient, proctoringApi, proctoringWebSocket
  pages/MonitoringDebugPage.tsx
```

No changes to Flask backend, auth flow, or existing app routes.
