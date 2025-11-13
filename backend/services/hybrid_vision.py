import os
import json
import base64
from pathlib import Path
from typing import Dict, Any, List

from openai import OpenAI
from services.roboflow_vision import roboflow_vision_service


class HybridVisionService:
    """
    Hybrid service that combines:
    1. Roboflow YOLOv11 for fast, accurate damage detection
    2. OpenAI GPT-4o for severity assessment and reasoning

    This provides the best of both worlds:
    - Precise bounding boxes from trained YOLO model
    - Intelligent severity analysis and contextual reasoning from LLM
    """

    def __init__(self):
        # Initialize OpenAI for reasoning
        api_key = os.getenv("OPENAI_API_KEY") or "not-set"
        self.llm_client = OpenAI(api_key=api_key)
        self.llm_model = "gpt-4o-2024-11-20"

    def _encode_image(self, image_path: Path) -> str:
        """Encode image to base64 string."""
        with open(image_path, "rb") as image_file:
            return base64.standard_b64encode(image_file.read()).decode("utf-8")

    def _create_reasoning_prompt(self, yolo_detections: List[Dict[str, Any]]) -> str:
        """
        Create a prompt for the LLM to reason about YOLO detections.

        The LLM will assess severity based on:
        - Number of damages
        - Size/area of damage (from bounding boxes)
        - Confidence scores
        - Spatial distribution
        """
        prompt = f"""You are an expert roof inspector analyzing this roof photograph for damage.

I have identified {len(yolo_detections)} areas of potential damage in this image (numbered 0 to {len(yolo_detections)-1}).

For each damaged area, provide:
1. **Type**: Classify the specific damage type you observe:
   - missing_shingles: Complete absence of shingles
   - cracked_shingles: Visible cracks or splits
   - hail_damage: Circular dents or bruising
   - wind_damage: Lifted or curled shingles
   - torn_underlayment: Tears in protective layer
   - damaged_shingles: General shingle damage

2. **Severity**: Rate as minor, moderate, or severe based on what you see

3. **Description**: Describe the damage as if you're writing an inspection report. Be specific about what you observe.
   Examples: "Large area of missing shingles exposing underlayment", "Small crack in shingle corner", "Multiple circular impact marks on shingle surface"

4. **Assessment**: Brief reasoning for your severity rating and confidence level (high/medium/low)

Return a JSON response in this exact format:
{{
  "enhanced_damages": [
    {{
      "original_index": 0,
      "type": "damage_type",
      "severity": "minor|moderate|severe",
      "description": "What you observe in this damaged area",
      "severity_reasoning": "Why you assigned this severity",
      "confidence_assessment": "high|medium|low and brief reason"
    }}
  ],
  "overall_assessment": {{
    "severity": "minor|moderate|severe",
    "reasoning": "Overall roof condition assessment",
    "immediate_action_needed": true|false,
    "confidence": "high|medium|low"
  }}
}}

Return ONLY valid JSON with NO markdown formatting."""
        return prompt

    async def detect_damage(self, image_path: Path) -> Dict[str, Any]:
        """
        Hybrid detection pipeline:
        1. Run YOLO for precise damage detection
        2. Use LLM for severity reasoning and classification refinement

        Args:
            image_path: Path to the image file

        Returns:
            Dict with enhanced damages including LLM reasoning
        """
        print(f"[DEBUG] Starting hybrid detection on: {image_path}")

        # Step 1: Run YOLO detection
        print("[DEBUG] Step 1: Running YOLOv11 detection...")
        yolo_result = roboflow_vision_service.detect_damage(image_path)
        yolo_damages = yolo_result.get("damages", [])

        print(f"[DEBUG] YOLO detected {len(yolo_damages)} damages")

        # If no damages detected, return early
        if not yolo_damages:
            return {
                "damages": [],
                "summary": {
                    "total_damages": 0,
                    "by_type": {},
                    "by_severity": {}
                },
                "reasoning": "No damage detected by YOLO model"
            }

        # Step 2: Use LLM for reasoning (with image)
        print("[DEBUG] Step 2: Running LLM reasoning with image...")
        llm_enhancement = await self._run_llm_reasoning(yolo_damages, image_path)

        # Step 3: Merge YOLO detections with LLM reasoning
        print("[DEBUG] Step 3: Merging YOLO + LLM results...")
        enhanced_damages = self._merge_detections(yolo_damages, llm_enhancement)

        # Step 4: Calculate final summary
        summary = self._calculate_summary(enhanced_damages)

        return {
            "damages": enhanced_damages,
            "summary": summary,
            "reasoning": llm_enhancement.get("overall_assessment", {}).get("reasoning", ""),
            "confidence": llm_enhancement.get("overall_assessment", {}).get("confidence", "medium")
        }

    async def _run_llm_reasoning(self, yolo_damages: List[Dict[str, Any]], image_path: Path) -> Dict[str, Any]:
        """Run LLM reasoning on YOLO detections with image context."""
        # Check if API key is set
        if self.llm_client.api_key == "not-set":
            print("[WARNING] OPENAI_API_KEY not set, skipping LLM reasoning")
            return {
                "enhanced_damages": [],
                "overall_assessment": {
                    "severity": "unknown",
                    "reasoning": "LLM reasoning skipped (no API key)",
                    "immediate_action_needed": False,
                    "confidence": "low"
                }
            }

        try:
            # Encode image
            image_data = self._encode_image(image_path)
            file_ext = image_path.suffix.lower()
            media_type = "image/jpeg" if file_ext in [".jpg", ".jpeg"] else "image/png"

            prompt = self._create_reasoning_prompt(yolo_damages)

            response = self.llm_client.chat.completions.create(
                model=self.llm_model,
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
                                "text": prompt
                            }
                        ]
                    }
                ],
                max_tokens=2000,
            )

            response_text = response.choices[0].message.content

            # Parse JSON response
            result = self._parse_json_response(response_text)
            return result

        except Exception as e:
            print(f"[WARNING] LLM reasoning failed: {e}")
            return {
                "enhanced_damages": [],
                "overall_assessment": {
                    "severity": "unknown",
                    "reasoning": f"LLM reasoning failed: {str(e)}",
                    "immediate_action_needed": False,
                    "confidence": "low"
                }
            }

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """Parse JSON from LLM response, handling markdown code blocks."""
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
            print(f"[ERROR] Failed to parse LLM JSON: {e}")
            print(f"[ERROR] Response text: {text}")
            return {
                "enhanced_damages": [],
                "overall_assessment": {
                    "severity": "unknown",
                    "reasoning": "Failed to parse LLM response",
                    "immediate_action_needed": False,
                    "confidence": "low"
                }
            }

    def _merge_detections(
        self,
        yolo_damages: List[Dict[str, Any]],
        llm_enhancement: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Merge YOLO detections with LLM reasoning.
        Keep YOLO's bounding boxes and confidence, enhance with LLM's reasoning.
        """
        enhanced_damages_list = llm_enhancement.get("enhanced_damages", [])

        # Create a map of original_index to LLM enhancement
        llm_map = {
            item.get("original_index", idx): item
            for idx, item in enumerate(enhanced_damages_list)
        }

        # Merge
        merged = []
        for idx, yolo_damage in enumerate(yolo_damages):
            llm_data = llm_map.get(idx, {})

            merged_damage = {
                # Keep YOLO's precise data
                "bbox": yolo_damage["bbox"],
                "confidence": yolo_damage["confidence"],

                # Use LLM's enhanced classification if available
                "type": llm_data.get("type", yolo_damage.get("type", "unknown")),
                "severity": llm_data.get("severity", yolo_damage.get("severity", "minor")),

                # Use LLM's description if available, otherwise fall back to YOLO
                "description": llm_data.get("description", yolo_damage.get("description", "Roof damage detected")),
                "severity_reasoning": llm_data.get("severity_reasoning", ""),
                "confidence_assessment": llm_data.get("confidence_assessment", "")
            }

            merged.append(merged_damage)

        return merged

    def _calculate_summary(self, damages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate damage summary statistics."""
        by_type = {}
        by_severity = {}

        for damage in damages:
            damage_type = damage.get("type", "unknown")
            by_type[damage_type] = by_type.get(damage_type, 0) + 1

            severity = damage.get("severity", "minor")
            by_severity[severity] = by_severity.get(severity, 0) + 1

        return {
            "total_damages": len(damages),
            "by_type": by_type,
            "by_severity": by_severity
        }


# Global instance
hybrid_vision_service = HybridVisionService()
