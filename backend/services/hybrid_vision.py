import os
import json
import base64
import asyncio
from pathlib import Path
from typing import Dict, Any, List

from openai import OpenAI
from services.roboflow_vision import roboflow_vision_service
from services.utils import calculate_summary


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
        # Use gpt-4o-mini for fast, cost-effective vision reasoning
        # Note: gpt-5-nano doesn't support vision/images
        self.llm_model = os.getenv("LLM_MODEL", "gpt-4o-mini")

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

    def _create_single_damage_prompt(self, damage: Dict[str, Any], damage_index: int) -> str:
        """
        Create a focused prompt for analyzing a single damage area.

        Args:
            damage: Single damage detection from YOLO
            damage_index: Index of this damage in the list

        Returns:
            Prompt string for LLM
        """
        bbox = damage.get("bbox", [])
        confidence = damage.get("confidence", 0)

        prompt = f"""You are a conservative roof inspector analyzing damage area #{damage_index}.

DAMAGE LOCATION: Bounding box coordinates {bbox} (percentage of image)
DETECTION CONFIDENCE: {confidence * 100:.0f}%

Analyze this specific damaged area and provide:

1. **Type**: What kind of damage do you observe?
   - missing_shingles: Complete absence of shingles
   - cracked_shingles: Visible cracks or splits
   - hail_damage: Circular dents or bruising
   - wind_damage: Lifted or curled shingles
   - torn_underlayment: Tears in protective layer
   - damaged_shingles: General shingle damage

2. **Severity**: BE CONSERVATIVE. Use these strict criteria:
   - **severe**: ONLY if structural integrity is compromised (exposed wood/underlayment over large area, active water intrusion risk, immediate repair needed)
   - **moderate**: Visible damage that will worsen but not immediately critical (multiple cracked shingles, lifted edges, moderate hail dents)
   - **minor**: Cosmetic or early-stage damage (small cracks, minor wear, single damaged shingle, superficial granule loss)

   DEFAULT TO MINOR unless clear evidence warrants higher severity.

3. **Description**: Describe what you see as if writing an inspection report
   Examples: "Large area of missing shingles exposing underlayment", "Small crack in shingle corner", "Minor granule loss on asphalt shingle"

4. **Reasoning**: Why you assigned this severity and your confidence level (high/medium/low)

Return ONLY valid JSON in this format:
{{
  "type": "damage_type",
  "severity": "minor|moderate|severe",
  "description": "What you observe",
  "severity_reasoning": "Why this severity",
  "confidence_assessment": "high|medium/low and reason"
}}

NO markdown formatting."""
        return prompt

    async def _reason_about_single_damage(
        self,
        damage: Dict[str, Any],
        damage_index: int,
        image_path: Path
    ) -> Dict[str, Any]:
        """
        Use LLM to reason about a single damage area.

        Args:
            damage: Single damage detection
            damage_index: Index of damage
            image_path: Path to image

        Returns:
            Enhanced damage data
        """
        try:
            # Encode image
            image_data = self._encode_image(image_path)
            file_ext = image_path.suffix.lower()
            media_type = "image/jpeg" if file_ext in [".jpg", ".jpeg"] else "image/png"

            prompt = self._create_single_damage_prompt(damage, damage_index)

            print(f"[DEBUG] Calling LLM model: {self.llm_model} for damage {damage_index}")
            print(f"[DEBUG] Prompt length: {len(prompt)} chars")

            try:
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
                    max_completion_tokens=400  # gpt-5-nano only supports default temperature
                )
                print(f"[DEBUG] API call succeeded")
            except Exception as api_error:
                print(f"[ERROR] API call failed: {api_error}")
                import traceback
                traceback.print_exc()
                raise

            print(f"[DEBUG] Raw response object:")
            print(f"  - Model: {response.model}")
            print(f"  - ID: {response.id}")
            print(f"  - Choices count: {len(response.choices)}")

            if response.choices:
                choice = response.choices[0]
                print(f"  - First choice finish_reason: {choice.finish_reason}")
                print(f"  - First choice message: {choice.message}")
                print(f"  - Message content type: {type(choice.message.content)}")
                print(f"  - Message content value: {repr(choice.message.content)}")

                # Check for refusal (new in some models)
                if hasattr(choice.message, 'refusal'):
                    print(f"  - Refusal: {choice.message.refusal}")

                response_text = choice.message.content or ""
            else:
                print(f"  - NO CHOICES IN RESPONSE!")
                response_text = ""

            print(f"[DEBUG] Final response_text length: {len(response_text)}")
            print(f"\n[LLM RESPONSE {damage_index}] Full response:")
            print(response_text)
            print(f"[LLM RESPONSE {damage_index}] End of response\n")

            result = self._parse_json_response(response_text)
            print(f"[DEBUG] Parsed result for damage {damage_index}: {result}")

            return {
                "original_index": damage_index,
                **result
            }

        except Exception as e:
            print(f"[ERROR] LLM reasoning failed for damage {damage_index}: {e}")
            import traceback
            traceback.print_exc()
            return {
                "original_index": damage_index,
                "type": damage.get("type", "unknown"),
                "severity": damage.get("severity", "minor"),
                "description": damage.get("description", "Roof damage detected"),
                "severity_reasoning": f"LLM analysis failed: {str(e)}",
                "confidence_assessment": "low"
            }

    async def _generate_overall_assessment(
        self,
        enhanced_damages: List[Dict[str, Any]],
        image_path: Path
    ) -> Dict[str, Any]:
        """
        Generate overall roof assessment based on all damages.

        Args:
            enhanced_damages: List of enhanced damage data
            image_path: Path to image

        Returns:
            Overall assessment dictionary
        """
        if not enhanced_damages:
            return {
                "severity": "unknown",
                "reasoning": "No damage detected",
                "immediate_action_needed": False,
                "confidence": "high"
            }

        try:
            # Count severities
            severe_count = sum(1 for d in enhanced_damages if d.get("severity") == "severe")
            moderate_count = sum(1 for d in enhanced_damages if d.get("severity") == "moderate")
            minor_count = sum(1 for d in enhanced_damages if d.get("severity") == "minor")

            # Determine overall severity
            if severe_count > 0:
                overall_severity = "severe"
                immediate_action = True
            elif moderate_count > 2:  # Multiple moderate issues
                overall_severity = "severe"
                immediate_action = True
            elif moderate_count > 0:
                overall_severity = "moderate"
                immediate_action = False
            else:
                overall_severity = "minor"
                immediate_action = False

            # Create summary prompt
            prompt = f"""You are an expert roof inspector providing an overall assessment.

DAMAGE SUMMARY:
- Total damages: {len(enhanced_damages)}
- Severe: {severe_count}
- Moderate: {moderate_count}
- Minor: {minor_count}

Provide a brief overall assessment (2-3 sentences) of the roof condition and whether immediate action is needed.

Return ONLY valid JSON:
{{
  "reasoning": "Your overall assessment",
  "confidence": "high|medium|low"
}}

NO markdown formatting."""

            # Encode image for context
            image_data = self._encode_image(image_path)
            file_ext = image_path.suffix.lower()
            media_type = "image/jpeg" if file_ext in [".jpg", ".jpeg"] else "image/png"

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
                max_completion_tokens=300  # gpt-5-nano only supports default temperature
            )

            response_text = response.choices[0].message.content
            result = self._parse_json_response(response_text)

            return {
                "severity": overall_severity,
                "reasoning": result.get("reasoning", "Overall roof assessment completed"),
                "immediate_action_needed": immediate_action,
                "confidence": result.get("confidence", "medium")
            }

        except Exception as e:
            print(f"[WARNING] Overall assessment failed: {e}")
            return {
                "severity": overall_severity if 'overall_severity' in locals() else "unknown",
                "reasoning": f"Overall assessment based on {len(enhanced_damages)} damages",
                "immediate_action_needed": severe_count > 0 if 'severe_count' in locals() else False,
                "confidence": "medium"
            }

    async def _run_llm_reasoning_parallel(
        self,
        yolo_damages: List[Dict[str, Any]],
        image_path: Path
    ) -> Dict[str, Any]:
        """
        Run LLM reasoning in parallel for each damage detection.
        Significantly faster for images with multiple damages.

        Args:
            yolo_damages: List of YOLO damage detections
            image_path: Path to image

        Returns:
            Enhanced damages with LLM reasoning
        """
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

        if not yolo_damages:
            return {
                "enhanced_damages": [],
                "overall_assessment": {
                    "severity": "unknown",
                    "reasoning": "No damage detected",
                    "immediate_action_needed": False,
                    "confidence": "high"
                }
            }

        try:
            print(f"[DEBUG] Analyzing {len(yolo_damages)} damages in parallel...")

            # Create tasks for parallel execution
            tasks = [
                self._reason_about_single_damage(damage, idx, image_path)
                for idx, damage in enumerate(yolo_damages)
            ]

            # Run all tasks concurrently
            enhanced_damages = await asyncio.gather(*tasks)

            # Generate overall assessment
            overall = await self._generate_overall_assessment(enhanced_damages, image_path)

            print(f"[DEBUG] Parallel LLM analysis complete")

            return {
                "enhanced_damages": list(enhanced_damages),
                "overall_assessment": overall
            }

        except Exception as e:
            print(f"[ERROR] Parallel LLM reasoning failed: {e}")
            return {
                "enhanced_damages": [],
                "overall_assessment": {
                    "severity": "unknown",
                    "reasoning": f"LLM reasoning failed: {str(e)}",
                    "immediate_action_needed": False,
                    "confidence": "low"
                }
            }

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
        print(f"\n{'='*80}")
        print(f"[HYBRID] Starting hybrid detection on: {image_path}")
        print(f"[HYBRID] LLM Model: {self.llm_model}")
        print(f"[HYBRID] API Key set: {self.llm_client.api_key != 'not-set'}")
        print(f"{'='*80}\n")

        # Step 1: Run YOLO detection
        print("[HYBRID] Step 1: Running YOLOv11 detection...")
        yolo_result = roboflow_vision_service.detect_damage(image_path)
        yolo_damages = yolo_result.get("damages", [])

        print(f"[HYBRID] YOLO detected {len(yolo_damages)} damages")

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

        # Step 2: Use LLM for reasoning in parallel (with image)
        print("[HYBRID] Step 2: Running parallel LLM reasoning with image...")
        llm_enhancement = await self._run_llm_reasoning_parallel(yolo_damages, image_path)
        print(f"[HYBRID] LLM enhancement result: {llm_enhancement}")

        # Step 3: Merge YOLO detections with LLM reasoning
        print("[HYBRID] Step 3: Merging YOLO + LLM results...")
        enhanced_damages = self._merge_detections(yolo_damages, llm_enhancement)
        print(f"[HYBRID] Enhanced damages: {enhanced_damages}")

        # Step 4: Calculate final summary (using shared utility)
        summary = calculate_summary(enhanced_damages)

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


# Global instance
hybrid_vision_service = HybridVisionService()
