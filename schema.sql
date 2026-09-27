-- ============================================================
--  Medicine Reminder System – Supabase SQL Schema
--  Run this in: Supabase Dashboard → SQL Editor → New Query
-- ============================================================

BEGIN;

-- 1. Users table
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    username      VARCHAR(100) NOT NULL,
    email         VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at    TIMESTAMP DEFAULT NOW()
);

-- 2. Medicines table
CREATE TABLE IF NOT EXISTS medicines (
    id             SERIAL PRIMARY KEY,
    user_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name           VARCHAR(200) NOT NULL,
    dosage         VARCHAR(100) NOT NULL,
    frequency      VARCHAR(100) NOT NULL,
    reminder_time  TIME        NOT NULL,        -- e.g. 08:00
    start_date     DATE        NOT NULL,
    end_date       DATE        NOT NULL,
    instructions   TEXT        DEFAULT '',
    created_at     TIMESTAMP   DEFAULT NOW()
);

-- 3. Reminders table  (one row = one scheduled dose on a specific date)
CREATE TABLE IF NOT EXISTS reminders (
    id             SERIAL PRIMARY KEY,
    medicine_id    INTEGER NOT NULL REFERENCES medicines(id) ON DELETE CASCADE,
    user_id        INTEGER NOT NULL REFERENCES users(id)    ON DELETE CASCADE,
    scheduled_time TIME    NOT NULL,
    scheduled_date DATE    NOT NULL,
    status         VARCHAR(20) DEFAULT 'pending',  -- pending | taken | skipped
    created_at     TIMESTAMP DEFAULT NOW()
);

-- 4. Dose History table
CREATE TABLE IF NOT EXISTS dose_history (
    id             SERIAL PRIMARY KEY,
    user_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reminder_id    INTEGER REFERENCES reminders(id),
    medicine_name  VARCHAR(200),
    taken_date     DATE,
    taken_time     VARCHAR(10),
    status         VARCHAR(20),     -- taken | skipped
    created_at     TIMESTAMP DEFAULT NOW()
);

-- Upgrade existing installations as well as new databases.
ALTER TABLE medicines ADD COLUMN IF NOT EXISTS reminder_times JSONB DEFAULT '[]'::jsonb;
-- Preserve history when a medicine and its reminders are removed.
ALTER TABLE dose_history DROP CONSTRAINT IF EXISTS dose_history_reminder_id_fkey;
ALTER TABLE dose_history ADD CONSTRAINT dose_history_reminder_id_fkey
  FOREIGN KEY (reminder_id) REFERENCES reminders(id) ON DELETE SET NULL;
-- Keep historical rows while detaching duplicate reminder references.
UPDATE dose_history SET reminder_id = NULL WHERE reminder_id IN (
 SELECT id FROM (SELECT id, row_number() OVER (
 PARTITION BY medicine_id, scheduled_date, scheduled_time ORDER BY
 CASE WHEN status <> 'pending' THEN 0 ELSE 1 END, id) AS rn FROM reminders) ranked WHERE rn > 1
);
DELETE FROM reminders WHERE id IN (
 SELECT id FROM (SELECT id, row_number() OVER (
 PARTITION BY medicine_id, scheduled_date, scheduled_time ORDER BY
 CASE WHEN status <> 'pending' THEN 0 ELSE 1 END, id) AS rn FROM reminders) ranked WHERE rn > 1
);
CREATE UNIQUE INDEX IF NOT EXISTS reminder_unique_dose
 ON reminders(medicine_id, scheduled_date, scheduled_time);

CREATE OR REPLACE FUNCTION record_dose(p_reminder_id integer, p_user_id integer, p_status text, p_timezone text DEFAULT 'Asia/Kolkata')
RETURNS void LANGUAGE plpgsql AS $$
DECLARE dose reminders%ROWTYPE; med_name text;
BEGIN
 IF p_status NOT IN ('taken', 'skipped') THEN RAISE EXCEPTION 'Invalid status'; END IF;
 SELECT * INTO dose FROM reminders WHERE id = p_reminder_id AND user_id = p_user_id FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Reminder not found'; END IF;
 IF dose.status = p_status THEN RETURN; END IF;
 IF dose.status <> 'pending' THEN RAISE EXCEPTION 'Dose already recorded'; END IF;
 SELECT name INTO med_name FROM medicines WHERE id = dose.medicine_id;
 UPDATE reminders SET status = p_status WHERE id = p_reminder_id;
 INSERT INTO dose_history(user_id, reminder_id, medicine_name, taken_date, taken_time, status)
 VALUES(p_user_id, p_reminder_id, med_name, (CURRENT_TIMESTAMP AT TIME ZONE p_timezone)::date, to_char(CURRENT_TIMESTAMP AT TIME ZONE p_timezone, 'HH24:MI'), p_status);
END;
$$;

-- Only the backend service-role key may access these custom-auth tables.
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE medicines ENABLE ROW LEVEL SECURITY;
ALTER TABLE reminders ENABLE ROW LEVEL SECURITY;
ALTER TABLE dose_history ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON FUNCTION record_dose(integer, integer, text, text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION record_dose(integer, integer, text, text) TO service_role;

COMMIT;
