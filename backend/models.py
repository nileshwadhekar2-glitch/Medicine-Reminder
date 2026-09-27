"""
models.py - Python OOP Classes for Medicine Reminder System
This demonstrates: Class, Object, Constructor, Methods, Encapsulation
"""

from datetime import datetime, date


# ─────────────────────────────────────────────
# 1.  User Class
# ─────────────────────────────────────────────
class User:
    """Represents a registered user of the application."""

    def __init__(self, id: int, username: str, email: str, password_hash: str):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.created_at = datetime.now()

    def get_info(self) -> dict:
        """Return a safe (no-password) dict of the user."""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "created_at": str(self.created_at),
        }

    def __repr__(self):
        return f"User(id={self.id}, username={self.username})"


# ─────────────────────────────────────────────
# 2.  Medicine Class
# ─────────────────────────────────────────────
class Medicine:
    """Represents a medicine added by a user."""

    def __init__(
        self,
        id: int,
        user_id: int,
        name: str,
        dosage: str,
        frequency: str,
        reminder_time: str,
        start_date: str,
        end_date: str,
        instructions: str = "",
    ):
        self.id = id
        self.user_id = user_id
        self.name = name
        self.dosage = dosage
        self.frequency = frequency      # e.g. "Once daily", "Twice daily"
        self.reminder_time = reminder_time  # e.g. "08:00"
        self.start_date = start_date
        self.end_date = end_date
        self.instructions = instructions

    def is_active_today(self) -> bool:
        """Check whether this medicine is still within its date range."""
        today = date.today()
        try:
            start = datetime.strptime(self.start_date, "%Y-%m-%d").date()
            end = datetime.strptime(self.end_date, "%Y-%m-%d").date()
            return start <= today <= end
        except ValueError:
            return False

    def get_info(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "dosage": self.dosage,
            "frequency": self.frequency,
            "reminder_time": self.reminder_time,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "instructions": self.instructions,
            "is_active_today": self.is_active_today(),
        }

    def __repr__(self):
        return f"Medicine(id={self.id}, name={self.name}, dosage={self.dosage})"


# ─────────────────────────────────────────────
# 3.  Reminder Class
# ─────────────────────────────────────────────
class Reminder:
    """Represents a scheduled reminder for a medicine on a specific date."""

    STATUSES = ("pending", "taken", "skipped")

    def __init__(
        self,
        id: int,
        medicine_id: int,
        user_id: int,
        scheduled_time: str,
        scheduled_date: str,
        status: str = "pending",
    ):
        self.id = id
        self.medicine_id = medicine_id
        self.user_id = user_id
        self.scheduled_time = scheduled_time  # "HH:MM"
        self.scheduled_date = scheduled_date  # "YYYY-MM-DD"
        self.status = status                  # pending / taken / skipped

    def mark_taken(self):
        """Mark this reminder as taken."""
        self.status = "taken"

    def mark_skipped(self):
        """Mark this reminder as skipped."""
        self.status = "skipped"

    def get_info(self) -> dict:
        return {
            "id": self.id,
            "medicine_id": self.medicine_id,
            "user_id": self.user_id,
            "scheduled_time": self.scheduled_time,
            "scheduled_date": self.scheduled_date,
            "status": self.status,
        }

    def __repr__(self):
        return (
            f"Reminder(id={self.id}, medicine_id={self.medicine_id}, "
            f"time={self.scheduled_time}, status={self.status})"
        )


# ─────────────────────────────────────────────
# 4.  DoseHistory Class
# ─────────────────────────────────────────────
class DoseHistory:
    """Records the final outcome of a dose (taken / skipped)."""

    def __init__(
        self,
        id: int,
        user_id: int,
        medicine_id: int,
        medicine_name: str,
        taken_date: str,
        taken_time: str,
        status: str,
    ):
        self.id = id
        self.user_id = user_id
        self.medicine_id = medicine_id
        self.medicine_name = medicine_name
        self.taken_date = taken_date
        self.taken_time = taken_time
        self.status = status

    def get_info(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "medicine_id": self.medicine_id,
            "medicine_name": self.medicine_name,
            "taken_date": self.taken_date,
            "taken_time": self.taken_time,
            "status": self.status,
        }

    def __repr__(self):
        return (
            f"DoseHistory(medicine={self.medicine_name}, "
            f"date={self.taken_date}, status={self.status})"
        )
