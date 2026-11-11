from __future__ import annotations

import asyncio
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Room

logger = logging.getLogger(__name__)


def cleanup_expired_rooms(
    db: Session, *, now: datetime | None = None
) -> int:
    now = now or datetime.now(timezone.utc)
    rooms = db.scalars(
        select(Room).where(
            Room.expires_at.is_not(None),
            Room.expires_at <= now,
        )
    ).all()
    if not rooms:
        return 0

    upload_dir = Path(get_settings().upload_dir)
    room_ids = [room.id for room in rooms]

    try:
        for room in rooms:
            db.delete(room)
        db.commit()
    except Exception:
        db.rollback()
        raise

    for room_id in room_ids:
        room_dir = upload_dir / str(room_id)
        shutil.rmtree(room_dir, ignore_errors=True)
        if room_dir.exists():
            try:
                room_dir.rmdir()
            except OSError:
                pass

    logger.info("Deleted %s expired room(s)", len(room_ids))
    return len(room_ids)


async def cleanup_loop(interval_seconds: int | None = None) -> None:
    interval = interval_seconds or get_settings().room_cleanup_interval_seconds
    while True:
        try:
            with SessionLocal() as db:
                cleanup_expired_rooms(db)
        except Exception:
            logger.exception("Expired room cleanup failed")

        await asyncio.sleep(interval)
