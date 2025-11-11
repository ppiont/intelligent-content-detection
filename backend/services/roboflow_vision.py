import os
import base64
import requests
from pathlib import Path
from typing import List, Dict, Any


class RoboflowVisionService:
    """Service for detecting roof damage using Roboflow Inference API."""

    def __init__(self):
        self.api_key = os.getenv("ROBOFLOW_API_KEY") or "not-set"

        # Roboflow Inference API endpoint
        # Using the public model: shingle-roof-inspection/damaged-shingle-obj-detection
        self.api_url = "https://detect.roboflow.com/damaged-shingle-obj-detection/1"

        # Default confidence and overlap thresholds
        self.confidence = 40
        self.overlap = 30

    def detect_damage(self, image_path: Path) -> Dict[str, Any]:
        """
        Detect roof damage in an image using Roboflow Inference API.

        Args:
            image_path: Path to the image file

        Returns:
            Dict with damages array and summary statistics
        """
        print(f"[DEBUG] Running Roboflow inference on: {image_path}")

        # Read and encode image to base64
        with open(image_path, "rb") as image_file:
            image_data = base64.b64encode(image_file.read()).decode("utf-8")

        # Make API request
        params = {
            "api_key": self.api_key,
            "confidence": self.confidence,
            "overlap": self.overlap,
        }

        response = requests.post(
            self.api_url,
            params=params,
            data=image_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if response.status_code != 200:
            raise RuntimeError(f"Roboflow API error: {response.status_code} - {response.text}")

        result = response.json()
        print(f"[DEBUG] Roboflow raw result: {result}")

        # Parse predictions
        predictions = result.get("predictions", [])
        damages = []

        # Get image dimensions from result
        image_width = result.get("image", {}).get("width", 0)
        image_height = result.get("image", {}).get("height", 0)

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

            # Map Roboflow classes to our severity system
            severity = self._map_class_to_severity(detected_class)
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

    def _map_class_to_severity(self, roboflow_class: str) -> str:
        """
        Map Roboflow class names to severity levels.

        Roboflow model classes: "Damaged", "Not Damaged", "Obvious Damage"
        """
        roboflow_class_lower = roboflow_class.lower()

        if "obvious" in roboflow_class_lower:
            return "severe"
        elif "damaged" in roboflow_class_lower and "not" not in roboflow_class_lower:
            return "moderate"
        else:
            return "minor"

    def _map_class_to_type(self, roboflow_class: str) -> str:
        """Map Roboflow class to damage type."""
        roboflow_class_lower = roboflow_class.lower()

        # The Roboflow model detects shingle damage generically
        # We'll categorize based on severity indicator
        if "obvious" in roboflow_class_lower:
            return "missing_shingles"
        elif "damaged" in roboflow_class_lower:
            return "damaged_shingles"
        else:
            return "wear"

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
