# Drawing Game — Product Requirements Document

**Version:** 1.0  
**Status:** Approved initial scope  
**Product type:** Real-time multiplayer web application

---

## 1. Product Overview

A browser-based multiplayer drawing game where players join private rooms, receive image references, draw independently within configurable time limits, and reveal their results together.

The game supports two modes:
1. Same Image — all players draw the same reference image.
2. Random Assignment — each player receives a different randomly assigned image.

The application is designed for casual multiplayer entertainment, with no birthday-specific branding or account registration.

## 2. Product Objectives

- Allow users to create and join private multiplayer rooms.
- Support 2–10 participants, including the host.
- Provide two distinct drawing experiences.
- Synchronize game progression and timers in real time.
- Provide a simple and reliable drawing canvas.
- Create an entertaining, host-controlled results reveal.
- Allow players to recover their sessions after disconnection.

## 3. User Roles

### Host
- Creates and manages a room.
- Selects the game mode.
- Uploads reference images.
- Configures game settings.
- Starts the game.
- Monitors player progress.
- Controls the results reveal.
- Participates as a regular drawing player.

### Player
- Joins using a room code.
- Selects a nickname.
- Participates in the active game.
- Views their assigned reference image.
- Draws independently.
- Submits and optionally reopens their drawing before the deadline.
- Views the final results.

## 4. Functional Requirements

### FR-01: Room Management
- The host can create a private room.
- Each room receives a unique join code.
- Players can join using the room code.
- Players choose their own nicknames.
- Minimum participants: 2.
- Maximum participants: 10, including the host.
- The room displays its current participants.
- The host can start the game when requirements are satisfied.
- Late arrivals wait for the next round.

### FR-02: Game Configuration

The host configures:

**Reference image viewing duration**
- 10 seconds
- 20 seconds
- 30 seconds
- 60 seconds

**Drawing duration**
- 3 minutes
- 5 minutes
- Unlimited

The host's preferred settings are saved in browser localStorage.

The active room configuration is stored on the backend and synchronized with all participants.

### FR-03: Game Mode 1 — Same Image

1. The host uploads exactly one reference image.
2. The image is made available to all active players.
3. All players enter the viewing stage.
4. The reference image appears with a countdown indicator.
5. The image disappears when the viewing timer expires.
6. Players enter their independent drawing canvases.
7. Drawing begins with the configured duration.
8. Drawings are collected and locked when the drawing stage ends.
9. The host proceeds to the reveal stage.

### FR-04: Game Mode 2 — Random Assignment

1. The host uploads exactly one image per active participant.
2. The backend validates the uploaded images.
3. The backend randomly shuffles and distributes the images.
4. Every player receives exactly one image.
5. Every image is assigned to exactly one player.
6. Players cannot see other players' assignments.
7. Each player enters the viewing stage independently of other players' private content.
8. The reference image disappears when the viewing timer expires.
9. Players draw independently.
10. All drawings are collected and locked when the drawing stage ends.
11. The host proceeds to the reveal stage.

### FR-05: Drawing Canvas

The initial drawing interface includes:
- Freehand brush.
- Color selection.
- Brush size adjustment.
- Eraser.
- Undo.
- Redo.
- Clear canvas.
- Submit drawing.

Players receive their own private drawing canvas.

The canvas must work on desktop and mobile devices.

### FR-06: Submission Management

- Players may submit before the drawing deadline.
- Submitted drawings are temporarily locked.
- Players may unsubmit while drawing time remains.
- Unsubmitting allows further editing.
- When the timer expires, all drawings become permanently locked for that game.
- The last saved drawing is retained if a player disconnects.

### FR-07: Results Reveal

The host controls the reveal process.

1. The host selects Start Reveal.
2. The backend establishes a randomized reveal order.
3. The first player's drawing appears without the original image.
4. The player's nickname is displayed underneath.
5. The host selects Reveal Original.
6. The drawing moves to one side.
7. The original image appears beside it.
8. The host selects Next Reveal.
9. The process repeats for every participant.

After the reveal starts, drawings and assignments cannot be modified.

### FR-08: Reconnection

- Players can reconnect using their room code and a secure saved session token.
- The application restores their player identity.
- Their assigned reference image remains unchanged.
- Their drawing is restored.
- The server maintains the original deadline.
- Reconnecting does not reset the drawing timer.
- The host can reconnect and recover host permissions.

### FR-09: Data Expiration

- Rooms are temporary.
- Completed rooms expire after 24 hours.
- Abandoned rooms expire after 24 hours without completion.
- Associated reference images and drawings are deleted upon expiration.
- No permanent player profiles are maintained.

## 5. Non-Functional Requirements

### Performance
- Fast initial website loading.
- Real-time room updates.
- Smooth drawing interaction.
- No unnecessary full-page reloads.
- Efficient image and drawing transfer.

### Reliability
- Server-authoritative timers.
- Server-authoritative random assignments.
- Automatic WebSocket reconnection.
- Drawing persistence during active games.
- Consistent game state across participants.

### Security and Privacy
- Private rooms.
- No public room directory.
- Host-only administrative actions.
- Server-side permission validation.
- Upload validation and file-size enforcement.
- Secure player reconnection tokens.
- Temporary media storage.
- No exposure of private image assignments.

### Compatibility
- Modern desktop browsers.
- Modern mobile browsers.
- Responsive interface.
- Mouse, trackpad and touchscreen drawing support.

## 6. Technical Stack

| Layer | Technology |
|---|---|
| Frontend | HTML, CSS, JavaScript |
| Drawing | HTML Canvas API |
| Backend | Python + FastAPI |
| Real-time | WebSockets |
| ORM | SQLAlchemy |
| Database | Neon PostgreSQL |
| Image storage | Temporary object storage |
| Frontend hosting | Netlify |
| Backend hosting | Always-on cloud VM |
| Version control | Git + GitHub |

## 7. Initial Data Entities

- **Room:** room ID, join code, host ID, status, settings, timestamps.
- **Player:** player ID, room ID, nickname, role, connection status.
- **Game:** game ID, room ID, mode, current phase, start and end timestamps.
- **ReferenceImage:** image ID, game ID, storage key.
- **Assignment:** player ID, reference image ID.
- **Drawing:** drawing ID, player ID, game ID, drawing data, submission status.
- **Reveal:** game ID, randomized reveal order, current reveal index.

## 8. Game Lifecycle

The application follows these states:

1. WAITING_ROOM
2. CONFIGURATION
3. IMAGE_VIEWING
4. DRAWING
5. DRAWING_COMPLETED
6. REVEAL_DRAWING
7. REVEAL_ORIGINAL
8. RESULTS_COMPLETED
9. EXPIRED

Only authorized host actions and valid game transitions can change the game state.

## 9. MVP Exclusions

The initial release will not include:

- User accounts or authentication profiles.
- Public room discovery.
- Text or voice chat.
- Scoring or competitive rankings.
- Social media integration.
- Advanced drawing brushes.
- Permanent artwork galleries.
- Birthday-specific themes.
- AI-generated images or drawing evaluation.

## 10. MVP Acceptance Criteria

The MVP is considered functional when:

- Two to ten people can join the same room.
- The host can participate and control the game.
- Both game modes work correctly.
- Random assignment never duplicates an image.
- Players cannot see other players' private assignments.
- Viewing and drawing timers synchronize correctly.
- Players can draw and submit independently.
- Players can unsubmit before the deadline.
- Drawings survive a page refresh or temporary disconnection.
- The host can reveal every drawing in randomized order.
- Each original image is revealed beside its correct drawing.
- Rooms and their associated media expire as specified.
- The application works on desktop and mobile browsers.
- The public deployment supports multiple simultaneous participants.

---

**End of PRD — Version 1.0**