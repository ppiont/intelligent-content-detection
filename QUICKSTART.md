# RoofScan AI - Quick Start Guide

## Current Status: ✅ READY TO USE

Both backend and frontend servers are currently running!

- **Backend**: http://localhost:8000
- **Frontend**: http://localhost:5174

## ⚠️ IMPORTANT: Set Your API Key

Before you can analyze images, you need to add your OpenRouter API key:

1. Open `backend/.env`
2. Replace `your_api_key_here` with your actual OpenRouter API key
3. Get your key from: https://openrouter.ai/keys

The backend server will automatically reload when you save the .env file.

**Why OpenRouter?** OpenRouter provides unified access to Claude Sonnet 4.5 and other models with flexible pricing and no waitlists.

## How to Use

1. **Open the Application**
   - Navigate to http://localhost:5174 in your browser

2. **Upload a Roof Image**
   - Drag and drop a roof photo into the upload zone
   - Or click to browse and select a file
   - Supported formats: JPG, PNG (max 10MB)

3. **Wait for Analysis**
   - The system will analyze the image using Claude Sonnet 4.5 Vision
   - This typically takes 3-10 seconds

4. **Review Results**
   - View the original and annotated images side-by-side
   - Check the damage summary statistics
   - Review the detailed damage table

5. **Generate Report**
   - Click "Generate PDF Report" to download a professional report
   - The PDF includes all damage details and is ready for insurance submission

## Testing the System

If you don't have roof images handy, you can:

1. Search for "damaged roof photos" online
2. Look for images showing:
   - Hail damage
   - Missing shingles
   - Wind damage
   - Cracked shingles

3. Download a few test images and try uploading them

## Stopping the Servers

When you're done testing:

```bash
# Find and kill the backend server
lsof -ti:8000 | xargs kill

# Find and kill the frontend server
lsof -ti:5174 | xargs kill
```

## Restarting Later

To restart the servers:

```bash
# Terminal 1 - Backend
cd backend
uv run python main.py

# Terminal 2 - Frontend
cd frontend
bun dev
```

## Troubleshooting

### "Error analyzing image" or API errors
- Make sure you've set your `OPENROUTER_API_KEY` in `backend/.env`
- Check that your API key is valid at https://openrouter.ai/keys
- Verify you have credits available on your OpenRouter account
- Check OpenRouter's status page if you're getting persistent errors

### Frontend can't connect to backend
- Make sure both servers are running
- Check that backend is on port 8000
- Check browser console for CORS errors

### Image won't upload
- Verify the file is JPG or PNG format
- Check file size is under 10MB
- Make sure the `uploads/` directory exists

## Next Steps

1. **Add Your API Key** (if not done yet)
2. **Test with Sample Images**
3. **Review the PRD.md** for full feature specifications
4. **Check CLAUDE.md** for development guidance
5. **Read README.md** for detailed documentation

## Architecture Overview

```
User uploads image
    ↓
FastAPI receives and validates file
    ↓
OpenRouter → Claude Sonnet 4.5 Vision analyzes image
    ↓
Image processor draws bounding boxes
    ↓
Results sent to frontend
    ↓
User reviews and generates PDF report
```

## API Documentation

Visit http://localhost:8000/docs for interactive API documentation (Swagger UI).

## Need Help?

- Check the README.md for detailed documentation
- Review the PRD.md for product requirements
- Check CLAUDE.md for development context
- Open an issue on GitHub

---

**Status**: MVP Prototype - Ready for demonstration and testing
