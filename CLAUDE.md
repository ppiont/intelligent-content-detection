# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**RoofScan AI Prototype** - An AI-powered roof damage detection system for automated insurance claim processing. The system analyzes roof photos using Vision LLMs, highlights damage areas with bounding boxes, and generates structured PDF reports.

## Architecture

This is a web application with three main components:

### 1. Backend API (FastAPI)
- **Main Endpoint**: `POST /api/analyze` - accepts roof images, returns damage analysis
- **Vision LLM Integration**: Uses Claude Sonnet 4.5 via OpenRouter for damage detection
- **Image Processing Pipeline**:
  1. Receive uploaded image via multipart/form-data
  2. Convert to base64 and send to Vision LLM with structured prompt
  3. Parse JSON response containing damage objects with bounding boxes (percentage coordinates)
  4. Draw bounding boxes and labels on copy of original image using PIL
  5. Return JSON with damages array, summary statistics, and URLs to original/annotated images
- **Report Generation**: PDF creation using ReportLab or WeasyPrint
- **Storage**: Local filesystem (`/uploads` for originals, `/outputs` for annotated)

### 2. Frontend Application
- **Upload Component**: Drag-and-drop interface for roof images (JPG/PNG, max 10MB)
- **Results Display**: Three-panel layout showing original image, annotated image with damage overlays, and damage summary table
- **Report Download**: Trigger PDF generation and download

### 3. Core Data Flow
```
User uploads image → Backend saves to /uploads
                   → Convert to base64 → Vision LLM API call
                   → Parse JSON response with damages array
                   → Draw bounding boxes (color-coded by severity)
                   → Save annotated image to /outputs
                   → Return analysis results to frontend
                   → User triggers PDF report generation
```

## Damage Detection Model

### Damage Object Structure
```json
{
  "type": "hail_impact | wind_damage | missing_shingles | cracked_shingles | torn_underlayment",
  "severity": "minor | moderate | severe",
  "bbox": [x1, y1, x2, y2],  // percentages (0-100), top-left origin
  "confidence": 0.0-1.0,
  "description": "Optional text description"
}
```

### Severity Color Coding
- **Minor**: Yellow (rgba with 0.2 alpha for fill)
- **Moderate**: Orange (rgba with 0.2 alpha for fill)
- **Severe**: Red (rgba with 0.2 alpha for fill)
- Bounding box line width: 3px

### Vision LLM Prompt Structure
The prompt in PRD.md:246-275 defines the exact format for Vision LLM requests. Key elements:
- Damage types to detect (5 categories)
- Severity assessment criteria
- Bounding box coordinate format (percentage-based)
- Confidence scoring
- Strict JSON response format requirement

## Build Order and Dependencies

Follow this implementation sequence (from PRD.md:365-383):

1. **Phase 1 + 6.1-6.3**: Core detection backend (FastAPI server, Vision LLM integration, JSON parsing)
2. **Phase 2 + 6.4**: Visual annotation (bounding box overlay using PIL)
3. **Phase 3**: Results presentation (damage summary and details table)
4. **Phase 7**: Frontend UI (upload component, results display, API communication)
5. **Phase 4 + 6.5**: Report generation (PDF creation with ReportLab/WeasyPrint)
6. **Phase 5**: Error handling and polish

Each phase completion produces independently testable output.

## Technology Stack

### Backend
- Python 3.10+
- FastAPI (API framework)
- OpenAI SDK (for OpenRouter API access)
- Pillow (PIL) for image manipulation
- ReportLab for PDF generation
- OpenRouter (unified API for Claude Sonnet 4.5)

### Frontend
- HTML/CSS/JavaScript (vanilla or React - not yet determined)
- Async fetch for API communication
- Responsive design (mobile/tablet support)

## Key Implementation Notes

### Coordinate Conversion
Vision LLM returns percentage-based bounding boxes. Convert to pixel coordinates:
```python
pixel_x = (percentage_x / 100) * image_width
pixel_y = (percentage_y / 100) * image_height
```

### Error Handling Priorities
- API retry logic (max 3 attempts) for OpenRouter/Vision LLM failures
- File type validation (prevent code execution)
- Malformed JSON response handling
- Network timeout graceful degradation
- Clear user-facing error messages for all failure modes

### Image Storage Pattern
- Generate unique filenames using UUID
- Save originals to `/uploads/<uuid>.<ext>`
- Save annotated to `/outputs/<uuid>_annotated.jpg`
- Serve via FastAPI static file routes

### Performance Targets
- Vision LLM API response: < 10 seconds
- Image processing (bbox overlay): < 1 second
- PDF generation: < 2 seconds
- Total end-to-end: < 15 seconds

## Testing Approach

Manual testing checklist (PRD.md:395-402):
- Valid roof image upload and analysis
- Non-roof image handling
- Corrupted file error handling
- API timeout retry behavior
- Zero damage detection scenario
- Multiple damage detection
- PDF report generation and accuracy

Test image requirements: Need 5-10 sample roof photos showing hail damage, missing shingles, wind damage, multiple damage types, and clean roofs (negative cases).

## Out of Scope for Prototype

The PRD explicitly excludes (PRD.md:330-341):
- User authentication
- Database/persistent storage
- Batch processing multiple images
- Manual editing of AI results
- Insurance company API integration
- Mobile app
- Custom model training
- Cost estimation features

## API Response Format

```json
{
  "damages": [Damage, ...],
  "summary": {
    "total_damages": integer,
    "by_type": {"type": count, ...},
    "by_severity": {"severity": count, ...}
  },
  "annotated_image_url": "string",
  "original_image_url": "string"
}
```

## Report Structure

PDF sections (PRD.md:113-119):
1. Header with title and timestamp
2. Executive Summary (total damages, severity breakdown)
3. Full-size annotated photo
4. Detailed damage table
5. Recommendations based on severity levels

Filename format: `roof_damage_report_YYYYMMDD_HHMMSS.pdf`
