import os
import uuid
from pathlib import Path
from typing import Optional, Dict, Any
from collections import Counter

from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

# Load environment variables from .env file
load_dotenv()

from services.vision import vision_service
from services.image_processor import image_processor
from services.report_generator import report_generator

# Initialize FastAPI app
app = FastAPI(title="RoofScan AI API")

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


def _calculate_summary(damages: list) -> Dict[str, Any]:
    """Calculate damage summary statistics."""
    if not damages:
        return {
            "total_damages": 0,
            "by_type": {},
            "by_severity": {}
        }

    # Count by type
    types = [d.get("type", "unknown") for d in damages]
    by_type = dict(Counter(types))

    # Count by severity
    severities = [d.get("severity", "unknown") for d in damages]
    by_severity = dict(Counter(severities))

    return {
        "total_damages": len(damages),
        "by_type": by_type,
        "by_severity": by_severity
    }


@app.get("/")
async def root():
    return {"message": "RoofScan AI API", "status": "running"}


@app.post("/api/analyze")
async def analyze_roof(file: UploadFile = File(...)):
    """
    Analyze a roof image for damage detection.

    Args:
        file: Uploaded image file (JPG/PNG, max 10MB)

    Returns:
        JSON response with detected damages and annotated image URL
    """
    # Validate file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Read file content
    content = await file.read()

    # Validate file size
    if len(content) > MAX_FILE_SIZE:
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

    try:
        # Call OpenAI GPT-4o Vision for damage detection
        detection_result = await vision_service.detect_damage(original_path)
        damages = detection_result.get("damages", [])

        # Generate annotated image with bounding boxes
        annotated_filename = f"{file_id}_annotated.jpg"
        annotated_path = OUTPUT_DIR / annotated_filename

        image_processor.annotate_image(original_path, annotated_path, damages)

        # Calculate damage summary statistics
        summary = _calculate_summary(damages)

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
        # Clean up uploaded file on error
        if original_path.exists():
            original_path.unlink()

        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing image: {str(e)}"
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
