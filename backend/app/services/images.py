from __future__ import annotations

import uuid
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile
from PIL import Image as PILImage, UnidentifiedImageError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models import GameMode, Player, ReferenceImage, Room
from app.schemas.rooms import RoomSettings
from app.services.lobby import count_uploaded_images, required_image_count
from app.services.rooms import ensure_waiting

ALLOWED_FORMATS = {
    "JPEG": ("image/jpeg", "jpg"),
    "PNG": ("image/png", "png"),
    "WEBP": ("image/webp", "webp"),
}


def _read_and_validate_upload(upload: UploadFile) -> tuple[bytes, str]:
    settings = get_settings()
    data = upload.file.read(settings.max_upload_size_bytes + 1)
    if not data:
        raise AppError(400, "The uploaded file is empty")
    if len(data) > settings.max_upload_size_bytes:
        raise AppError(400, "Image exceeds the 5 MB limit")

    try:
        with PILImage.open(BytesIO(data)) as image:
            image.verify()
            image_format = image.format
    except (UnidentifiedImageError, PILImage.DecompressionBombError):
        raise AppError(400, "Upload a valid JPG, PNG, or WEBP image") from None
    except (OSError, ValueError):
        raise AppError(400, "Upload a valid JPG, PNG, or WEBP image") from None

    if image_format not in ALLOWED_FORMATS:
        raise AppError(400, "Only JPG, PNG, and WEBP images are supported")

    return data, image_format


def get_storage_path(storage_key: str) -> Path:
    settings = get_settings()
    base = Path(settings.upload_dir).resolve()
    path = (base / storage_key).resolve()
    if not path.is_relative_to(base):
        raise AppError(400, "Invalid image storage path")
    return path


def save_reference_image(
    db: Session, room: Room, upload: UploadFile
) -> ReferenceImage:
    data, image_format = _read_and_validate_upload(upload)
    content_type, extension = ALLOWED_FORMATS[image_format]

    locked_room = db.scalar(
        select(Room).where(Room.id == room.id).with_for_update()
    )
    if locked_room is None:
        raise AppError(404, "Room not found")
    ensure_waiting(locked_room)

    room_settings = RoomSettings.model_validate(locked_room.settings or {})
    player_count = (
        db.scalar(
            select(func.count())
            .select_from(Player)
            .where(Player.room_id == locked_room.id)
        )
        or 0
    )
    uploaded = count_uploaded_images(db, locked_room.id)
    required = required_image_count(room_settings.mode, player_count)

    if uploaded >= required:
        if room_settings.mode == GameMode.SAME_IMAGE:
            message = "Same-image mode accepts exactly one reference image"
        else:
            message = (
                f"Random assignment mode accepts one image per player "
                f"({required} currently)"
            )
        raise AppError(409, message)

    storage_key = f"{locked_room.id}/{uuid.uuid4().hex}.{extension}"
    path = get_storage_path(storage_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

    original_filename = None
    if upload.filename:
        original_filename = Path(upload.filename).name[:255]

    image = ReferenceImage(
        room_id=locked_room.id,
        game_id=None,
        storage_key=storage_key,
        original_filename=original_filename,
        content_type=content_type,
        file_size=len(data),
    )
    db.add(image)
    try:
        db.commit()
    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)
        raise

    db.refresh(image)
    return image


def list_reference_images(db: Session, room: Room) -> list[ReferenceImage]:
    return list(
        db.scalars(
            select(ReferenceImage)
            .where(ReferenceImage.room_id == room.id)
            .order_by(ReferenceImage.created_at)
        ).all()
    )


def get_reference_image(
    db: Session, room: Room, image_id: uuid.UUID
) -> ReferenceImage:
    image = db.scalar(
        select(ReferenceImage).where(
            ReferenceImage.id == image_id,
            ReferenceImage.room_id == room.id,
        )
    )
    if image is None:
        raise AppError(404, "Reference image not found")
    return image


def delete_reference_image(
    db: Session, room: Room, image_id: uuid.UUID
) -> None:
    ensure_waiting(room)
    image = get_reference_image(db, room, image_id)
    path = get_storage_path(image.storage_key)
    db.delete(image)
    db.commit()
    path.unlink(missing_ok=True)
