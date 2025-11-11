from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from io import BytesIO

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image as RLImage,
    PageBreak,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT


class ReportGenerator:
    """Service for generating PDF reports from damage analysis results."""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Setup custom paragraph styles."""
        self.styles.add(
            ParagraphStyle(
                name="CustomTitle",
                parent=self.styles["Heading1"],
                fontSize=24,
                textColor=colors.HexColor("#2d3748"),
                spaceAfter=6,
                alignment=TA_CENTER,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="SectionHeader",
                parent=self.styles["Heading2"],
                fontSize=16,
                textColor=colors.HexColor("#4a5568"),
                spaceBefore=12,
                spaceAfter=6,
            )
        )

    def _create_header(self, timestamp: str) -> List:
        """Create report header section."""
        elements = []

        # Title
        title = Paragraph("Roof Damage Assessment Report", self.styles["CustomTitle"])
        elements.append(title)
        elements.append(Spacer(1, 0.1 * inch))

        # Timestamp
        date_text = Paragraph(
            f"<b>Generated:</b> {timestamp}", self.styles["Normal"]
        )
        elements.append(date_text)
        elements.append(Spacer(1, 0.3 * inch))

        return elements

    def _create_executive_summary(self, summary: Dict[str, Any]) -> List:
        """Create executive summary section."""
        elements = []

        # Section header
        header = Paragraph("Executive Summary", self.styles["SectionHeader"])
        elements.append(header)

        # Summary statistics
        total = summary.get("total_damages", 0)
        by_severity = summary.get("by_severity", {})

        severe = by_severity.get("severe", 0)
        moderate = by_severity.get("moderate", 0)
        minor = by_severity.get("minor", 0)

        summary_text = f"""
        <b>Total Damages Detected:</b> {total}<br/>
        <b>Severe:</b> {severe}<br/>
        <b>Moderate:</b> {moderate}<br/>
        <b>Minor:</b> {minor}
        """

        summary_para = Paragraph(summary_text, self.styles["Normal"])
        elements.append(summary_para)
        elements.append(Spacer(1, 0.3 * inch))

        return elements

    def _create_recommendations(self, summary: Dict[str, Any]) -> List:
        """Create recommendations section based on severity."""
        elements = []

        by_severity = summary.get("by_severity", {})
        severe = by_severity.get("severe", 0)
        moderate = by_severity.get("moderate", 0)

        if severe > 0:
            rec_text = """
            <b>⚠️ Immediate Action Required:</b> Severe damage detected.
            Recommend immediate professional inspection and repair to prevent further deterioration.
            """
        elif moderate > 0:
            rec_text = """
            <b>Recommended Action:</b> Moderate damage detected.
            Schedule professional inspection within 2-4 weeks to assess repair needs.
            """
        else:
            rec_text = """
            <b>Status:</b> Minor or no significant damage detected.
            Regular maintenance recommended to maintain roof integrity.
            """

        header = Paragraph("Recommendations", self.styles["SectionHeader"])
        elements.append(header)

        rec_para = Paragraph(rec_text, self.styles["Normal"])
        elements.append(rec_para)
        elements.append(Spacer(1, 0.3 * inch))

        return elements

    def _create_annotated_image(self, image_path: Path) -> List:
        """Create annotated image section."""
        elements = []

        header = Paragraph("Annotated Image", self.styles["SectionHeader"])
        elements.append(header)
        elements.append(Spacer(1, 0.1 * inch))

        try:
            # Add image - scale to fit page width
            img = RLImage(str(image_path), width=6.5 * inch, height=4.5 * inch)
            elements.append(img)
        except Exception as e:
            error_text = Paragraph(
                f"<i>Error loading image: {str(e)}</i>", self.styles["Normal"]
            )
            elements.append(error_text)

        elements.append(Spacer(1, 0.3 * inch))

        return elements

    def _create_damage_table(self, damages: List[Dict[str, Any]]) -> List:
        """Create damage details table."""
        elements = []

        header = Paragraph("Damage Details", self.styles["SectionHeader"])
        elements.append(header)
        elements.append(Spacer(1, 0.1 * inch))

        if not damages:
            no_damage = Paragraph(
                "<i>No damage detected in this analysis.</i>", self.styles["Normal"]
            )
            elements.append(no_damage)
            return elements

        # Table data
        table_data = [["#", "Type", "Severity", "Confidence", "Description"]]

        for idx, damage in enumerate(damages, 1):
            damage_type = damage.get("type", "unknown").replace("_", " ").title()
            severity = damage.get("severity", "unknown").title()
            confidence = f"{damage.get('confidence', 0) * 100:.0f}%"
            description = damage.get("description", "-")[:50]  # Truncate if too long

            table_data.append([str(idx), damage_type, severity, confidence, description])

        # Create table
        table = Table(table_data, colWidths=[0.5 * inch, 1.8 * inch, 1 * inch, 1 * inch, 2.2 * inch])

        # Style table
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#edf2f7")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#2d3748")),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 1), (-1, -1), 9),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7fafc")]),
                ]
            )
        )

        elements.append(table)
        elements.append(Spacer(1, 0.3 * inch))

        return elements

    def generate_report(
        self,
        damages: List[Dict[str, Any]],
        summary: Dict[str, Any],
        annotated_image_path: Path,
    ) -> BytesIO:
        """
        Generate a PDF report from analysis results.

        Args:
            damages: List of detected damages
            summary: Summary statistics
            annotated_image_path: Path to annotated image

        Returns:
            BytesIO buffer containing the PDF
        """
        # Create PDF buffer
        buffer = BytesIO()

        # Create PDF document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )

        # Build content
        elements = []

        # Header
        timestamp = datetime.now().strftime("%B %d, %Y %I:%M %p")
        elements.extend(self._create_header(timestamp))

        # Executive Summary
        elements.extend(self._create_executive_summary(summary))

        # Recommendations
        elements.extend(self._create_recommendations(summary))

        # Annotated Image
        if annotated_image_path.exists():
            elements.extend(self._create_annotated_image(annotated_image_path))

        # Damage Details Table
        elements.extend(self._create_damage_table(damages))

        # Build PDF
        doc.build(elements)

        # Reset buffer position
        buffer.seek(0)

        return buffer


# Global instance
report_generator = ReportGenerator()
