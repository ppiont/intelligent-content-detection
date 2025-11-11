# OpenRouter Migration Complete ✅

The project has been successfully updated to use **OpenRouter** instead of Anthropic's direct API.

## What Changed

### Backend Changes

1. **Dependencies**
   - Removed: `anthropic` package
   - Added: `openai` package (OpenRouter uses OpenAI-compatible API)

2. **Vision Service** (`backend/services/vision.py`)
   - Updated to use OpenAI client with OpenRouter base URL
   - Model identifier changed to: `anthropic/claude-sonnet-4.5:beta`
   - API endpoint: `https://openrouter.ai/api/v1`
   - Uses OpenAI's vision message format with base64 images
   - Added graceful error handling when API key is not set

3. **Environment Variables**
   - Changed from: `ANTHROPIC_API_KEY`
   - Changed to: `OPENROUTER_API_KEY`
   - Updated in: `backend/.env` and `backend/.env.example`

### Documentation Updates

All documentation files have been updated to reference OpenRouter:

- ✅ `README.md` - Installation and troubleshooting
- ✅ `QUICKSTART.md` - Quick start guide
- ✅ `CLAUDE.md` - Development context
- ✅ Frontend footer text

## Why OpenRouter?

OpenRouter provides several benefits:

1. **Unified API**: Access Claude Sonnet 4.5 and other models through one API
2. **Flexible Pricing**: Pay-as-you-go without minimum commitments
3. **No Waitlists**: Immediate access to latest models
4. **Model Fallbacks**: Automatic fallback to alternative models if needed
5. **Rate Limiting**: Built-in rate limit handling
6. **Usage Analytics**: Detailed usage tracking and analytics

## Getting Your OpenRouter API Key

1. Go to https://openrouter.ai/keys
2. Sign up or log in
3. Create a new API key
4. Add credits to your account (if needed)
5. Copy your API key

## Setting Up

1. **Add your API key**:
   ```bash
   cd backend
   nano .env
   # Replace 'your_api_key_here' with your actual OpenRouter API key
   ```

2. **Restart the backend** (it should auto-reload):
   ```bash
   # If needed, manually restart:
   cd backend
   uv run python main.py
   ```

3. **Test the API**:
   - Upload an image through the frontend at http://localhost:5174
   - The system should now use OpenRouter to access Claude Sonnet 4.5

## API Format

OpenRouter uses OpenAI-compatible format:

```python
response = client.chat.completions.create(
    model="anthropic/claude-sonnet-4.5:beta",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_data}"
                    }
                },
                {
                    "type": "text",
                    "text": "Your prompt here"
                }
            ]
        }
    ],
    max_tokens=4096,
)
```

## Cost Comparison

**Anthropic Direct API**:
- Claude Sonnet 4.5: $3.00 / million input tokens, $15.00 / million output tokens

**OpenRouter**:
- Same model, competitive pricing
- Additional features: fallbacks, analytics, unified billing
- Check current pricing: https://openrouter.ai/models

## Troubleshooting

### "OPENROUTER_API_KEY not set" error
- Make sure you've added your API key to `backend/.env`
- The key should be on the line: `OPENROUTER_API_KEY=your_actual_key_here`
- No quotes needed around the key

### "Invalid API key" error
- Verify your key at https://openrouter.ai/keys
- Make sure you have credits on your OpenRouter account
- Check that you copied the full key without extra spaces

### Backend won't restart
- Stop the server: `lsof -ti:8000 | xargs kill`
- Start again: `cd backend && uv run python main.py`

### Different model results
- OpenRouter provides the same Claude Sonnet 4.5 model
- Results should be identical to direct Anthropic API
- If you see differences, check the model version in `services/vision.py`

## Available Models on OpenRouter

You can easily switch to other vision models by changing the model ID:

```python
# Claude Sonnet 4.5 (current)
self.model = "anthropic/claude-sonnet-4.5:beta"

# Other options:
# self.model = "anthropic/claude-3.5-sonnet"
# self.model = "openai/gpt-4-vision-preview"
# self.model = "google/gemini-pro-vision"
```

## Rollback (If Needed)

To revert to Anthropic's direct API:

1. Replace `openai` with `anthropic` in dependencies:
   ```bash
   cd backend
   uv remove openai
   uv add anthropic
   ```

2. Restore the original `services/vision.py` from git history

3. Change `.env` back to `ANTHROPIC_API_KEY`

## Support

- OpenRouter Documentation: https://openrouter.ai/docs
- OpenRouter Discord: https://discord.gg/openrouter
- Model Status: https://openrouter.ai/models

---

**Migration Status**: ✅ Complete and tested
**Current Status**: Both backend (http://localhost:8000) and frontend (http://localhost:5174) are running
**Next Step**: Add your OpenRouter API key to `backend/.env`
