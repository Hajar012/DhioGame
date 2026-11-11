from __future__ import annotations

from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import RoomContext, get_room_context
from app.core.errors import AppError
from app.db.session import get_db
from app.schemas.rooms import (
    ImageUploadResponse,
    ReadyUpdate,
    ReferenceImageResponse,
    RoomCreate,
    RoomJoin,
    RoomSessionResponse,
    RoomSettingsUpdate,
    RoomState,
)
from app.services import images, lobby, realtime, rooms

router = APIRouter(prefix="/rooms", tags=["rooms"])


@router.post(
    "",
    response_model=RoomSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_room(
    payload: RoomCreate,
    db: Session = Depends(get_db),
) -> RoomSessionResponse:
    room, player, token = rooms.create_room(db, payload)
    return RoomSessionResponse(
        token=token,
        player=lobby.player_to_response(room, player),
        room=lobby.build_room_state(db, room),
    )


@router.post("/join", response_model=RoomSessionResponse)
def join_room(
    payload: RoomJoin,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> RoomSessionResponse:
    room, player, token = rooms.join_room(
        db, payload.room_code, payload.nickname
    )
    realtime.queue_room_state(background_tasks, room.join_code)
    return RoomSessionResponse(
        token=token,
        player=lobby.player_to_response(room, player),
        room=lobby.build_room_state(db, room),
    )


@router.get("/{room_code}", response_model=RoomState)
def read_room(
    context: RoomContext = Depends(get_room_context),
    db: Session = Depends(get_db),
) -> RoomState:
    return lobby.build_room_state(db, context.room)


@router.post("/{room_code}/ready", response_model=RoomState)
def update_ready(
    payload: ReadyUpdate,
    background_tasks: BackgroundTasks,
    context: RoomContext = Depends(get_room_context),
    db: Session = Depends(get_db),
) -> RoomState:
    rooms.set_ready(db, context.room, context.player, payload.is_ready)
    realtime.queue_room_state(background_tasks, context.room.join_code)
    return lobby.build_room_state(db, context.room)


@router.patch("/{room_code}/settings", response_model=RoomState)
def update_settings(
    payload: RoomSettingsUpdate,
    background_tasks: BackgroundTasks,
    context: RoomContext = Depends(get_room_context),
    db: Session = Depends(get_db),
) -> RoomState:
    rooms.require_host(context.room, context.player)
    rooms.update_settings(db, context.room, payload)
    realtime.queue_room_state(background_tasks, context.room.join_code)
    return lobby.build_room_state(db, context.room)


@router.get(
    "/{room_code}/images",
    response_model=list[ReferenceImageResponse],
)
def list_reference_images(
    context: RoomContext = Depends(get_room_context),
    db: Session = Depends(get_db),
) -> list[ReferenceImageResponse]:
    rooms.require_host(context.room, context.player)
    return [
        lobby.to_image_response(image, context.room.join_code)
        for image in images.list_reference_images(db, context.room)
    ]


@router.post(
    "/{room_code}/images",
    response_model=ImageUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_reference_image(
    room_code: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    context: RoomContext = Depends(get_room_context),
    db: Session = Depends(get_db),
) -> ImageUploadResponse:
    rooms.require_host(context.room, context.player)
    image = images.save_reference_image(db, context.room, file)
    realtime.queue_room_state(background_tasks, context.room.join_code)
    return ImageUploadResponse(
        image=lobby.to_image_response(image, context.room.join_code),
        room=lobby.build_room_state(db, context.room),
    )


@router.delete("/{room_code}/images/{image_id}", response_model=RoomState)
def delete_reference_image(
    room_code: str,
    image_id: UUID,
    background_tasks: BackgroundTasks,
    context: RoomContext = Depends(get_room_context),
    db: Session = Depends(get_db),
) -> RoomState:
    rooms.require_host(context.room, context.player)
    images.delete_reference_image(db, context.room, image_id)
    realtime.queue_room_state(background_tasks, context.room.join_code)
    return lobby.build_room_state(db, context.room)


@router.get(
    "/{room_code}/images/{image_id}/content",
    response_class=FileResponse,
)
def read_reference_image_content(
    room_code: str,
    image_id: UUID,
    context: RoomContext = Depends(get_room_context),
    db: Session = Depends(get_db),
) -> FileResponse:
    rooms.require_host(context.room, context.player)
    image = images.get_reference_image(db, context.room, image_id)
    path = images.get_storage_path(image.storage_key)
    if not path.is_file():
        raise AppError(404, "Reference image file is missing")

    return FileResponse(
        path,
        media_type=image.content_type or "application/octet-stream",
        filename=image.original_filename or path.name,
    )
