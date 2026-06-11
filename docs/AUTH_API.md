# Auth API (OTP-based)

## Owner registration

1. `POST /auth/register` — stores intent, sends 6-digit OTP (10 min expiry)
2. `POST /auth/verify-otp` — `{ "email", "otp" }` → creates user + workspace
   - **SOLO**: `workspace.status = ACTIVE`, login allowed
   - **INSTITUTION**: `user.status = PENDING_APPROVAL`, no workspace until super admin approves via `POST /admin/institutions/{user_id}/approve`
3. `POST /auth/resend-otp` — new OTP (rate limited)

## Student / invite

- Same OTP flow via `POST /auth/verify-otp` after register

## Super admin

- `POST /auth/superadmin/login`
- `GET /admin/institutions/pending`
- `GET /admin/institutions/{user_id}`
- `POST /admin/institutions/{user_id}/approve` — creates workspace
- `POST /admin/institutions/{user_id}/reject` — `{ "reason": "..." }`

## Testing without reading the database

OTP is stored hashed in `email_otps`. In **development** (`FLASK_ENV=development`, default):

1. API responses include **`dev_otp`** (6-digit code) on register / resend / invite register.
2. The same code is printed in the **terminal** running `python run.py`:
   ```
   [DEV OTP] you@example.com -> 123456
   ```

Optional `.env`:

```env
EXPOSE_OTP_IN_DEV_RESPONSE=true   # default in development
```

Set to `false` to test email-only (production-like). **Never enable in production** (`ProductionConfig` defaults to off).

## Removed (breaking)

- `GET /auth/verify/{token}`
- `POST /auth/verify-email`
- `POST /auth/resend-verification`
