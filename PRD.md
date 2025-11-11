# Product Requirements Document (PRD)
## Roof Damage Detection Prototype

**Product Name**: RoofScan AI Prototype  
**Target Use Case**: Automated roof damage detection for insurance claims  
**Scope**: Minimal Viable Prototype (MVP)

---

## 1. Product Overview

### Purpose
A working prototype that demonstrates AI-powered roof damage detection. Users upload photos of roofs, and the system automatically identifies damage, highlights problem areas, and generates a structured insurance report.

### Core Value Proposition
Transform manual roof inspection documentation into automated, structured data in seconds.

---

## 2. User Personas

**Primary User: Sam the Contractor**
- Takes 20-50 roof photos per job
- Needs to submit insurance claims quickly
- Currently manually reviews photos and writes damage descriptions
- Success = cuts claim prep time from 2 hours to 15 minutes

---

## 3. User Stories

### Must Have (P0)
1. **As a contractor**, I want to upload a roof photo so that I can get automated damage analysis
2. **As a contractor**, I want to see damage highlighted on my photo so that I can verify the AI found the right areas
3. **As a contractor**, I want damage categorized by type so that I know what to report to insurance
4. **As a contractor**, I want a downloadable report so that I can attach it to my insurance claim

### Nice to Have (P1)
5. **As a contractor**, I want to upload multiple photos at once so that I can process a full job faster
6. **As a contractor**, I want to edit AI results so that I can correct mistakes before generating the report

---

## 4. Functional Requirements

### Phase 1: Core Detection Engine

**Feature 1.1: Image Upload**
- User can select a single image file (JPG, PNG)
- Max file size: 10MB
- Image displays in preview area after selection
- Clear error message if file type or size is invalid

**Feature 1.2: Damage Detection API**
- Send image to Vision LLM (Claude 3.5 Sonnet or GPT-4 Vision)
- Structured prompt requesting:
  - Damage types: hail impact, wind damage, missing shingles, cracked shingles, torn underlayment
  - Severity levels: minor, moderate, severe
  - Bounding box coordinates (percentage-based: x1, y1, x2, y2)
  - Confidence score (0-1)
- Return JSON response with array of detected damages

**Feature 1.3: Response Parsing**
- Parse JSON from Vision LLM
- Validate structure (required fields present)
- Handle malformed responses gracefully
- Convert percentage coordinates to pixel coordinates based on image dimensions

---

### Phase 2: Visual Annotation

**Feature 2.1: Bounding Box Overlay**
- Draw rectangles on image at detected damage locations
- Color code by severity:
  - Minor: Yellow
  - Moderate: Orange  
  - Severe: Red
- Box line width: 3px
- Semi-transparent fill (alpha 0.2) inside boxes

**Feature 2.2: Damage Labels**
- Display damage type text above each bounding box
- Include severity in label (e.g., "Hail Impact - Moderate")
- White text with dark background for readability
- Font size scales with image size

**Feature 2.3: Annotated Image Display**
- Show original image with overlays in UI
- Allow user to zoom in on specific areas
- Provide side-by-side view: original vs annotated

---

### Phase 3: Results Presentation

**Feature 3.1: Damage Summary Panel**
- Display list of all detected damages
- Show count by damage type
- Show count by severity level
- Calculate total damaged areas

**Feature 3.2: Damage Details Table**
- One row per detected damage
- Columns: Type, Severity, Confidence, Location Description
- Location description derived from bounding box position (e.g., "Upper left quadrant", "Center-right section")
- Sortable by any column

---

### Phase 4: Report Generation

**Feature 4.1: PDF Report Structure**
- Header: "Roof Damage Assessment Report"
- Date and timestamp
- Section 1: Executive Summary (total damages, severity breakdown)
- Section 2: Annotated photo (full size)
- Section 3: Detailed damage table
- Section 4: Recommendations based on severity

**Feature 4.2: Report Download**
- Generate PDF on demand when user clicks "Generate Report"
- Download starts automatically
- File name format: `roof_damage_report_YYYYMMDD_HHMMSS.pdf`

---

### Phase 5: User Interface

**Feature 5.1: Landing Page**
- Simple hero section explaining what the tool does
- Clear call-to-action: "Upload Roof Photo"
- Upload button/dropzone prominently displayed

**Feature 5.2: Analysis Page**
- Progress indicator while processing
- Three-panel layout:
  - Left: Original image
  - Center: Annotated image
  - Right: Damage summary
- "Generate Report" button at bottom

**Feature 5.3: Loading States**
- Show spinner during API call
- Display estimated time: "Analyzing... typically takes 3-5 seconds"
- Disable upload button while processing

**Feature 5.4: Error Handling**
- Clear error messages for:
  - API failures
  - Invalid images
  - No damage detected
  - Network timeouts
- Ability to retry failed operations

---

## 5. Technical Architecture

### Phase 6: Backend API

**Feature 6.1: FastAPI Server**
- POST `/api/analyze` endpoint
- Accepts multipart/form-data with image file
- Returns JSON with damages array and annotated image URL

**Feature 6.2: Image Storage**
- Save uploaded images to `/uploads` directory
- Save annotated images to `/outputs` directory
- Generate unique filenames using UUID
- Serve images via static file route

**Feature 6.3: Vision LLM Integration**
- Abstract API call into separate service module
- Convert image to base64 for API request
- Send prompt with image
- Parse JSON from text response (handle markdown code blocks)
- Implement retry logic (max 3 attempts) for API failures

**Feature 6.4: Image Processing**
- Use PIL (Pillow) for image manipulation
- Draw bounding boxes on copy of original image
- Add text labels with background boxes
- Save annotated image as JPG (quality 90)

**Feature 6.5: Report Generation**
- Use ReportLab or WeasyPrint for PDF creation
- Template-based approach
- Embed annotated image
- Format table with proper styling

---

### Phase 7: Frontend Application

**Feature 7.1: File Upload Component**
- Drag-and-drop zone
- Click to browse fallback
- Image preview after selection
- Clear/reset button

**Feature 7.2: Results Display Component**
- Image viewer with zoom controls
- Collapsible damage list
- Responsive layout (works on tablet/mobile)

**Feature 7.3: API Communication**
- Async fetch requests to backend
- Loading state management
- Error boundary for graceful failures

---

## 6. Data Models

### Damage Object
```json
{
  "type": "hail_impact | wind_damage | missing_shingles | cracked_shingles | torn_underlayment",
  "severity": "minor | moderate | severe",
  "bbox": [x1, y1, x2, y2],  // percentages (0-100)
  "confidence": 0.0-1.0,
  "description": "Optional text description"
}
```

### API Response
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

---

## 7. Vision LLM Prompt Template

```
You are analyzing a photograph of a roof for damage. 

Identify and locate all visible damage in this image. Focus on:
- Hail impact (circular dents, bruising)
- Wind damage (lifted/blown-off sections)
- Missing shingles (exposed underlayment)
- Cracked shingles (visible splits)
- Torn underlayment (rips in protective layer)

For each damage area found:
1. Classify the damage type
2. Assess severity: minor (cosmetic), moderate (functional impact), severe (immediate repair needed)
3. Provide bounding box coordinates as percentages [x1, y1, x2, y2] where (0,0) is top-left
4. Rate your confidence (0.0 to 1.0)

Return ONLY valid JSON in this exact format:
{
  "damages": [
    {
      "type": "damage_type",
      "severity": "minor|moderate|severe",
      "bbox": [x1, y1, x2, y2],
      "confidence": 0.0-1.0,
      "description": "brief description"
    }
  ]
}

If no damage is detected, return: {"damages": []}
```

---

## 8. Non-Functional Requirements

### Performance
- API response time: < 10 seconds per image
- Image processing (bbox overlay): < 1 second
- PDF generation: < 2 seconds
- Frontend load time: < 2 seconds

### Reliability
- API retry logic for transient failures
- Graceful degradation if Vision LLM is unavailable
- No data loss on processing errors

### Usability
- Zero-training required (intuitive UI)
- Mobile-responsive design
- Accessible color contrast ratios

### Security
- No authentication required (prototype)
- File type validation to prevent code execution
- No persistent storage of user data

---

## 9. Success Criteria

### Phase 1-2 Success Criteria
✅ Can upload roof image and receive damage detections  
✅ Damages are highlighted with bounding boxes on image  
✅ At least 3 different damage types can be detected

### Phase 3-4 Success Criteria
✅ Damage summary displays accurate counts  
✅ PDF report generates and downloads successfully  
✅ Report contains all detected damage details

### Phase 5-7 Success Criteria
✅ End-to-end workflow works without errors  
✅ UI is intuitive (no documentation needed to use)  
✅ Processing time is acceptable (< 15 seconds total)

### Demo Success Criteria
✅ Can demonstrate on 3 different roof photos  
✅ Shows variety of damage types detected  
✅ Generates professional-looking report  
✅ Clearly communicates business value

---

## 10. Out of Scope

### Explicitly NOT included in prototype:
- User authentication or accounts
- Database/persistent storage
- Multiple image batch processing
- Manual editing of detected damages
- Integration with insurance company APIs
- Mobile app (web only)
- Real-time camera capture
- Training custom models
- Cost estimation or material recommendations
- Historical analysis or trend detection

---

## 11. Dependencies

### External Services
- Vision LLM API (Claude 3.5 Sonnet or GPT-4 Vision)
- API key provisioned and working

### Technology Stack
- **Backend**: Python 3.10+, FastAPI, Pillow, ReportLab
- **Frontend**: HTML/CSS/JavaScript (vanilla or React)
- **Deployment**: Local development server (no production hosting)

### Test Data
- 5-10 sample roof photos showing various damage types
- Mix of clear damage and ambiguous cases

---

## 12. Phase Dependencies

### Logical Build Order
```
Phase 1 (Core Detection) 
  ↓
Phase 6.1-6.3 (Backend API + Vision Integration)
  ↓
Phase 2 (Visual Annotation)
  ↓
Phase 6.4 (Image Processing)
  ↓
Phase 3 (Results Presentation)
  ↓
Phase 7 (Frontend)
  ↓
Phase 4 (Report Generation)
  ↓
Phase 6.5 (Report Service)
  ↓
Phase 5 (Polish & Error Handling)
```

**Atomic Unit Sizes:**
- Each feature can be built independently within its phase
- Each phase completion produces testable output
- No circular dependencies between phases

---

## 13. Testing Strategy

### Manual Testing Checklist
- [ ] Upload valid roof image → See results
- [ ] Upload non-roof image → Handle gracefully
- [ ] Upload corrupted file → Show error message
- [ ] API timeout → Retry and show loading state
- [ ] No damage detected → Clear message to user
- [ ] Multiple damages → All shown in table and on image
- [ ] Generate report → PDF downloads correctly
- [ ] Report accuracy → Matches what's shown in UI

### Test Images Needed
1. Roof with obvious hail damage
2. Roof with missing shingles
3. Roof with wind damage
4. Roof with multiple damage types
5. Clean roof (no damage) - negative test case

---

## 14. Deployment

### Prototype Environment
- Local development server
- No cloud hosting required
- Access via `localhost:8000` or similar

### Demo Setup
- Backend server running
- Frontend served (can be static files)
- 3-5 test images ready in demo folder
- Rehearsed narrative explaining each step

---

This PRD is complete, atomic, and ready to build. Each phase builds logically on the previous phase, and each feature within a phase can be implemented independently.