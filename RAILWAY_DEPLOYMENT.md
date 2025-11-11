# Railway Deployment Guide

This guide will help you deploy RoofScan AI to Railway with both backend and frontend services.

## Prerequisites

1. Railway account (sign up at https://railway.app)
2. Railway CLI installed (optional but recommended)
3. OpenAI API key

## Deployment Steps

### Option 1: Deploy via Railway Dashboard (Recommended)

#### 1. Create New Project
1. Go to https://railway.app/new
2. Click "Deploy from GitHub repo"
3. Connect your GitHub account and select this repository

#### 2. Deploy Backend Service
1. Railway will auto-detect the backend
2. Add environment variables:
   - `OPENAI_API_KEY`: Your OpenAI API key (from https://platform.openai.com/api-keys)
3. Railway will use the `backend/railway.toml` configuration
4. Backend will deploy on a Railway-provided domain

#### 3. Deploy Frontend Service
1. Click "New Service" in your Railway project
2. Select "From GitHub repo" → same repository
3. Change the Root Directory to `frontend`
4. Add environment variable:
   - `VITE_API_URL`: The backend service URL (e.g., `https://your-backend.up.railway.app`)
5. Railway will use the `frontend/railway.toml` configuration
6. Frontend will deploy on a Railway-provided domain

### Option 2: Deploy via Railway CLI

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login to Railway
railway login

# Create new project
railway init

# Deploy backend
cd backend
railway up

# Set environment variables
railway variables set OPENAI_API_KEY=your_openai_api_key_here

# Deploy frontend (in a new terminal/service)
cd ../frontend
railway up

# Set frontend environment variable
railway variables set VITE_API_URL=https://your-backend-url.up.railway.app
```

## Environment Variables

### Backend (`backend` service)
- `OPENAI_API_KEY` (required): Your OpenAI API key
- `PORT` (auto-set by Railway): The port the backend will run on

### Frontend (`frontend` service)
- `VITE_API_URL` (required): Full URL to your backend service (including https://)
- `PORT` (auto-set by Railway): The port the frontend will run on

## Configuration Files

Both services use Railway's modern **RAILPACK** builder:

- `backend/railway.toml` - Backend configuration
- `frontend/railway.toml` - Frontend configuration

## Post-Deployment

1. **Test the backend**: Visit `https://your-backend.up.railway.app/` - should return `{"message": "RoofScan AI API", "status": "running"}`

2. **Test the frontend**: Visit `https://your-frontend.up.railway.app/` - you should see the upload interface

3. **Upload a roof image** to test the full flow

## Troubleshooting

### Backend issues:
- Check logs: `railway logs` in backend directory
- Verify `OPENAI_API_KEY` is set correctly
- Ensure `pyproject.toml` lists all dependencies

### Frontend issues:
- Check logs: `railway logs` in frontend directory
- Verify `VITE_API_URL` points to the correct backend URL
- Make sure the API URL includes `https://` and has no trailing slash

### CORS issues:
- The backend is configured to accept requests from any origin
- If you see CORS errors, check that the frontend is using the correct backend URL

## Costs

Railway offers:
- Free tier with $5/month credit
- Usage-based pricing after free tier
- This app should run comfortably within the free tier for development/testing

## Custom Domains

To use custom domains:
1. Go to your service in Railway dashboard
2. Click "Settings" → "Domains"
3. Add your custom domain
4. Update DNS records as instructed
5. Update `VITE_API_URL` in frontend if you use a custom domain for backend
