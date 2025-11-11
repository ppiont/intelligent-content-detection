import base64
import json
import os
from typing import List, Dict, Any
from pathlib import Path

from openai import OpenAI


class VisionService:
    """Service for detecting roof damage using OpenAI GPT-4 Vision."""

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY") or "not-set"
        self.client = OpenAI(api_key=api_key)
        # Using latest GPT-4o with vision capabilities
        self.model = "gpt-4o-2024-11-20"  # Latest GPT-4o model
        self.max_retries = 3

    def _encode_image(self, image_path: Path) -> str:
        """Encode image to base64 string."""
        with open(image_path, "rb") as image_file:
            return base64.standard_b64encode(image_file.read()).decode("utf-8")

    def _get_prompt(self) -> str:
        """Get the structured prompt for roof damage detection."""
        return """You are an expert roof inspector analyzing this photograph for damage.

DAMAGE TYPES TO IDENTIFY:
- missing_shingles: Areas where shingles are completely absent, exposing underlayment or wood
- cracked_shingles: Visible cracks, splits, or fractures in shingles
- hail_damage: Circular dents, bruising, or impact marks on shingles
- wind_damage: Lifted, curled, or partially blown-off shingle sections
- torn_underlayment: Rips or tears in the protective membrane beneath shingles

SEVERITY ASSESSMENT:
- minor: Small cosmetic damage, no immediate risk
- moderate: Functional damage that needs repair soon
- severe: Major damage requiring immediate attention to prevent water infiltration

CRITICAL: BOUNDING BOX INSTRUCTIONS
You MUST provide accurate bounding boxes that FULLY ENCOMPASS each damaged area.

Coordinate system: [x1, y1, x2, y2] as PERCENTAGES (0-100 scale)
- x1, y1 = top-left corner (percentage from top-left of image)
- x2, y2 = bottom-right corner (percentage from top-left of image)
- (0, 0) is the TOP-LEFT of the image
- (100, 100) is the BOTTOM-RIGHT of the image

EXAMPLES:
- Damage in center covering 20% of image width and 15% height:
  bbox = [40, 42.5, 60, 57.5]

- Large hole in upper right quadrant:
  bbox = [55, 15, 85, 45]

- Missing shingles along left edge:
  bbox = [5, 30, 25, 60]

IMPORTANT: Draw boxes that are GENEROUS - slightly larger than the damage to ensure full coverage.
If damage spans a large area (like a big hole), the box should be proportionally large (e.g., 20-40% of image dimensions).

Return ONLY valid JSON with NO markdown formatting:
{
  "damages": [
    {
      "type": "missing_shingles|cracked_shingles|hail_damage|wind_damage|torn_underlayment",
      "severity": "minor|moderate|severe",
      "bbox": [x1, y1, x2, y2],
      "confidence": 0.0-1.0,
      "description": "brief description of what you see"
    }
  ]
}

If no damage visible, return: {"damages": []}"""

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """Parse JSON from LLM response, handling markdown code blocks."""
        # Remove markdown code blocks if present
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON response: {e}\nResponse: {text}")

    async def detect_damage(self, image_path: Path) -> Dict[str, Any]:
        """
        Detect roof damage in an image using OpenAI GPT-4 Vision.

        Args:
            image_path: Path to the image file

        Returns:
            Dictionary containing detected damages

        Raises:
            Exception: If API call fails after max retries
        """
        # Check if API key is set
        if self.client.api_key == "not-set":
            raise Exception(
                "OPENAI_API_KEY not set. Please add your OpenAI API key to backend/.env file. "
                "Get your key from: https://platform.openai.com/api-keys"
            )

        # Encode image
        image_data = self._encode_image(image_path)

        # Determine media type based on file extension
        file_ext = image_path.suffix.lower()
        media_type = "image/jpeg" if file_ext in [".jpg", ".jpeg"] else "image/png"

        # Retry logic
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                # Call OpenRouter API (OpenAI-compatible format)
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{media_type};base64,{image_data}"
                                    }
                                },
                                {
                                    "type": "text",
                                    "text": self._get_prompt()
                                }
                            ]
                        }
                    ],
                    max_tokens=3000,
                )

                # Extract text response
                response_text = response.choices[0].message.content

                # Parse JSON response
                result = self._parse_json_response(response_text)

                # Validate structure
                if "damages" not in result:
                    raise ValueError("Response missing 'damages' field")

                return result

            except Exception as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    continue

        # If we get here, all retries failed
        raise Exception(f"Failed to detect damage after {self.max_retries} attempts: {last_exception}")


# Global instance
vision_service = VisionService()
