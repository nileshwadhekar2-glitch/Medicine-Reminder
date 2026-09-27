"""
main.py - FastAPI Backend for Medicine Reminder System
Endpoints:
  Auth       : POST /signup, POST /login
  Medicines  : POST /medicines, GET /medicines, PUT /medicines/{id}, DELETE /medicines/{id}
  Reminders  : POST /reminders, GET /reminders/today, PUT /reminders/{id}/status
  History    : GET /history
  Dashboard  : GET /dashboard/stats
"""

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
from datetime import date, datetime
import hashlib
import os
import secrets
import hmac
import re
import time
from pathlib import Path
from zoneinfo import ZoneInfo
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from postgrest.exceptions import APIError

from database import get_supabase

APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Kolkata")

def app_today():
    return datetime.now(ZoneInfo(APP_TIMEZONE)).date()

# ── App setup ──────────────────────────────────────────────────────────────────
app = FastAPI(title="Medicine Reminder API", version="1.0.0")

@app.exception_handler(APIError)
async def database_error_handler(request, exc):
    if str(exc.code) in {"PGRST205", "PGRST202", "42703", "42P01"}:
        return JSONResponse(status_code=503, content={"detail": "Database setup is incomplete. Run schema.sql in your Supabase SQL Editor, then try again."})
    if str(exc.code) == "23505":
        return JSONResponse(status_code=409, content={"detail": "This record already exists. Refresh and try again."})
    return JSONResponse(status_code=503, content={"detail": "Database request failed. Please try again or check the server configuration."})


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # allow the frontend (opened as file://) to call the API
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

class LazyDatabase:
    def table(self, name):
        try:
            return get_supabase().table(name)
        except ValueError as exc:
            raise HTTPException(503, "Database is not configured. Follow README.md setup instructions.") from exc


db = LazyDatabase()


# ── Helpers ────────────────────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600000).hex()
    return f"pbkdf2${salt}${digest}"


def verify_password(password, stored):
    if stored.startswith("pbkdf2$"):
        _, salt, digest = stored.split("$")
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600000).hex()
    else:
        actual, digest = hashlib.sha256(password.encode()).hexdigest(), stored
    return hmac.compare_digest(actual, digest)


def token_signature(value):
    key = os.getenv("AUTH_SECRET") or os.getenv("SUPABASE_KEY")
    if not key:
        raise HTTPException(503, "Configure SUPABASE_KEY or AUTH_SECRET on the server")
    return hmac.new(key.encode(), value.encode(), hashlib.sha256).hexdigest()


def issue_token(user_id):
    value = f"{user_id}.{int(time.time()) + 86400 * 7}"
    return f"{value}.{token_signature(value)}"


def get_user_from_token(token: str):
    try:
        user_id, expiry, signature = token.removeprefix("Bearer ").split(".")
        if int(expiry) <= time.time() or not hmac.compare_digest(signature, token_signature(f"{user_id}.{expiry}")):
            return None
        result = db.table("users").select("*").eq("id", int(user_id)).execute()
        return result.data[0] if result.data else None
    except (ValueError, TypeError):
        return None


def owned_medicine(medicine_id, user_id):
    rows = db.table("medicines").select("*").eq("id", medicine_id).eq("user_id", user_id).execute().data
    if not rows:
        raise HTTPException(404, "Medicine not found")
    return rows[0]


def ensure_today(user_id, today):
    medicines = db.table("medicines").select("*").eq("user_id", user_id).execute().data
    rows = []
    day = date.fromisoformat(today)
    for m in medicines:
        if not m["start_date"] <= today <= m["end_date"]:
            continue
        elapsed = (day - date.fromisoformat(m["start_date"])).days
        frequency = m["frequency"]
        if frequency == "As needed" or (frequency == "Weekly" and elapsed % 7) or (frequency == "Every alternate day" and elapsed % 2):
            continue
        times = m.get("reminder_times") or [m["reminder_time"]]
        for scheduled in times:
            rows.append(dict(user_id=user_id, medicine_id=m["id"], scheduled_date=today, scheduled_time=scheduled, status="pending"))
    if rows:
        db.table("reminders").upsert(rows, on_conflict="medicine_id,scheduled_date,scheduled_time", ignore_duplicates=True).execute()


# ── Pydantic schemas (request bodies) ─────────────────────────────────────────
class SignupRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    email: str = Field(pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$", max_length=255)
    password: str = Field(min_length=6, max_length=1024)

    @field_validator("username", "email", mode="before")
    @classmethod
    def clean(cls, value, info):
        return value.strip().lower() if info.field_name == "email" else value.strip()


class LoginRequest(BaseModel):
    email: str
    password: str


class MedicineCreate(BaseModel):
    name: str
    dosage: str
    frequency: str
    reminder_time: str          # "HH:MM"
    start_date: str             # "YYYY-MM-DD"
    end_date: str
    instructions: Optional[str] = ""
    reminder_times: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_schedule(self):
        if not self.name.strip() or not self.dosage.strip():
            raise ValueError("Name and dosage cannot be blank")
        start, end = date.fromisoformat(self.start_date), date.fromisoformat(self.end_date)
        if end < start:
            raise ValueError("End date cannot be before start date")
        counts = {"Once daily": 1, "Twice daily": 2, "Three times daily": 3, "Every alternate day": 1, "Weekly": 1, "As needed": 1}
        if self.frequency not in counts:
            raise ValueError("Unsupported frequency")
        times = self.reminder_times or [self.reminder_time]
        if any(not re.fullmatch(r"\d{2}:\d{2}(:00)?", t) for t in times):
            raise ValueError("Reminder times must use HH:MM")
        normalized = [datetime.strptime(t[:5], "%H:%M").strftime("%H:%M") for t in times]
        if len(set(normalized)) != counts[self.frequency]:
            raise ValueError("Enter one distinct reminder time for each daily dose")
        self.reminder_times = sorted(normalized)
        self.reminder_time = self.reminder_times[0]
        return self


class MedicineUpdate(BaseModel):
    reminder_times: Optional[list[str]] = None
    name: Optional[str] = None
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    reminder_time: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    instructions: Optional[str] = None


class ReminderCreate(BaseModel):
    medicine_id: int
    scheduled_time: str   # "HH:MM"
    scheduled_date: str   # "YYYY-MM-DD"


class StatusUpdate(BaseModel):
    status: str           # "taken" or "skipped"
    medicine_name: Optional[str] = None  # ignored; use the stored medicine name


# ── Auth Routes ────────────────────────────────────────────────────────────────
@app.post("/signup")
def signup(req: SignupRequest):
    """Register a new user."""
    # Check if email already exists
    existing = db.table("users").select("id").eq("email", req.email).execute()
    if existing.data:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed = hash_password(req.password)
    result = db.table("users").insert({
        "username": req.username,
        "email": req.email,
        "password_hash": hashed,
    }).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Could not create user")

    user = result.data[0]
    return {"message": "Account created!", "user_id": user["id"], "username": user["username"], "token": issue_token(user["id"])}


@app.post("/login")
def login(req: LoginRequest):
    """Login and return a signed, expiring session token."""
    result = (
        db.table("users")
        .select("*")
        .eq("email", req.email.strip().lower())
        .execute()
    )
    if not result.data or not verify_password(req.password, result.data[0]["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user = result.data[0]
    # Signed token prevents impersonation by changing a user ID.
    return {
        "message": "Login successful",
        "token": issue_token(user["id"]),
        "user_id": user["id"],
        "username": user["username"],
    }


# ── Medicine Routes ────────────────────────────────────────────────────────────
@app.post("/medicines")
def add_medicine(req: MedicineCreate, authorization: str = Header(default="")):
    """Add a new medicine for the logged-in user."""
    user = get_user_from_token(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    result = db.table("medicines").insert({
        "user_id": user["id"],
        "name": req.name,
        "dosage": req.dosage,
        "frequency": req.frequency,
        "reminder_time": req.reminder_time,
        "start_date": req.start_date,
        "end_date": req.end_date,
        "instructions": req.instructions,
        "reminder_times": req.reminder_times,
    }).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Could not add medicine")

    return {"message": "Medicine added!", "medicine": result.data[0]}


@app.get("/medicines")
def get_medicines(authorization: str = Header(default="")):
    """Get all medicines for the logged-in user."""
    user = get_user_from_token(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    result = (
        db.table("medicines")
        .select("*")
        .eq("user_id", user["id"])
        .order("created_at", desc=True)
        .execute()
    )
    return {"medicines": result.data}


@app.put("/medicines/{medicine_id}")
def update_medicine(medicine_id: int, req: MedicineUpdate, authorization: str = Header(default="")):
    """Update a medicine."""
    user = get_user_from_token(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Build only the fields that were provided
    existing = owned_medicine(medicine_id, user["id"])
    update_data = req.model_dump(exclude_none=True)
    if "reminder_time" in update_data and "reminder_times" not in update_data:
        update_data["reminder_times"] = []
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        validated = MedicineCreate(**{**existing, **update_data})
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    update_data = validated.model_dump()
    result = (
        db.table("medicines")
        .update(update_data)
        .eq("id", medicine_id)
        .eq("user_id", user["id"])
        .execute()
    )
    db.table("reminders").delete().eq("medicine_id", medicine_id).eq("user_id", user["id"]).eq("status", "pending").gte("scheduled_date", str(app_today())).execute()
    return {"message": "Medicine updated!", "medicine": result.data[0] if result.data else {}}


@app.delete("/medicines/{medicine_id}")
def delete_medicine(medicine_id: int, authorization: str = Header(default="")):
    """Delete a medicine."""
    user = get_user_from_token(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    owned_medicine(medicine_id, user["id"])
    db.table("medicines").delete().eq("id", medicine_id).eq("user_id", user["id"]).execute()
    return {"message": "Medicine deleted!"}


# ── Reminder Routes ────────────────────────────────────────────────────────────
@app.post("/reminders")
def create_reminder(req: ReminderCreate, authorization: str = Header(default="")):
    """Create a reminder entry for a specific date."""
    user = get_user_from_token(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    medicine = owned_medicine(req.medicine_id, user["id"])
    try:
        date.fromisoformat(req.scheduled_date)
        datetime.strptime(req.scheduled_time, "%H:%M")
    except ValueError:
        raise HTTPException(422, "Use YYYY-MM-DD and HH:MM")
    if not medicine["start_date"] <= req.scheduled_date <= medicine["end_date"]:
        raise HTTPException(422, "Reminder is outside the medicine date range")
    result = db.table("reminders").upsert({
        "medicine_id": req.medicine_id,
        "user_id": user["id"],
        "scheduled_time": req.scheduled_time,
        "scheduled_date": req.scheduled_date,
        "status": "pending",
    }, on_conflict="medicine_id,scheduled_date,scheduled_time", ignore_duplicates=True).execute()

    return {"message": "Reminder created!", "reminder": result.data[0] if result.data else {}}


@app.get("/reminders/today")
def get_todays_reminders(authorization: str = Header(default="")):
    """Get all reminders for today, joined with medicine name."""
    user = get_user_from_token(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    today = str(app_today())   # "YYYY-MM-DD"

    ensure_today(user["id"], today)
    reminders = (
        db.table("reminders")
        .select("*, medicines(name, dosage)")
        .eq("user_id", user["id"])
        .eq("scheduled_date", today)
        .order("scheduled_time")
        .execute()
    )
    return {"reminders": reminders.data, "date": today}


@app.put("/reminders/{reminder_id}/status")
def update_reminder_status(reminder_id: int, req: StatusUpdate, authorization: str = Header(default="")):
    """Mark a reminder as taken or skipped, and log to dose_history."""
    user = get_user_from_token(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if req.status not in ("taken", "skipped"):
        raise HTTPException(status_code=400, detail="Status must be 'taken' or 'skipped'")

    rows = db.table("reminders").select("*, medicines(name)").eq("id", reminder_id).eq("user_id", user["id"]).execute().data
    if not rows:
        raise HTTPException(404, "Reminder not found")
    reminder = rows[0]
    if reminder["status"] != "pending" and reminder["status"] != req.status:
        raise HTTPException(409, "This dose has already been recorded")
    # One database transaction owns the status transition and history insert.
    get_supabase().rpc("record_dose", {"p_reminder_id": reminder_id, "p_user_id": user["id"], "p_status": req.status, "p_timezone": APP_TIMEZONE}).execute()

    return {"message": f"Reminder marked as {req.status}"}


# ── History Route ──────────────────────────────────────────────────────────────
@app.get("/history")
def get_history(authorization: str = Header(default="")):
    """Get all dose history for the logged-in user."""
    user = get_user_from_token(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    result = (
        db.table("dose_history")
        .select("*")
        .eq("user_id", user["id"])
        .order("taken_date", desc=True)
        .execute()
    )
    return {"history": result.data}


# ── Dashboard Stats ────────────────────────────────────────────────────────────
@app.get("/dashboard/stats")
def dashboard_stats(authorization: str = Header(default="")):
    """Return summary counts for the dashboard."""
    user = get_user_from_token(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    today = str(app_today())

    ensure_today(user["id"], today)

    # Total medicines
    medicines = db.table("medicines").select("id").eq("user_id", user["id"]).execute()
    total_medicines = len(medicines.data)

    # Today's reminders
    todays = (
        db.table("reminders")
        .select("status")
        .eq("user_id", user["id"])
        .eq("scheduled_date", today)
        .execute()
    )
    today_total = len(todays.data)
    taken = sum(1 for r in todays.data if r["status"] == "taken")
    pending = sum(1 for r in todays.data if r["status"] == "pending")

    return {
        "username": user["username"],
        "total_medicines": total_medicines,
        "todays_reminders": today_total,
        "taken_today": taken,
        "pending_today": pending,
    }


app.mount("/", StaticFiles(directory=Path(__file__).resolve().parent.parent / "frontend", html=True), name="frontend")


# ── Run ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
