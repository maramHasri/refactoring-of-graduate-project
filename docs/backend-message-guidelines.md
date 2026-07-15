# Backend Message Guidelines

These rules keep API response messages stable and consistent across the project.

The frontend translates backend English messages using its own dictionaries.
Backend localization is intentionally **not** implemented.

## Source of truth

- All backend response messages live in `utils/messages.py` as `Messages.*` constants.
- Catalog for frontend teams: `docs/backend-messages.md`.

## Rules for developers

1. **Never write hardcoded response messages** in services, routes, decorators, or utilities.
2. **Always use** the centralized `Messages` registry, for example:
   ```python
   from utils.messages import Messages
   raise NotFoundError(Messages.USER_NOT_FOUND)
   return {"message": Messages.WORKSPACE_CREATED}, 201
   ```
3. **Reuse an existing message** when the meaning is the same.
4. **Do not create duplicates** such as `"User not found"` and `"No user found"`.
5. Backend messages are **part of the API contract**. Frontend translation maps depend on the exact English text.
6. **Do not casually change** existing standardized message strings. Changing wording breaks frontend dictionaries.
7. **Any new message** must be:
   - Added to `utils/messages.py` first
   - Documented in `docs/backend-messages.md`
   - Then referenced from application code

## Adding a new message

1. Check `utils/messages.py` and `docs/backend-messages.md` for an existing constant.
2. If none fits, add a new constant under the correct domain section in `Messages`.
3. Use a clear, stable English sentence.
4. Prefer `{placeholder}` + `.format(...)` for dynamic values.
5. Update `docs/backend-messages.md`.
6. Use `Messages.YOUR_CONSTANT` in code.

## Dynamic values

```python
raise ValidationError(
    Messages.YOU_HAVE_REACHED_THE_MAXIMUM_ALLOWED_ATTEMPTS_MAX_ATTEMPTS.format(
        max_attempts=max_attempts
    )
)
```

Keep placeholders simple names (`{max_attempts}`, `{reason}`, `{id}`).
Do not put Python expressions inside message templates.

## Out of scope

Do **not** introduce:

- Localization keys
- `message_code` / translation keys for i18n
- Flask-Babel / gettext
- Translation database tables
- `Accept-Language` handling

Keep English messages as the stable contract.
The frontend is responsible for Arabic/English display translation.
