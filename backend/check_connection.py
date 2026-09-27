"""Read-only database configuration check; never prints secrets or row contents."""
from database import get_supabase


def main():
    try:
        db = get_supabase()
    except Exception as exc:
        print(f'Client initialization failed: {type(exc).__name__}')
        return 1
    failed = False
    for table, fields in [('users', 'id'), ('medicines', 'id,reminder_times'), ('reminders', 'id'), ('dose_history', 'id')]:
        try:
            db.table(table).select(fields).limit(1).execute()
            print(f'{table}: accessible')
        except Exception as exc:
            print(f'{table}: failed ({type(exc).__name__}, code {getattr(exc, "code", "unavailable")})')
            failed = True
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
