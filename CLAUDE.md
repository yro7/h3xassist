# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

### Critical Thinking and Feedback

**IMPORTANT: Always critically evaluate and challenge user suggestions, even when they seem reasonable.**

**USE BRUTAL HONESTY**: Don't try to be polite or agreeable. Be direct, challenge assumptions, and point out flaws immediately.

- **Question assumptions**: Don't just agree - analyze if there are better approaches
- **Offer alternative perspectives**: Suggest different solutions or point out potential issues
- **Challenge organization decisions**: If something doesn't fit logically, speak up
- **Point out inconsistencies**: Help catch logical errors or misplaced components
- **Research thoroughly**: Never skim documentation or issues - read them complete before responding
- **Admit ignorance**: Say "I don't know" instead of guessing or agreeing without understanding

This critical feedback helps improve decision-making and ensures robust solutions. Being agreeable is less valuable than being thoughtful and analytical.

### Example Behaviors

- ✅ "I disagree - that component belongs in a different file because..."
- ✅ "Have you considered this alternative approach?"
- ✅ "This seems inconsistent with the pattern we established..."
- ❌ Just implementing suggestions without evaluation

## Architectural Principles

### MANDATORY: Separation of Responsibilities 

**CRITICAL RULE: Every class, module, and function must have a SINGLE, clearly defined responsibility. Challenge ANY design that mixes concerns.**

#### Browser Architecture Rules:
- **PlatformController**: ONLY platform-specific meeting logic (join, speakers, leave). NEVER audio, storage, or orchestration.
- **ExternalBrowserSession**: ONLY browser process lifecycle and CDP communication. NEVER meeting-specific logic.
- **MeetingRecorder**: ONLY orchestration of recording components. NEVER browser details or platform specifics.

#### Audio Architecture Rules:
- **VirtualDevice**: ONLY PipeWire device management. NEVER meeting logic.
- **AudioRecorder**: ONLY audio capture and encoding. NEVER speaker detection or storage.
- **AudioEncoder**: ONLY format conversion. NEVER device management.

#### Storage Architecture Rules:
- **RecordingStore**: ONLY filesystem operations and metadata. NEVER audio processing or meeting logic.
- **RecordingHandle**: ONLY single recording lifecycle. NEVER batch operations or orchestration.

#### API Architecture Rules:
- **CalendarSyncService**: ONLY Outlook calendar synchronization. NEVER direct recording or scheduling.
- **MeetingScheduler**: ONLY scheduling and queue management. NEVER calendar sync or recording execution.
- **RecordingManager**: ONLY recording lifecycle and file operations. Uses one-recorder-per-meeting pattern with UUID mapping. NEVER scheduling or calendar logic.
- **ConnectionManager**: ONLY WebSocket connections and broadcasts. NEVER business logic or data persistence.
- **PostProcessService**: ONLY post-processing orchestration. NEVER recording or scheduling.

#### Responsibility Violation Examples (FORBIDDEN):
- ❌ MeetingRecorder calling `page.goto()` directly
- ❌ PlatformController managing audio devices  
- ❌ AudioRecorder handling speaker intervals
- ❌ RecordingStore knowing about browser sessions
- ❌ MeetingScheduler starting recordings directly (should delegate to RecordingManager)
- ❌ CalendarSyncService managing recording lifecycle
- ❌ Any class doing "just a little bit" of another's job

#### Enforcement Rules:
1. **Challenge every import**: If class A imports class B, A should only use B's public interface for A's core responsibility
2. **Question every parameter**: If a method takes >3 parameters, it probably violates SRP
3. **Reject convenience methods**: "It's easier to just add this here" is ALWAYS wrong
4. **Force dependency injection**: Classes should receive dependencies, never create them internally
5. **Mandate interfaces/protocols**: Any cross-module communication must go through defined protocols

**When in doubt, ALWAYS choose more separation over convenience.**

## Project Overview

H3xAssist is an automated meeting assistant that can join, record, transcribe, and summarize meetings. It consists of:

1. **Python Backend** (`src/h3xassist/`): Core meeting automation, recording, and processing
2. **Next.js Web Frontend** (`h3xassist-web/`): Modern React dashboard for management and monitoring  
3. **FastAPI Server** (`src/h3xassist/api/`): REST API and WebSocket server bridging frontend and backend

The system uses browser automation (Playwright), audio processing (PipeWire/FFmpeg), speech recognition (WhisperX), and AI summarization (Google Gemini).

## Development Commands

The project includes a Taskfile for streamlined development workflows. Install Task from https://taskfile.dev to use these commands.

### Quick Start with Taskfile
```bash
task install          # Install all dependencies
task setup           # Run complete setup wizard
task dev             # Start development environment
task help            # Show all available commands
```

### Essential Development Tasks
- **`task dev`** - Start both backend and frontend in development mode
- **`task dev:backend`** - Start backend service only
- **`task dev:frontend`** - Start frontend dev server only
- **`task build`** - Build frontend for production (static export to `out/`)
- **`task prod`** - Build frontend and start production service

### Code Quality Tasks
- **`task format`** - Format all code (Python + frontend)
- **`task lint`** - Run all linters
- **`task typecheck`** - Run type checking (mypy + tsc)
- **`task check`** - Run all checks (lint + typecheck)
- **`task fix`** - Auto-fix linting issues
- **`task pre-commit`** - Run pre-commit checks

### Utility Tasks
- **`task types`** - Generate TypeScript types from OpenAPI
- **`task clean`** - Clean all build artifacts and caches

### Manual Commands (without Taskfile)

#### Python Environment
- Use `uv run` for all Python commands
- Install dependencies: `uv sync`
- Run the CLI: `uv run h3xassist --help`

#### Web Frontend
- Install dependencies: `cd h3xassist-web && pnpm install`
- Development server: `cd h3xassist-web && pnpm run dev` (requires API server running)
- Build: `cd h3xassist-web && pnpm run build` (creates static export in `out/`)
- Production: Static files are served by FastAPI backend (no separate frontend server needed)

#### Service Operations
- **Start complete service**: `uv run h3xassist service run` (starts API server + scheduler + processing)
- **Check service status**: `uv run h3xassist service status`
- **Web interface**: Access at `http://localhost:11411` by default (configurable in settings.yaml)

#### Code Quality Tools
- **Format code**: `uv run ruff format src/`
- **Lint code**: `uv run ruff check src/`
- **Type checking**: `uv run mypy`
- **Auto-fix linting issues**: `uv run ruff check --fix src/`

#### TypeScript API Client Generation
- **Generate types**: `cd h3xassist-web && pnpm run types:generate` (requires API server running)
- **Generate with formatting**: `cd h3xassist-web && pnpm run types:generate-dev`

### Development Notes
- **No formal test suite**: Project currently lacks pytest configuration - test via web interface
- **Manual validation**: Test functionality via web interface and API endpoints
- **Type hints**: Code uses modern Python typing (Pydantic models, type annotations)
- **Strict mypy configuration**: Enforces comprehensive type checking

### CLI Command Structure
The CLI is focused on configuration, setup, and service management:
- `uv run h3xassist config` - Interactive configuration wizard
- `uv run h3xassist setup browser` - Configure browser profiles  
- `uv run h3xassist setup outlook` - Microsoft Graph authentication
- `uv run h3xassist setup models` - Download AI models
- `uv run h3xassist service run` - Start complete service (API server + scheduler + processing)
- `uv run h3xassist service status` - Check service health

**All operational functionality (recording, processing, event scheduling) is handled through the web interface and API.**

## Architecture

### High-Level Architecture
The system follows a 3-tier architecture with integrated production deployment:

1. **Frontend Layer** (`h3xassist-web/`): Next.js React application
   - Real-time dashboard with WebSocket updates
   - Event scheduling and recording management
   - shadcn/ui components with Tailwind CSS
   - TypeScript throughout with strict type checking
   - **Production**: Static export (`output: 'export'`) served by FastAPI backend

2. **API Layer** (`src/h3xassist/api/`): FastAPI server with dependency injection
   - REST endpoints for CRUD operations
   - WebSocket server for real-time updates
   - Manager pattern for business logic isolation
   - Automatic Outlook calendar integration
   - **Production**: Serves static frontend files from `h3xassist-web/out/`

3. **Core Layer** (`src/h3xassist/`): Python business logic
   - Meeting automation and recording orchestration  
   - Audio pipeline with PipeWire integration
   - Post-processing with WhisperX and AI summarization
   - File-based storage with structured metadata

### Production Deployment Architecture
In production, there's **only one server process** needed:
- FastAPI serves both API endpoints (`/api/v1/*`) and static frontend files
- Next.js builds to static files (`next build` creates `out/` directory)
- All traffic goes through single port (default: 11411)
- SPA routing handled by FastAPI catch-all route serving `index.html`

### API Architecture Pattern
The API layer uses a **Manager + Dependency Injection** pattern:

- **CalendarSyncService**: Synchronizes with Outlook calendar and creates meeting records
- **MeetingScheduler**: Manages scheduling queue and triggers recordings at the right time
- **RecordingManager**: Manages recording lifecycle, MeetingRecorder instances, and file operations
- **ConnectionManager**: Handles WebSocket connections and broadcasts refresh signals
- **PostProcessService**: Orchestrates transcription, diarization, and summarization pipeline
- **Dependencies Module**: Provides singleton managers with proper initialization/cleanup

Managers are connected via callback patterns for loose coupling. Data flow:
```
Outlook → CalendarSyncService → MeetingScheduler → RecordingManager → PostProcessService
                                                           ↓
                                               ConnectionManager → WebSocket → Frontend
```

### Core Modules
- **settings.py**: Pydantic settings with YAML config support (~/.config/h3xassist/settings.yaml)
- **models/**: Centralized data models (api.py, recording.py, summary.py, profile.py)
- **errors.py**: Custom HTTP exceptions (MeetingNotFoundError, ProfileNotFoundError)
- **storage/**: Recording filesystem storage with RecordingStore/RecordingHandle
- **scheduler/**: Meeting scheduling and queue management (scheduler.py, calendar_sync.py)
- **cli/**: Typer-based CLI for configuration, setup, and service management
- **audio/**: Consolidated audio pipeline (virtual.py, recorder.py)
- **browser/**: Playwright automation and profile management (session.py, profiles.py, platforms.py)
- **postprocess/**: WhisperX transcription pipeline with stages/ architecture
- **speaker/**: Diarization refinement (mapping.py for anchor-based assignment only)
- **integrations/**: External service integrations (outlook.py for Microsoft Graph)
- **meeting_recorder.py**: Core recording orchestration
- **api/**: FastAPI server with managers, routers, and WebSocket support

### Key Architectural Decisions
- **Manager Pattern**: API business logic isolated in manager classes with dependency injection
- **WebSocket-First**: Real-time updates prioritized over polling for responsive UI
- **Consolidated Audio Pipeline**: All audio processing (PipeWire, FFmpeg, virtual devices) unified in audio/
- **Storage Module**: RecordingStore and related components organized in storage/ directory
- **Speaker Mapping**: Only anchor-based assignment (soft assignment removed due to poor performance)  
- **Minimal CLI**: Only configuration, setup, and service management - all operations via web interface
- **Settings Centralization**: Single settings.py file instead of fragmented config modules
- **Postprocess Pipeline**: Staged processing architecture (asr → mapping → summary → export)
- **Session-Based Controllers**: PlatformControllers receive ExternalBrowserSession for complete browser lifecycle control
- **Protocol-Based Interfaces**: All cross-module communication uses defined protocols (PlatformController, etc.)
- **One-Recorder-Per-Meeting**: RecordingManager maintains UUID->MeetingRecorder mapping instead of shared instances
- **Graceful vs Cancel Operations**: Distinct stop (graceful with processing) vs cancel (immediate with artifact deletion) patterns

### Recording Operation Patterns

#### Stop vs Cancel Architecture
The system implements two distinct recording termination patterns:

**Stop Operation (Graceful)**:
- API: `POST /api/v1/recordings/{id}/stop`
- Behavior: Triggers `asyncio.Event` to signal graceful shutdown
- Process: Allows audio recording to complete naturally, then runs post-processing
- Result: Complete processed recording with transcript and summary
- Frontend: Square (■) button icon

**Cancel Operation (Immediate)**:
- API: `DELETE /api/v1/recordings/{id}`
- Behavior: Immediately cancels asyncio task and deletes all artifacts
- Process: Terminates recording immediately, removes all files from disk
- Result: No artifacts remain, recording marked as CANCELLED
- Frontend: X (✕) button icon with destructive styling

#### MeetingRecorder Architecture
- **One Instance Per Recording**: Each recording gets its own MeetingRecorder instance
- **UUID Mapping**: RecordingManager maintains `Dict[UUID, MeetingRecorder]` for lifecycle control
- **Graceful Stop Support**: MeetingRecorder exposes `trigger_graceful_stop()` method with asyncio.Event
- **Async Task Management**: Each recording runs as separate asyncio task for proper isolation

### Meeting Lifecycle
Complete automated workflow:
1. **Calendar Sync**: CalendarSyncService fetches Outlook events and stores meeting metadata
2. **Scheduling**: MeetingScheduler monitors upcoming meetings and queues recordings
3. **Pre-Meeting**: Scheduler triggers recording 2 minutes before meeting start
4. **Join & Record**: RecordingManager creates MeetingRecorder instance for orchestration
5. **Real-time Updates**: ConnectionManager broadcasts RefreshSignal to update frontend
6. **Recording Control**: Users can stop (graceful) or cancel (immediate) via web interface
7. **Post-Processing**: PostProcessService runs transcription, diarization, and summarization (stop only)
8. **Storage**: RecordingStore persists structured output files with metadata

### Data Storage Structure
```
~/.local/share/h3xassist/meetings/
  └── YYYYMMDD_HHMMSS-provider-platform-subject-eid-hash/
      ├── audio.ogg              # Opus-encoded recording
      ├── transcript.txt          # Plain text transcript
      ├── transcript.json         # Structured transcript with speaker intervals
      ├── state.json             # Recording metadata and status
      ├── summary.md             # Generated markdown summary
      ├── summary.json           # Structured summary data
      └── browser.log            # Browser console logs and debug info
```

### Audio Processing Pipeline
1. **Virtual Devices**: PipeWire virtual sink/source creation
2. **Browser Audio**: Route meeting audio to virtual devices with stability profiles
3. **FFmpeg Capture**: Real-time PCM → Opus/OGG encoding
4. **Speaker Detection**: Caption interval tracking during recording
5. **Post-Processing**: WhisperX ASR + diarization + anchor-based speaker mapping

### Browser Stability Architecture
The system supports multiple browser stability profiles for different environments:

- **default**: Standard Chromium flags for normal operation
- **software_safe**: CPU-only rendering (--disable-gpu, --use-gl=swiftshader) for maximum stability, disables hardware video decode
- **gpu_balanced**: GPU enabled but hardware video decode disabled (--use-gl=angle), balances performance and stability

**Stability Core Features** (applied when profile != "default"):
- Extension isolation (--disable-extensions, --disable-component-update)
- Anti-throttling protection (--disable-background-timer-throttling, --disable-renderer-backgrounding)
- Keyring bypass (--password-store=basic, --use-mock-keychain) for bot profiles
- Auto-permission for media streams (--autoplay-policy=no-user-gesture-required)

**Additional Options**:
- `force_turn_tcp`: Force WebRTC through TCP via TURN servers instead of UDP
- `disable_telemetry`: Disable browser telemetry and domain reliability reporting

### Speaker Assignment Architecture
The speaker/ module contains focused components:
- **mapping.py**: Anchor-based assignment algorithm (build_speaker_mapping_anchor)
- **utils.py**: Utility functions (union_intervals, sum_overlap)

**Critical**: Only anchor-based speaker mapping is used. The soft assignment algorithm was removed due to poor accuracy.

### Data Models Architecture
Centralized models in `models/` directory:
- **api.py**: API response models (ErrorResponse, MessageResponse, RefreshSignal)
- **recording.py**: Core recording models (RecordingMeta, Transcript, CaptionInterval, DiarSegment)
- **summary.py**: AI summarization models (Summary, SummarySection)
- **profile.py**: Browser profile configuration models

### Error Handling
Custom exceptions in `errors.py`:
- **MeetingNotFoundError**: HTTP 404 for non-existent meetings
- **ProfileNotFoundError**: HTTP 404 for missing browser profiles

## Configuration

Settings hierarchy (higher priority overrides lower):
1. Environment variables (H3XASSIST_* prefix with __ for nesting)
2. ~/.config/h3xassist/settings.yaml
3. Default values in settings.py

### Essential Settings
- `models.whisperx_model_name`: ASR model (default: "large-v3")
- `models.hf_token`: Required for speaker diarization
- `summarization.provider_token`: Google API key for summaries
- `integrations.outlook`: Microsoft Graph credentials for calendar access
- `general.meeting_display_name`: Name shown to meeting participants
- `paths.meetings_base_dir`: Storage location (default: ~/.local/share/h3xassist)
- `browser.stability_profile`: Browser stability mode ("default", "software_safe", "gpu_balanced")
- `browser.force_turn_tcp`: Force WebRTC through TCP instead of UDP (default: false)
- `browser.disable_telemetry`: Disable browser telemetry reporting (default: true)
- `http.host`: API server host (default: "127.0.0.1")
- `http.port`: API server port (default: 11411)

## Dependencies

### Core Python Dependencies
- **whisperx>=3.4.2**: Speech recognition and diarization
- **playwright>=1.55.0**: Browser automation
- **google-genai>=1.32.0**: AI summarization
- **msgraph-sdk>=1.40.0**: Microsoft Graph integration
- **pydantic>=2.11.7**: Settings and data validation
- **typer>=0.16.1**: CLI framework
- **fastapi>=0.116.1**: API server framework
- **uvicorn>=0.35.0**: ASGI server

### Development Dependencies
- **mypy>=1.17.1**: Static type checking
- **ruff>=0.12.12**: Python linting and formatting
- **types-***: Type stubs for external libraries

### Frontend Dependencies
- **next@15.5.2**: React framework with App Router
- **@radix-ui/***: Headless UI components
- **tailwindcss@^4**: Utility-first CSS framework
- **typescript@^5**: Type checking and safety
- **sonner**: Toast notifications
- **lucide-react**: Modern icon library
- **openapi-fetch**: Type-safe API client generation
- **@tanstack/react-query**: Server state management

### System Requirements
- Linux (PipeWire audio system required)
- Python >=3.12
- Node.js 18+ and pnpm (for web frontend)
- FFmpeg (for audio processing)
- Chromium/Chrome browser for automation

## Frontend-Backend Integration

### Communication Patterns
- **TypeScript Client**: openapi-fetch generates typed API client from OpenAPI spec
- **React Query**: Manages caching, synchronization, and state management
- **WebSocket Updates**: RefreshSignal triggers automatic cache invalidation
- **API Endpoints**:
  - `GET /api/v1/recordings` - List all recordings with metadata
  - `POST /api/v1/recordings` - Create new recording from event ID
  - `POST /api/v1/recordings/{id}/stop` - Graceful stop with post-processing
  - `DELETE /api/v1/recordings/{id}` - Cancel immediately and delete artifacts
  - `GET /api/v1/calendars/outlook/events` - List Outlook calendar events
  - `POST /api/v1/calendars/outlook/sync` - Trigger calendar synchronization
  - `GET /api/v1/profiles` - List browser profiles
  - `POST /api/v1/profiles` - Create new browser profile
  - `GET /api/v1/service/status` - Check service health
  - `GET /api/v1/settings` - Get current settings
  - `POST /api/v1/settings` - Update settings

### WebSocket Architecture
- **Endpoint**: `ws://localhost:11411/api/v1/ws` (port configurable)
- **Message Type**: RefreshSignal (simple notification, no payload)
- **Auto-reconnect**: Frontend automatically reconnects on disconnect
- **React Query Integration**: Refresh signals trigger automatic refetch

## Development Workflow

### Setting Up Development Environment

#### With Taskfile (Recommended)
```bash
task install        # Install all dependencies
task setup          # Run complete setup wizard
task dev            # Start development environment
```

#### Manual Setup
1. Install Python dependencies: `uv sync`
2. Install frontend dependencies: `cd h3xassist-web && pnpm install`
3. Configure application: `uv run h3xassist config`
4. Set up browser profiles: `uv run h3xassist setup browser`

### Running in Development

#### With Taskfile
```bash
task dev            # Start both backend and frontend
# OR run separately:
task dev:backend    # Terminal 1: Start backend
task dev:frontend   # Terminal 2: Start frontend
```

#### Manual
1. Start backend service: `uv run h3xassist service run`
2. In separate terminal, start frontend: `cd h3xassist-web && pnpm run dev`
3. Access development UI at `http://localhost:3000`

### Production Deployment

#### With Taskfile
```bash
task build          # Build frontend static files
task service:run    # Start production service (serves API + frontend)
# OR combined:
task prod           # Build + start production service
```

#### Manual Production
```bash
cd h3xassist-web && pnpm run build  # Build static files to out/
uv run h3xassist service run         # Start service (auto-serves static files)
# Access at http://localhost:11411 (or configured port)
```

**Important**: In production, you only need one process. The FastAPI backend automatically serves the built frontend files from `h3xassist-web/out/` directory.

### Code Quality Checks

#### With Taskfile
```bash
task check          # Run all checks (lint + typecheck)
task format         # Format all code  
task fix            # Auto-fix issues
task pre-commit     # Format + check + git status
```

#### Manual
- Format before commit: `uv run ruff format src/`
- Check linting: `uv run ruff check src/`
- Fix linting issues: `uv run ruff check --fix src/`
- Type checking: `uv run mypy`

### Important Development Notes
- Always use absolute imports in Python code
- Never use relative imports
- Create Pydantic models instead of untyped dicts
- Follow strict separation of responsibilities (see Architecture section)
- Test changes via web interface (no automated test suite)
- Regenerate TypeScript types after API changes: `cd h3xassist-web && pnpm run types:generate`