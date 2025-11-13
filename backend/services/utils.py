"""
Shared utility functions for RoofScan AI backend services.

This module contains common functions used across multiple services to avoid code duplication.
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime, timedelta
from collections import Counter
from PIL import Image

logger = logging.getLogger(__name__)


def calculate_summary(damages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate damage summary statistics.

    Args:
        damages: List of damage dictionaries

    Returns:
        Dictionary with total_damages, by_type, and by_severity counts
    """
    if not damages:
        return {
            "total_damages": 0,
            "by_type": {},
            "by_severity": {}
        }

    # Count by type
    types = [d.get("type", "unknown") for d in damages]
    by_type = dict(Counter(types))

    # Count by severity
    severities = [d.get("severity", "unknown") for d in damages]
    by_severity = dict(Counter(severities))

    return {
        "total_damages": len(damages),
        "by_type": by_type,
        "by_severity": by_severity
    }


def sanitize_filename(filename: str) -> str:
    """
    Remove path traversal characters from filename.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename safe for filesystem operations
    """
    # Remove path traversal attempts
    safe_name = filename.replace('..', '').replace('/', '').replace('\\', '')

    # Remove any remaining suspicious characters
    safe_name = ''.join(c for c in safe_name if c.isalnum() or c in '._-')

    return safe_name


def validate_image(file_path: Path) -> bool:
    """
    Validate that a file is a valid image and not corrupted.

    Args:
        file_path: Path to image file

    Returns:
        True if image is valid, False otherwise
    """
    try:
        img = Image.open(file_path)
        img.verify()  # Verify image integrity

        # Reopen after verify (verify closes the file)
        img = Image.open(file_path)

        # Strip EXIF data for privacy
        if hasattr(img, 'info') and 'exif' in img.info:
            logger.info(f"Stripping EXIF data from {file_path}")
            img_no_exif = Image.new(img.mode, img.size)
            img_no_exif.putdata(list(img.getdata()))
            img_no_exif.save(file_path)

        return True
    except Exception as e:
        logger.error(f"Invalid image {file_path}: {e}")
        return False


def cleanup_old_files(directory: Path, max_age_hours: int = 24):
    """
    Delete files older than max_age_hours from directory.

    Args:
        directory: Directory to clean
        max_age_hours: Maximum file age in hours before deletion
    """
    if not directory.exists():
        return

    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    deleted_count = 0

    try:
        for file_path in directory.glob("*"):
            if file_path.is_file():
                file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_mtime < cutoff:
                    file_path.unlink()
                    deleted_count += 1
                    logger.debug(f"Deleted old file: {file_path}")

        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old files from {directory}")
    except Exception as e:
        logger.error(f"Error during file cleanup: {e}")


def optimize_image_for_api(image_path: Path, max_dimension: int = 1024) -> Path:
    """
    Optimize image for API calls by resizing and compressing.

    Reduces payload size while maintaining quality for detection.

    Args:
        image_path: Path to original image
        max_dimension: Maximum width or height in pixels

    Returns:
        Path to optimized image
    """
    img = Image.open(image_path)

    # Convert RGBA/LA/P to RGB
    if img.mode in ('RGBA', 'LA', 'P'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'RGBA':
            background.paste(img, mask=img.split()[-1])
        else:
            background.paste(img)
        img = background

    # Resize if too large
    if max(img.size) > max_dimension:
        ratio = max_dimension / max(img.size)
        new_size = tuple(int(dim * ratio) for dim in img.size)
        img = img.resize(new_size, Image.Resampling.LANCZOS)
        logger.info(f"Resized image from {image_path.stat().st_size} to {new_size}")

    # Save optimized version
    optimized_path = image_path.parent / f"{image_path.stem}_optimized.jpg"
    img.save(optimized_path, 'JPEG', quality=85, optimize=True)

    original_size = image_path.stat().st_size
    optimized_size = optimized_path.stat().st_size
    reduction = (1 - optimized_size / original_size) * 100

    logger.info(f"Optimized image: {original_size} -> {optimized_size} bytes ({reduction:.1f}% reduction)")

    return optimized_path


def validate_api_keys() -> None:
    """
    Validate that required API keys are set in environment.

    Raises:
        ValueError: If any required API keys are missing
    """
    required_keys = ["OPENAI_API_KEY", "ROBOFLOW_API_KEY"]
    missing = [
        key for key in required_keys
        if not os.getenv(key) or os.getenv(key) == "not-set" or os.getenv(key).startswith("your_")
    ]

    if missing:
        raise ValueError(
            f"Missing or invalid API keys: {', '.join(missing)}. "
            f"Please set them in backend/.env file."
        )

    logger.info("All required API keys validated successfully")
