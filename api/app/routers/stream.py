import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import text

from app.db import ReaderSession
from app.security import decode_token
from app.serializers import row_to_dict

router = APIRouter(prefix="/api", tags=["tiempo-real"])

EVENT_QUERY = """
    SELECT id, mag, place, region, event_time, updated_at, tsunami, longitude, latitude, depth_km
    FROM curated.events
    WHERE updated_at > :last_seen
      AND event_time >= now() - interval '2 days'
    ORDER BY updated_at ASC
    LIMIT 50
"""


def fetch_events(last_seen):
    with ReaderSession() as db:
        rows = (
            db.execute(text(EVENT_QUERY), {"last_seen": last_seen})
            .mappings()
            .all()
        )
    return [row_to_dict(row) for row in rows]


def fetch_initial():
    with ReaderSession() as db:
        rows = (
            db.execute(
                text(
                    """
                    SELECT id, mag, place, region, event_time, updated_at, tsunami,
                           longitude, latitude, depth_km
                    FROM curated.events
                    WHERE event_time >= now() - interval '6 hours'
                    ORDER BY event_time DESC
                    LIMIT 10
                    """
                )
            )
            .mappings()
            .all()
        )
    return [row_to_dict(row) for row in reversed(rows)]


@router.get("/stream")
async def stream(request: Request, token: str = Query(min_length=10)):
    payload = decode_token(token)
    if payload.get("role") not in {"viewer", "admin"}:
        raise HTTPException(status_code=403, detail="Rol no autorizado")

    async def event_generator():
        yield "retry: 5000\n\n"
        initial = fetch_initial()
        last_seen = None
        for event in initial:
            yield f"data: {json.dumps(event)}\n\n"
        if initial:
            last_seen = max(
                datetime.fromisoformat(event["updated_at"]) for event in initial
            )
        if last_seen is None:
            last_seen = datetime.now(timezone.utc)
        while True:
            if await request.is_disconnected():
                break
            try:
                events = fetch_events(last_seen)
            except Exception:
                yield "event: error\ndata: {\"detail\":\"stream temporalmente no disponible\"}\n\n"
                await asyncio.sleep(5)
                continue
            if events:
                last_seen = datetime.fromisoformat(events[-1]["updated_at"])
                for event in events:
                    yield f"data: {json.dumps(event)}\n\n"
            else:
                yield ": heartbeat\n\n"
            await asyncio.sleep(5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
