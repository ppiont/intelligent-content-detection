from pathlib import Path
from typing import List, Dict, Any, Tuple

from PIL import Image, ImageDraw, ImageFont


class ImageProcessor:
    """Service for annotating images with damage bounding boxes."""

    # Severity color mapping (RGB with alpha for fills)
    SEVERITY_COLORS = {
        "minor": {
            "stroke": (255, 255, 0),  # Yellow
            "fill": (255, 255, 0, 51),  # Yellow with 0.2 alpha (51/255)
        },
        "moderate": {
            "stroke": (255, 165, 0),  # Orange
            "fill": (255, 165, 0, 51),  # Orange with 0.2 alpha
        },
        "severe": {
            "stroke": (255, 0, 0),  # Red
            "fill": (255, 0, 0, 51),  # Red with 0.2 alpha
        },
    }

    BOX_LINE_WIDTH = 3

    def _percentage_to_pixels(
        self, bbox: List[float], width: int, height: int
    ) -> Tuple[int, int, int, int]:
        """
        Convert percentage-based bounding box to pixel coordinates.

        Args:
            bbox: [x1, y1, x2, y2] as percentages (0-1 or 0-100)
            width: Image width in pixels
            height: Image height in pixels

        Returns:
            Tuple of (x1, y1, x2, y2) in pixel coordinates
        """
        # Check if values are in 0-1 range (common for ML models) or 0-100 range
        # If max value is <= 1, assume 0-1 range, otherwise 0-100
        max_val = max(bbox)
        if max_val <= 1.0:
            # Values are in 0-1 range, multiply directly
            x1 = int(bbox[0] * width)
            y1 = int(bbox[1] * height)
            x2 = int(bbox[2] * width)
            y2 = int(bbox[3] * height)
        else:
            # Values are in 0-100 range, divide by 100 first
            x1 = int((bbox[0] / 100) * width)
            y1 = int((bbox[1] / 100) * height)
            x2 = int((bbox[2] / 100) * width)
            y2 = int((bbox[3] / 100) * height)
        return (x1, y1, x2, y2)

    def _draw_label(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        position: Tuple[int, int],
        severity: str,
        font_size: int,
    ):
        """
        Draw a text label with background box.

        Args:
            draw: PIL ImageDraw object
            text: Label text
            position: (x, y) position for top-left of label
            severity: Severity level for color selection
            font_size: Font size for the text
        """
        # Try to load a nice font, fallback to default
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
        except:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
            except:
                font = ImageFont.load_default()

        # Get text bounding box
        bbox = draw.textbbox(position, text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Add padding
        padding = 4
        background_bbox = [
            bbox[0] - padding,
            bbox[1] - padding,
            bbox[2] + padding,
            bbox[3] + padding,
        ]

        # Draw background
        color = self.SEVERITY_COLORS.get(severity, self.SEVERITY_COLORS["minor"])
        draw.rectangle(background_bbox, fill=(0, 0, 0, 180))  # Semi-transparent black

        # Draw text
        draw.text(position, text, fill=(255, 255, 255), font=font)

    def annotate_image(
        self, input_path: Path, output_path: Path, damages: List[Dict[str, Any]]
    ) -> Path:
        """
        Draw bounding boxes and labels on image for detected damages.

        Args:
            input_path: Path to original image
            output_path: Path to save annotated image
            damages: List of damage dictionaries with bbox, type, severity

        Returns:
            Path to the annotated image
        """
        print(f"[DEBUG] Annotating image with {len(damages)} damages")

        # Open image and convert to RGB if needed
        image = Image.open(input_path)
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Create a copy to draw on
        annotated = image.copy()
        draw = ImageDraw.Draw(annotated)

        # Calculate font size based on image dimensions
        font_size = max(12, min(image.width, image.height) // 40)

        # Draw each damage area
        for idx, damage in enumerate(damages):
            print(f"[DEBUG] Processing damage {idx}: {damage}")
            severity = damage.get("severity", "minor").lower()
            damage_type = damage.get("type", "unknown").replace("_", " ").title()
            bbox = damage.get("bbox", [])
            confidence = damage.get("confidence", 0.0)

            if len(bbox) != 4:
                continue

            # Convert percentage to pixels
            pixel_bbox = self._percentage_to_pixels(
                bbox, image.width, image.height
            )
            print(f"[DEBUG] Pixel bbox: {pixel_bbox}, Image size: {image.width}x{image.height}")

            # Get colors
            colors = self.SEVERITY_COLORS.get(
                severity, self.SEVERITY_COLORS["minor"]
            )
            print(f"[DEBUG] Drawing {severity} box with color {colors['stroke']}")

            # Draw rectangle outline with thick lines
            for i in range(self.BOX_LINE_WIDTH):
                adjusted_bbox = [
                    pixel_bbox[0] - i,
                    pixel_bbox[1] - i,
                    pixel_bbox[2] + i,
                    pixel_bbox[3] + i
                ]
                draw.rectangle(adjusted_bbox, outline=colors["stroke"])

            print(f"[DEBUG] Drew {self.BOX_LINE_WIDTH} rectangles")

            # Prepare label
            label = f"{damage_type} - {severity.title()}"
            if confidence > 0:
                label += f" ({confidence:.0%})"

            # Draw label above the box
            label_position = (pixel_bbox[0], max(0, pixel_bbox[1] - font_size - 12))
            self._draw_label(
                draw, label, label_position, severity, font_size
            )

        image = annotated

        # Save annotated image
        image.save(output_path, "JPEG", quality=90)

        return output_path


# Global instance
image_processor = ImageProcessor()
