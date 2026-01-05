import os
import hmac
import hashlib
from datetime import datetime, timezone
from fastapi import FastAPI, Request
import asyncpg

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # This allows Lovable to see the data
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# This connects to the database Railway gives you
DATABASE_URL = os.getenv("DATABASE_URL")

async def get_db():
    return await asyncpg.connect(DATABASE_URL)

@app.post("/webhooks/zoom")
async def zoom_webhook(request: Request):
    data = await request.json()
    event = data.get("event")

    # 1. THE HANDSHAKE: This makes that "Validate" button in Zoom turn green
    if event == "endpoint.url_validation":
        plain_token = data["payload"]["plainToken"]
        secret = os.getenv("ZOOM_WEBHOOK_SECRET")
        hash_for_zoom = hmac.new(
            secret.encode(), 
            plain_token.encode(), 
            hashlib.sha256
        ).hexdigest()
        return {"plainToken": plain_token, "encryptedToken": hash_for_zoom}

    # 2. RECORDING: Get the info from Zoom
    payload = data.get("payload", {}).get("object", {})
    participant = payload.get("participant", {})
    
    # We use email or name to identify the person
    email = participant.get("email", "unknown")
    name = participant.get("user_name", "Anonymous")
    meeting_id = payload.get("id") # This will be your 826... ID
    timestamp = datetime.now(timezone.utc)

    conn = await get_db()

    if event == "meeting.participant_joined":
        # Record a person joining the deep work room
        await conn.execute(
            "INSERT INTO attendance (email, user_name, session_id, join_time) VALUES ($1, $2, $3, $4)",
            email, name, str(meeting_id), timestamp
        )
    
    elif event == "meeting.participant_left":
        # Record them leaving and calculate minutes spent working
        await conn.execute(
            """UPDATE attendance 
               SET leave_time = $1, 
                   duration_minutes = EXTRACT(EPOCH FROM ($1 - join_time))/60 
               WHERE email = $2 AND session_id = $3 AND leave_time IS NULL""",
            timestamp, email, str(meeting_id)
        )

    await conn.close()
    return {"status": "success"}

@app.get("/leaderboard")
async def get_leaderboard():
    conn = await get_db()
    # This version pulls all completed sessions so Lovable can calculate monthly stats
    rows = await conn.fetch("""
        SELECT user_name, join_time, duration_minutes 
        FROM attendance 
        WHERE duration_minutes IS NOT NULL
    """)
    await conn.close()
    return [dict(r) for r in rows]