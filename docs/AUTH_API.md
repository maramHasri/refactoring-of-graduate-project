# Authentication & Workspace API

## Super admin (pinned in DB)

1. Add to `.env`:

```
SUPER_ADMIN_EMAIL=superadmin@eduforms.local
SUPER_ADMIN_PASSWORD=SuperAdmin@123
SUPER_ADMIN_FULL_NAME=Platform Super Admin
```

2. Run seeds:

```bash
flask db upgrade
flask seed
```

3. Login:

```http
POST /auth/superadmin/login
Content-Type: application/json

{
  "email": "superadmin@eduforms.local",
  "password": "SuperAdmin@123"
}
```

Response includes `access_token`, `refresh_token`, `user.is_superadmin: true`, empty `memberships`.

## Standard login

```http
POST /auth/login
```

Returns `requires_onboarding: true` when user has zero memberships.

## Auth endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register` | Owner registration (user + workspace + ADMIN membership) |
| POST | `/join-codes/register-student` | New student + join code (see Join codes in Swagger) |
| POST | `/auth/login` | Login |
| POST | `/auth/superadmin/login` | Super admin login only |
| POST | `/auth/logout` | Revoke current session (Bearer) |
| POST | `/auth/logout-all` | Revoke all sessions (Bearer) |
| POST | `/auth/refresh` | Refresh tokens |
| POST | `/auth/verify-email` | Verify email |
| POST | `/auth/resend-verification` | Resend verification |
| POST | `/auth/forgot-password` | Start reset |
| POST | `/auth/reset-password` | Complete reset |
| POST | `/auth/change-password` | Change password (Bearer) |

## Workspace endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/workspaces` | List accessible workspaces (Bearer) |
| POST | `/workspaces` | Create workspace (Bearer) |
| GET | `/workspaces/{id}` | Workspace detail |
| PATCH | `/workspaces/{id}` | Update (admin) |
| DELETE | `/workspaces/{id}` | Delete (owner only) |

Workspace context: send `X-Workspace-Id` header (not in JWT).

## Join codes (students only)

```http
POST /join-codes/join
Authorization: Bearer <token>

{ "join_code": "ABCD1234" }
```

## Invitations

| Method | Path | Read/Write |
|--------|------|------------|
| POST | `/invites` | Write (requires X-Workspace-Id) |
| GET | `/invites/{token}` | Read only |
| POST | `/invites/{token}/accept` | Write |
| POST | `/invites/{token}/reject` | Write |

SOLO workspaces: invites limited to STUDENT role only.
