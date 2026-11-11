from enum import Enum


class RoomStatus(str, Enum):
    WAITING = "waiting"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    EXPIRED = "expired"


class PlayerRole(str, Enum):
    HOST = "host"
    PLAYER = "player"


class ConnectionStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"


class GameMode(str, Enum):
    SAME_IMAGE = "same_image"
    RANDOM_ASSIGNMENT = "random_assignment"


class GamePhase(str, Enum):
    WAITING_ROOM = "waiting_room"
    CONFIGURATION = "configuration"
    IMAGE_VIEWING = "image_viewing"
    DRAWING = "drawing"
    DRAWING_COMPLETED = "drawing_completed"
    REVEAL_DRAWING = "reveal_drawing"
    REVEAL_ORIGINAL = "reveal_original"
    RESULTS_COMPLETED = "results_completed"
    EXPIRED = "expired"


class DrawingStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    LOCKED = "locked"
