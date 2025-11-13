import os
import uuid
import json
import asyncio
import logging
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Any
from collections import Counter
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, HTTPException, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Load environment variables from .env file
load_dotenv()

# Setup structured logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(
            'logs/roofscan.log',
            maxBytes=10485760,  # 10MB
            backupCount=5
        ),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

from services.vision import vision_service
from services.hybrid_vision import hybrid_vision_service
from services.image_processor import image_processor
from services.report_generator import report_generator
from services.utils import calculate_summary, validate_api_keys, cleanup_old_files

# Initialize FastAPI app
app = FastAPI(title="RoofScan AI API")

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Enable CORS for local React dev server and production
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "https://wonderful-gratitude-production.up.railway.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup directories - use absolute paths for production
UPLOAD_DIR = Path("uploads").absolute()
OUTPUT_DIR = Path("outputs").absolute()
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Mount static file directories
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")

# File validation constants
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}


class ReportRequest(BaseModel):
    """Request model for report generation."""
    damages: list
    summary: dict
    annotated_image_url: str
    original_image_url: str


# File cleanup worker
def start_cleanup_worker():
    """Start background worker for cleaning old files."""
    def worker():
        while True:
            try:
                cleanup_old_files(UPLOAD_DIR, max_age_hours=24)
                cleanup_old_files(OUTPUT_DIR, max_age_hours=24)
            except Exception as e:
                logger.error(f"File cleanup error: {e}")
            time.sleep(3600)  # Run every hour

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    logger.info("File cleanup worker started")


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    try:
        # Validate API keys
        validate_api_keys()
        logger.info("API keys validated successfully")

        # Start file cleanup worker
        start_cleanup_worker()

        logger.info("RoofScan AI API started successfully")
    except Exception as e:
        logger.error(f"Startup error: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("RoofScan AI API shutting down gracefully")


@app.get("/")
async def root():
    return {"message": "RoofScan AI API", "status": "running"}


@app.get("/health")
async def health_check():
    """
    Health check endpoint for load balancers and monitoring.

    Returns service status and API availability.
    """
    roboflow_available = os.getenv("ROBOFLOW_API_KEY") and os.getenv("ROBOFLOW_API_KEY") != "not-set"
    openai_available = os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_API_KEY") != "not-set"

    return {
        "status": "healthy",
        "services": {
            "yolo_available": roboflow_available,
            "llm_available": openai_available,
            "hybrid_mode": os.getenv("USE_HYBRID", "true").lower() == "true"
        }
    }


@app.post("/api/analyze")
@limiter.limit("10/minute")
async def analyze_roof(request: Request, file: UploadFile = File(...)):
    """
    Analyze a roof image for damage detection.

    Args:
        file: Uploaded image file (JPG/PNG, max 10MB)

    Returns:
        JSON response with detected damages and annotated image URL
    """
    logger.info(f"Analysis started for file: {file.filename}")
    start_time = time.time()

    # Validate file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        logger.warning(f"Invalid file type rejected: {file_ext}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Read file content
    content = await file.read()

    # Validate file size
    if len(content) > MAX_FILE_SIZE:
        logger.warning(f"File too large rejected: {len(content)} bytes")
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
        )

    # Generate unique filename
    file_id = str(uuid.uuid4())
    original_filename = f"{file_id}{file_ext}"
    original_path = UPLOAD_DIR / original_filename

    # Save uploaded file
    with open(original_path, "wb") as f:
        f.write(content)

    logger.debug(f"File saved: {original_path}")

    try:
        # Use hybrid approach: YOLOv11 for detection + GPT-4o for reasoning
        # Set USE_HYBRID=false in .env to fall back to pure OpenAI vision
        use_hybrid = os.getenv("USE_HYBRID", "true").lower() == "true"

        if use_hybrid:
            logger.info("Using hybrid vision (YOLO + LLM)")
            detection_result = await hybrid_vision_service.detect_damage(original_path)
        else:
            logger.info("Using pure OpenAI vision")
            detection_result = await vision_service.detect_damage(original_path)

        damages = detection_result.get("damages", [])

        # Generate annotated image with bounding boxes
        annotated_filename = f"{file_id}_annotated.jpg"
        annotated_path = OUTPUT_DIR / annotated_filename

        image_processor.annotate_image(original_path, annotated_path, damages)

        # Calculate damage summary statistics (using shared utility)
        summary = calculate_summary(damages)

        elapsed_time = time.time() - start_time
        logger.info(f"Analysis completed in {elapsed_time:.2f}s - {summary['total_damages']} damages detected")

        # Return complete response
        return JSONResponse({
            "status": "success",
            "damages": damages,
            "summary": summary,
            "original_image_url": f"/uploads/{original_filename}",
            "annotated_image_url": f"/outputs/{annotated_filename}",
            "file_id": file_id
        })

    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"Analysis failed after {elapsed_time:.2f}s: {str(e)}", exc_info=True)

        # Clean up uploaded file on error
        if original_path.exists():
            original_path.unlink()

        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing image: {str(e)}"
        )


@app.post("/api/analyze-stream")
@limiter.limit("10/minute")
async def analyze_roof_stream(request: Request, file: UploadFile = File(...)):
    """
    Stream analysis results as they become available (Server-Sent Events).

    Flow:
    1. Event 1 (yolo_complete): YOLO results + annotated image (2-3s)
    2. Event 2 (llm_complete): LLM enhancements (3-10s later)

    This provides instant visual feedback while LLM processes in background.
    """
    logger.info(f"Streaming analysis started for file: {file.filename}")
    start_time = time.time()

    async def generate():
        file_ext = Path(file.filename).suffix.lower()
        content = await file.read()

        # Validation
        if file_ext not in ALLOWED_EXTENSIONS:
            error_event = {
                "event": "error",
                "data": {"error": f"Invalid file type: {file_ext}"}
            }
            yield f"data: {json.dumps(error_event)}\n\n"
            return

        if len(content) > MAX_FILE_SIZE:
            error_event = {
                "event": "error",
                "data": {"error": "File too large"}
            }
            yield f"data: {json.dumps(error_event)}\n\n"
            return

        # Save file
        file_id = str(uuid.uuid4())
        original_filename = f"{file_id}{file_ext}"
        original_path = UPLOAD_DIR / original_filename

        with open(original_path, "wb") as f:
            f.write(content)

        try:
            # STEP 1: Run YOLO detection (FAST)
            logger.info("Step 1: Running YOLO detection")
            yolo_start = time.time()

            from services.roboflow_vision import roboflow_vision_service
            yolo_result = roboflow_vision_service.detect_damage(original_path)
            yolo_damages = yolo_result.get("damages", [])

            yolo_time = time.time() - yolo_start
            logger.info(f"YOLO completed in {yolo_time:.2f}s - {len(yolo_damages)} damages")

            # Generate initial annotated image with YOLO boxes
            annotated_filename = f"{file_id}_annotated.jpg"
            annotated_path = OUTPUT_DIR / annotated_filename
            image_processor.annotate_image(original_path, annotated_path, yolo_damages)

            # Ensure image is written to disk before sending event
            import time as time_module
            time_module.sleep(0.1)  # Small delay to ensure file is fully written

            # Stream Event 1: YOLO results (immediate feedback!)
            event_1 = {
                "event": "yolo_complete",
                "data": {
                    "damages": yolo_damages,
                    "summary": calculate_summary(yolo_damages),
                    "annotated_image_url": f"/outputs/{annotated_filename}?t={int(time.time() * 1000)}",
                    "original_image_url": f"/uploads/{original_filename}",
                    "file_id": file_id,
                    "status": "yolo_complete",
                    "processing_time": yolo_time
                }
            }
            yield f"data: {json.dumps(event_1)}\n\n"

            # STEP 2: Run LLM reasoning (SLOW but parallel)
            use_hybrid = os.getenv("USE_HYBRID", "true").lower() == "true"

            if use_hybrid and yolo_damages:
                logger.info("Step 2: Running parallel LLM reasoning")
                llm_start = time.time()

                # Run parallel LLM reasoning
                llm_enhancement = await hybrid_vision_service._run_llm_reasoning_parallel(
                    yolo_damages,
                    original_path
                )

                # Merge YOLO + LLM results
                enhanced_damages = hybrid_vision_service._merge_detections(
                    yolo_damages,
                    llm_enhancement
                )

                llm_time = time.time() - llm_start
                logger.info(f"LLM reasoning completed in {llm_time:.2f}s")

                # Re-annotate with enhanced data (if descriptions changed)
                image_processor.annotate_image(original_path, annotated_path, enhanced_damages)

                # Stream Event 2: LLM enhancements
                event_2 = {
                    "event": "llm_complete",
                    "data": {
                        "damages": enhanced_damages,
                        "summary": calculate_summary(enhanced_damages),
                        "reasoning": llm_enhancement.get("overall_assessment", {}).get("reasoning", ""),
                        "annotated_image_url": f"/outputs/{annotated_filename}?v={uuid.uuid4()}",  # Cache bust
                        "status": "complete",
                        "processing_time": llm_time,
                        "total_time": time.time() - start_time
                    }
                }
                yield f"data: {json.dumps(event_2)}\n\n"
            else:
                # No LLM processing, just finish
                event_final = {
                    "event": "complete",
                    "data": {
                        "status": "complete",
                        "total_time": time.time() - start_time
                    }
                }
                yield f"data: {json.dumps(event_final)}\n\n"

            total_time = time.time() - start_time
            logger.info(f"Streaming analysis completed in {total_time:.2f}s")

        except Exception as e:
            logger.error(f"Streaming analysis failed: {str(e)}", exc_info=True)

            # Clean up on error
            if original_path.exists():
                original_path.unlink()

            error_event = {
                "event": "error",
                "data": {"error": str(e)}
            }
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@app.post("/api/generate-report")
async def generate_report(request: ReportRequest):
    """
    Generate a PDF report from analysis results.

    Args:
        request: Report request containing damages, summary, and image URLs

    Returns:
        PDF file download
    """
    try:
        # Extract annotated image filename from URL
        annotated_filename = request.annotated_image_url.split("/")[-1]
        annotated_path = OUTPUT_DIR / annotated_filename

        if not annotated_path.exists():
            raise HTTPException(
                status_code=404,
                detail="Annotated image not found"
            )

        # Generate PDF report
        pdf_buffer = report_generator.generate_report(
            damages=request.damages,
            summary=request.summary,
            annotated_image_path=annotated_path
        )

        # Return PDF as streaming response
        from datetime import datetime
        filename = f"roof_damage_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating report: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
