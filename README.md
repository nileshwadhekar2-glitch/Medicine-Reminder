# MediRemind — Medicine Reminder

A college prototype built with HTML/CSS/JavaScript, FastAPI, and Supabase PostgreSQL.

## Run locally

Use **Python 3.12** with the pinned dependencies. The included `.venv` directory was created on Windows and cannot run on macOS. A working `.venv312` has been created on this Mac.

From the project folder:

```sh
# On this Mac, dependencies are already installed:
.venv312/bin/python backend/main.py
```

Open **http://127.0.0.1:8000**. The backend serves every frontend page. API docs are at http://127.0.0.1:8000/docs.

For a fresh installation:

```sh
python3.12 -m venv .venv312
source .venv312/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
python backend/main.py
```

On Windows use `py -3.12 -m venv .venv312`, `.venv312\Scripts\activate`, and `copy .env.example .env`.

## Connect Supabase

1. In the existing Supabase project's SQL Editor, run `schema.sql`. It creates the tables and upgrades existing ones in a transaction. The upgrade keeps dose history, detaches references to duplicate reminders, and removes duplicate reminder rows before creating a unique index. Back up existing data before applying to a populated project.
2. Copy `.env.example` to `.env` in this project folder.
3. Set `SUPABASE_URL` and the **backend-only secret key (`sb_secret_...`) or legacy service_role key** as `SUPABASE_KEY`. An anon key will not work with the enabled row-level security.
4. Generate `AUTH_SECRET` with `python -c "import secrets; print(secrets.token_hex(32))"` and paste it into `.env`.
5. Set `APP_TIMEZONE` to the browser's timezone (default `Asia/Kolkata`) and restart the backend.

Never commit `.env` or put the service-role key in frontend code. The app uses custom authentication; database tables are accessible through the backend service role. Existing numeric login tokens are invalid: log out and log back in after upgrading.

The frontend opens without credentials, but account and medicine operations require a configured database. The configured Supabase tables and dose-recording function have been verified. A live temporary-account check passed signup, login, medicine creation/edit/deletion, recurring reminder deduplication, taken status, history idempotency, dashboard counts, and history preservation. All generated test data was removed afterward.

## Using the app

Sign up → add a medicine → check Today's Schedule → mark Taken or Skip → view Dose History.

- Once daily uses the Reminder Time field.
- Twice or three times daily requires two or three distinct times in the Dose times field, such as `08:00, 20:00`. Enter the prescribed times; the app does not infer dose spacing.
- Weekly and alternate-day schedules start from the medicine's start date.
- As needed does not generate automatic reminders.
- Dashboard and Schedule requests generate that day's reminders within the medicine date range. Repeated requests preserve completed doses.
- Editing a medicine removes its pending reminders from today onward so the next schedule request generates the revised times. Completed history stays unchanged.
- When upgrading older twice/three-times-daily medicines, edit them to provide all dose times; old records contain only one time.
- Deleting a medicine preserves its dose history.

Reminder popups require an open Dashboard or Schedule page. They are in-page notifications, not background push notifications. Sleeping computers, suspended tabs, closed pages, and missed earlier days are not handled by a background scheduler. This prototype uses one configured timezone; use a matching browser timezone.

## Checks

```sh
.venv312/bin/python -m unittest discover -s backend -v
node tests/frontend.test.cjs
```

The backend suite checks password hashing, token tampering/expiry, ownership protection, schedule recurrence, multiple dose validation, static-page startup, and dispatch to the atomic dose-recording database function. Unit-test database interactions are mocked. A separate live signup-to-history check has also passed against the configured Supabase project. Concurrent-load testing has not been performed.

## Project layout

- `backend/main.py`: API, input validation, signed sessions, scheduling, static frontend
- `backend/database.py`: lazy Supabase client and project-relative `.env` loading
- `backend/models.py`: educational OOP examples
- `backend/test_app.py`: regression tests
- `frontend/`: login, dashboard, medicine forms, schedule, history, shared helpers
- `schema.sql`: tables, migration, RLS, and transactional dose recording

Passwords use salted PBKDF2; legacy SHA-256 password hashes remain readable for existing accounts. Sessions expire after seven days. Public deployment still needs its own deployment review, including HTTPS, login rate limiting, account recovery, and background notification requirements.
# Medicine-Reminder
