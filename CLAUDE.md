# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RoofScan AI is an AI-powered roof damage detection system that uses a **hybrid approach** combining YOLOv11 computer vision with LLM reasoning to analyze roof photos and generate professional PDF reports for insurance claims.

**Tech Stack:**
- Backend: Python 3.13+ with FastAPI, managed by `uv` package manager
- Frontend: React 19 with Vite, managed by Bun
- AI (Hybrid Mode - Default):
  - Roboflow YOLOv11 for precise damage detection (model: `roof-dmg-a1b1a/3`)
  - OpenAI GPT-4o for severity reasoning and classification (model: `gpt-4o-2024-11-20`)
- AI (Fallback): OpenAI GPT-4o Vision only (set `USE_HYBRID=false`)
- Deployment: Railway with RAILPACK builder

## Development Commands

### Backend (from `/backend` directory)

```bash
# Install dependencies
uv sync

# Run development server (with auto-reload)
uv run uvicorn main:app --reload --port 8000

# Run production server
uv run python main.py

# Add new Python dependency
uv add <package-name>
```

**Environment Setup:**
- Copy `backend/.env.example` to `backend/.env`
- Add `OPENAI_API_KEY` from https://platform.openai.com/api-keys
- Add `ROBOFLOW_API_KEY` from https://app.roboflow.com/settings/api
- Set `USE_HYBRID=true` for hybrid mode (YOLO + LLM) or `false` for OpenAI-only
- Optional: Configure `ROBOFLOW_MODEL_ID` and `ROBOFLOW_CONFIDENCE` threshold

**Logging:**
- Logs are written to `logs/roofscan.log` with rotation (10MB max, 5 backups)
- Log level: INFO (configurable in main.py)

### Frontend (from `/frontend` directory)

```bash
# Install dependencies
bun install

# Run development server (with HMR)
bun dev

# Build for production
bun build

# Lint code
bun lint

# Preview production build
bun preview

# Add new dependency
bun add <package-name>
```

## Architecture

### Request Flow (Streaming Mode - Default)

**NEW: Streaming endpoint provides instant feedback!**

1. **Image Upload** → Frontend uploads image via `/api/analyze-stream` endpoint
2. **YOLO Detection** → `roboflow_vision_service` runs YOLOv11 inference (2-3s)
3. **Stream Event 1 (yolo_complete)** → Frontend receives YOLO results immediately:
   - Precise bounding boxes, confidence scores, detected classes
   - Initial annotated image displayed to user
   - User sees results in 2-3 seconds!
4. **Parallel LLM Reasoning** → `hybrid_vision_service` processes damages concurrently:
   - Each damage analyzed independently in parallel (70% faster)
   - Severity assessment, damage type refinement, descriptions
   - Overall risk assessment and reasoning
5. **Stream Event 2 (llm_complete)** → Frontend receives enhanced results:
   - Updated with LLM descriptions and refined classifications
   - "Enhancing with AI..." badge shown during processing
   - Smooth transition from YOLO → enhanced results
6. **Image Annotation** → `image_processor` draws bounding boxes (called twice: YOLO, then enhanced)
7. **Results Display** → Progressive enhancement as data streams
8. **Report Generation** → Optional PDF via `/api/generate-report`

**Performance:**
- Time to first results: 2-3s (YOLO only)
- Time to final results: 5-8s (with parallel LLM)
- **60-80% reduction in perceived latency** vs sequential processing

### Backend Services (`backend/services/`)

**`hybrid_vision.py`** - Hybrid detection service (Default)
- `HybridVisionService.detect_damage()`: Main entry point for hybrid detection
- Step 1: Calls `roboflow_vision_service` for YOLOv11 detection
- Step 2: Sends YOLO results to GPT-4o for severity reasoning and classification refinement
- Step 3: Merges YOLO's precise bounding boxes with LLM's enhanced reasoning
- Returns JSON with `damages`, `summary`, `reasoning`, and `confidence` assessment
- Gracefully degrades if LLM API key missing (returns YOLO-only results)

**`roboflow_vision.py`** - YOLOv11 inference via Roboflow
- `RoboflowVisionService.detect_damage()`: Runs YOLOv11 inference
- Uses Roboflow Inference SDK with model ID: `roof-dmg-a1b1a/3`
- Returns detections with bounding boxes (pixel coordinates converted to percentages)
- Maps detected classes to severity levels and damage types
- Bounding boxes are percentages (0-100 scale): `[x1, y1, x2, y2]` where (0,0) is top-left

**`vision.py`** - OpenAI GPT-4o Vision (Fallback)
- `VisionService.detect_damage()`: Pure vision-based damage detection
- Used when `USE_HYBRID=false` in environment
- Converts images to base64, sends to GPT-4o with structured prompt
- Returns JSON with damages array containing: `type`, `severity`, `bbox`, `confidence`, `description`
- Implements retry logic (3 attempts)

**`image_processor.py`** - Bounding box annotation
- `ImageProcessor.annotate_image()`: Draws damage overlays on images
- Converts percentage bounding boxes to pixel coordinates (handles 0-1 and 0-100 ranges)
- Color coding by severity: Yellow (minor), Orange (moderate), Red (severe)
- Uses PIL/Pillow for image manipulation

**`report_generator.py`** - PDF report creation
- `ReportGenerator.generate_report()`: Creates professional PDF reports
- Uses ReportLab for PDF generation
- Sections: Header, Executive Summary, Recommendations, Annotated Image, Damage Details Table
- Returns BytesIO buffer for streaming response

### Damage Types

The system detects five damage types:
- `missing_shingles`: Exposed underlayment/wood
- `cracked_shingles`: Visible splits in shingles
- `hail_damage`: Circular dents/impact marks
- `wind_damage`: Lifted/curled shingle sections
- `torn_underlayment`: Membrane tears

Severity levels: `minor`, `moderate`, `severe`

### Frontend Components (`frontend/src/`)

**`App.jsx`** - Main application container
- Manages state: loading, error, results
- Handles upload via `handleUpload()` - calls `/api/analyze`
- Handles report generation via `handleGenerateReport()` - calls `/api/generate-report`
- Uses `VITE_API_URL` environment variable for API base URL (defaults to empty string for relative paths)

**`components/ImageUpload.jsx`** - Drag-and-drop upload interface
- Uses `react-dropzone` for file upload
- Validates: JPG/PNG only, 10MB max

**`components/Results.jsx`** - Analysis results display
- Shows original and annotated images side-by-side
- Displays damage summary statistics
- Renders damage details table
- Provides "Generate PDF Report" button

### File System Structure

Runtime directories (created automatically):
- `uploads/` - Original uploaded images (served via `/uploads` static route)
- `outputs/` - Annotated images (served via `/outputs` static route)

### API Endpoints

**POST `/api/analyze-stream`** (Recommended - Streaming)
- Accepts: `multipart/form-data` with `file` field
- Returns: Server-Sent Events (text/event-stream)
- Events:
  - `yolo_complete`: Initial YOLO results (2-3s)
  - `llm_complete`: Enhanced LLM results (3-10s later)
  - `error`: Error details
- Rate limit: 10 requests/minute per IP
- Max file size: 10MB
- Allowed types: `.jpg`, `.jpeg`, `.png`

**POST `/api/analyze`** (Legacy - Non-streaming)
- Accepts: `multipart/form-data` with `file` field
- Returns: JSON with complete results (5-15s wait)
- Rate limit: 10 requests/minute per IP
- Same validation as streaming endpoint

**GET `/health`**
- Returns: Service health status, API availability
- Used by load balancers and monitoring

**POST `/api/generate-report`**
- Accepts: JSON with `damages`, `summary`, `annotated_image_url`, `original_image_url`
- Returns: PDF file as streaming response

### CORS Configuration

Backend allows origins: `localhost:5173`, `localhost:5174`, `localhost:3000`, and Railway production URL.

### Deployment Notes

- Uses Railway with RAILPACK builder (supports `uv` natively)
- Start command: `uv run uvicorn main:app --host 0.0.0.0 --port $PORT`
- Uses absolute paths for `uploads/` and `outputs/` directories
- Frontend uses `VITE_API_URL` env var for API endpoint (empty string for relative paths in production)

## New Features & Improvements

### Streaming Response System
- **Server-Sent Events (SSE)** for progressive result delivery
- **Instant YOLO feedback** in 2-3 seconds
- **Background LLM enhancement** streams when ready
- **Visual progress indicator** ("Enhancing with AI..." badge)
- **60-80% reduction** in perceived latency

### Parallel LLM Processing
- Each damage analyzed **concurrently** instead of sequentially
- **70% faster** for multi-damage images
- Focused prompts per damage area (300 tokens vs 2000)
- Independent error handling per damage

### Infrastructure Improvements
- **Rate limiting**: 10 requests/minute per IP (slowapi)
- **Retry logic**: 3 attempts with exponential backoff (tenacity)
- **Structured logging**: Rotating file logs in `logs/` directory
- **Health check endpoint**: `/health` for monitoring
- **API key validation**: Fails fast on startup if keys missing
- **File cleanup**: Automatic deletion of files older than 24 hours
- **Graceful shutdown**: Proper cleanup on server stop

### Code Quality
- **Shared utilities module** eliminates duplicate code
- **Environment-based configuration** for all hardcoded values
- **Consistent error handling** across all services
- **Comprehensive logging** replaces print statements

## Key Implementation Details

### Bounding Box Coordinate System
- Vision model returns percentages (0-100 scale)
- `[x1, y1, x2, y2]` format where (0,0) is top-left, (100,100) is bottom-right
- Image processor handles both 0-1 and 0-100 range (detects max value)

### Structured Prompt Engineering
The vision prompt in `vision.py` is critical for accurate detection:
- Explicitly defines 5 damage types with descriptions
- Provides severity assessment criteria
- Includes detailed bounding box instructions with examples
- Requests JSON-only response (no markdown)

### Error Handling
- Backend validates file type and size before processing
- Vision service has 3-retry logic for API failures
- Frontend displays user-friendly error messages
- Cleanup of uploaded files on processing errors
- import the inference-sdk
from inference_sdk import InferenceHTTPClient

# initialize the client
CLIENT = InferenceHTTPClient(
    api_url="https://serverless.roboflow.com",
    api_key="{ROBOFLOW_API_KEY}"
)

# infer on a local image
result = CLIENT.infer("YOUR_IMAGE.jpg", model_id="roof-dmg-a1b1a/3")