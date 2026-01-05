import os
import hmac
import hashlib
from datetime import datetime, timezone
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import asyncpg

app = FastAPI()

# 1. PERMISSION SLIP FOR LOVABLE
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.getenv("DATABASE_URL")

async def get_db():
    return await asyncpg.connect(DATABASE_URL)

@app.post("/webhooks/zoom")
async def zoom_webhook(request: Request):
    data = await request.json()
    event = data.get("event")

    if event == "endpoint.url_validation":
        plain_token = data["payload"]["plainToken"]
        secret = os.getenv("ZOOM_WEBHOOK_SECRET")
        hash_for_zoom = hmac.new(
            secret.encode(), 
            plain_token.encode(), 
            hashlib.sha256
        ).hexdigest()
        return {"plainToken": plain_token, "encryptedToken": hash_for_zoom}

    payload = data.get("payload", {}).get("object", {})
    participant = payload.get("participant", {})
    
    email = participant.get("email", "unknown")
    name = participant.get("user_name", "Anonymous")
    meeting_id = payload.get("id") 
    timestamp = datetime.now(timezone.utc)

    conn = await get_db()

    if event == "meeting.participant_joined":
        # Create a new row when someone joins
        await conn.execute(
            "INSERT INTO attendance (email, user_name, session_id, join_time) VALUES ($1, $2, $3, $4)",
            email, name, str(meeting_id), timestamp
        )
    
    elif event == "meeting.participant_left":
        # Find the row that doesn't have a leave_time yet and update it
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
    # Pulls all completed sessions for both Daily and Monthly stats
    rows = await conn.fetch("""
        SELECT user_name, join_time, duration_minutes 
        FROM attendance 
        WHERE duration_minutes IS NOT NULL
    """)
    await conn.close()
    return [dict(r) for r in rows]