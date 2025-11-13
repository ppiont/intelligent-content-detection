import os
from pathlib import Path
from typing import List, Dict, Any
from inference_sdk import InferenceHTTPClient


class RoboflowVisionService:
    """Service for detecting roof damage using Roboflow Inference SDK."""

    def __init__(self):
        self.api_key = os.getenv("ROBOFLOW_API_KEY") or "not-set"

        # Your custom YOLOv11 model ID
        self.model_id = "roof-dmg-a1b1a/3"

        # Initialize the client - use detect.roboflow.com for hosted models
        self.client = InferenceHTTPClient(
            api_url="https://detect.roboflow.com",
            api_key=self.api_key
        )

        # Default confidence threshold (0-100 scale)
        self.confidence = 40

    def detect_damage(self, image_path: Path) -> Dict[str, Any]:
        """
        Detect roof damage in an image using Roboflow Inference SDK.

        Args:
            image_path: Path to the image file

        Returns:
            Dict with damages array and summary statistics
        """
        print(f"[DEBUG] Running Roboflow YOLOv11 inference on: {image_path}")

        # Check if API key is set
        if self.api_key == "not-set":
            raise Exception(
                "ROBOFLOW_API_KEY not set. Please add your Roboflow API key to backend/.env file. "
                "Get your key from: https://app.roboflow.com/settings/api"
            )

        # Run inference using the SDK
        result = self.client.infer(
            str(image_path),
            model_id=self.model_id
        )

        print(f"[DEBUG] Roboflow raw result: {result}")

        # Parse predictions
        predictions = result.get("predictions", [])
        damages = []

        # Get image dimensions from result (Roboflow SDK returns these at top level)
        image_width = result.get("image", {}).get("width", 0)
        image_height = result.get("image", {}).get("height", 0)

        # Fallback: if not in 'image' dict, check top level
        if image_width == 0 or image_height == 0:
            image_width = result.get("width", 0)
            image_height = result.get("height", 0)

        print(f"[DEBUG] Image dimensions: {image_width}x{image_height}")
        print(f"[DEBUG] Found {len(predictions)} predictions")

        for pred in predictions:
            # Roboflow returns:
            # - x, y: center coordinates (pixels)
            # - width, height: box dimensions (pixels)
            # - class: detected class name
            # - confidence: 0-1 score

            center_x = pred.get("x", 0)
            center_y = pred.get("y", 0)
            box_width = pred.get("width", 0)
            box_height = pred.get("height", 0)

            # Convert center+dimensions to corner coordinates (x1, y1, x2, y2)
            x1 = center_x - (box_width / 2)
            y1 = center_y - (box_height / 2)
            x2 = center_x + (box_width / 2)
            y2 = center_y + (box_height / 2)

            # Convert to percentages (0-100) for consistency with image processor
            if image_width > 0 and image_height > 0:
                bbox_percent = [
                    (x1 / image_width) * 100,
                    (y1 / image_height) * 100,
                    (x2 / image_width) * 100,
                    (y2 / image_height) * 100,
                ]
            else:
                bbox_percent = [0, 0, 0, 0]

            detected_class = pred.get("class", "unknown")
            confidence = pred.get("confidence", 0.0)

            # Map Roboflow classes to our severity system (using confidence and bbox size)
            severity = self._map_class_to_severity(detected_class, confidence, bbox_percent)
            damage_type = self._map_class_to_type(detected_class)

            damage = {
                "type": damage_type,
                "severity": severity,
                "bbox": bbox_percent,
                "confidence": confidence,
                "description": f"{detected_class} detected by Roboflow model",
            }

            damages.append(damage)
            print(f"[DEBUG] Damage: {damage}")

        # Generate summary
        summary = self._generate_summary(damages)

        return {
            "damages": damages,
            "summary": summary,
        }

    def _map_class_to_severity(self, roboflow_class: str, confidence: float, bbox: List[float]) -> str:
        """
        Map Roboflow class names to severity levels based on confidence and size.

        For models with a single "damage" class, we use confidence and bbox size
        to determine severity. The LLM will refine this further in hybrid mode.
        """
        # Calculate bounding box area (as percentage of image)
        if len(bbox) == 4:
            width = abs(bbox[2] - bbox[0])
            height = abs(bbox[3] - bbox[1])
            area = width * height
        else:
            area = 0

        # Use confidence and size to determine initial severity
        # High confidence + large area = more severe
        if confidence > 0.8 and area > 10:  # Large damage with high confidence
            return "severe"
        elif confidence > 0.6 and area > 5:  # Medium damage
            return "moderate"
        else:
            return "minor"

    def _map_class_to_type(self, roboflow_class: str) -> str:
        """
        Map Roboflow class to damage type.

        For single "damage" class models, return generic roof_damage.
        The LLM will refine this to specific types in hybrid mode.
        """
        # For single-class models, use generic type
        # The hybrid LLM will provide more specific classification
        return "roof_damage"

    def _generate_summary(self, damages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate summary statistics from damages."""
        by_type = {}
        by_severity = {}

        for damage in damages:
            # Count by type
            damage_type = damage.get("type", "unknown")
            by_type[damage_type] = by_type.get(damage_type, 0) + 1

            # Count by severity
            severity = damage.get("severity", "minor")
            by_severity[severity] = by_severity.get(severity, 0) + 1

        return {
            "total_damages": len(damages),
            "by_type": by_type,
            "by_severity": by_severity,
        }


# Global instance
roboflow_vision_service = RoboflowVisionService()
