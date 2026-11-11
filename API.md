# DentalHealth API

The API uses JSON or multipart/form-data for image uploads. Authenticated requests
supply `Authorization: Bearer <access token>`. Errors use `{"errors": ["..."]}`.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/register/` | Create patient, student or doctor account |
| POST | `/api/login/` | Sign in using email and password; returns user, access and refresh |
| POST | `/api/token/` | Alternate JWT sign-in endpoint; returns access and refresh |
| POST | `/api/token/refresh/` | Rotate refresh token; submit the current refresh |
| POST | `/api/logout/` | Blacklist the authenticated user's submitted refresh token |
| GET, PUT, PATCH | `/api/profile/` | View or update the current user's profile |
| DELETE | `/api/account/delete/` | Delete the authenticated account and its records |
| POST | `/api/cases/create/` | Patient creates their own case |
| GET | `/api/cases/` | Patient's cases; approved doctors see all cases |
| PATCH | `/api/cases/{id}/status/` | Approved doctor changes case status |
| GET | `/media/{path}` | Authorized owner or approved clinical access only |

Registration fields: `email`, `fullname`, `phone`, `password`, and `user_type`
(`patient`, `student`, `doctor`). Passwords must meet Django validation and contain
at least 12 characters. Email addresses are case-insensitively unique. Registering
a doctor creates an unapproved profile; an administrator must verify and approve
clinical access in Django admin before the doctor can view or modify cases.

Profile fields depend on the role. Nested user information is read-only, as are
profile ID and computed age. Updating birthdate recalculates age; future dates
are rejected. Clinical approval and privileges can only be managed by admin.

Case creation requires `description`. Optional fields include `title`, `pain_type`,
`pain_location`, `pain_duration`, `treated_before`, and `photos`. Patient, status,
physician notes and timestamps are read-only on this endpoint. Status changes
accept exactly one of `pending`, `active`, `completed`, or `rejected`.

Case listing returns `count`, `next`, `previous`, `results`, ordered newest first.
Use `?status=pending`, `?page=2` and `?page_size=20` (maximum 100).

Images must be valid JPEG, PNG or WebP, at most 5 MiB and 20 megapixels.
The same upload limits and birthdate validation apply in Django administration.
Public media mappings must not be configured. Use an authenticated fetch for media URLs.
Deleting accounts or image records removes their uploaded files after database
commit. Replacing an image removes the prior file after commit.

Registration and sign-in are rate-limited. A 401 response means authentication is
needed or invalid, 403 means the role lacks permission, and 429 means retry later.
The service contains no email activation or password reset email feature.

The optional public preview account is limited to read-only Django administration
with a separate synthetic database. Its credentials cannot obtain or use clinical
JWT tokens, and it cannot access private medical uploads.
