"""
PDF report generation
"""

from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime

# Try to import reportlab
try:
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, Image
    )
    from reportlab.pdfgen import canvas
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


class PDFReportGenerator:
    """Generate PDF reports for cost estimation"""
    
    def __init__(self, output_dir: str = "output/reports"):
        """
        Initialize PDF generator
        
        Args:
            output_dir: Directory to save reports
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        if HAS_REPORTLAB:
            self.styles = getSampleStyleSheet()
            self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles"""
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#0078D4'),
            spaceAfter=20,
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomHeading',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#323130'),
            spaceAfter=12,
        ))
        
        self.styles.add(ParagraphStyle(
            name='CostValue',
            parent=self.styles['Normal'],
            fontSize=14,
            textColor=colors.HexColor('#107C10'),
            spaceAfter=10,
        ))
    
    def generate_report(
        self,
        cost_data: Dict[str, Any],
        title: str = "Azure Cost Estimation Report",
        include_charts: bool = True
    ) -> str:
        """
        Generate a PDF report
        
        Args:
            cost_data: Cost breakdown data
            title: Report title
            include_charts: Whether to include charts
            
        Returns:
            Path to saved PDF
        """
        if not HAS_REPORTLAB:
            return "Error: reportlab not installed. Install with: pip install reportlab"
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"azure_cost_report_{timestamp}.pdf"
        filepath = self.output_dir / filename
        
        # Create PDF
        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72,
        )
        
        # Build story (content)
        story = []
        
        # Title
        story.append(Paragraph(title, self.styles['CustomTitle']))
        story.append(Spacer(1, 0.25 * inch))
        
        # Date
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        story.append(Paragraph(f"Generated: {date_str}", self.styles['Normal']))
        story.append(Spacer(1, 0.5 * inch))
        
        # Cost summary section
        story.append(Paragraph("Cost Summary", self.styles['CustomHeading']))
        story.append(Spacer(1, 0.25 * inch))
        
        summary = cost_data.get("summary", {})
        
        if summary:
            summary_data = [
                ["Metric", "Value"],
                ["Total Monthly", f"${summary.get('total_monthly_cost_usd', 0):.2f}"],
                ["Total Hourly", f"${summary.get('total_hourly_cost_usd', 0):.2f}"],
                ["Currency", summary.get("currency", "USD")],
                ["Region", summary.get("region", "N/A")],
            ]
            
            table = Table(summary_data, colWidths=[2.5 * inch, 2.5 * inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0078D4')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            story.append(table)
            story.append(Spacer(1, 0.5 * inch))
        
        # Service breakdown section
        story.append(Paragraph("Service Breakdown", self.styles['CustomHeading']))
        story.append(Spacer(1, 0.25 * inch))
        
        # Build service table
        service_rows = [["Service", "Monthly Cost"]]
        
        for service, details in cost_data.items():
            if service == "summary":
                continue
            
            if isinstance(details, dict):
                monthly = details.get("total_monthly", 0)
                if monthly:
                    service_rows.append([service, f"${monthly:.2f}"])
        
        if len(service_rows) > 1:
            service_table = Table(service_rows)
            service_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#107C10')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            story.append(service_table)
        
        # Build PDF
        doc.build(story)
        
        return str(filepath)
    
    def add_chart_to_report(
        self,
        pdf_path: str,
        chart_path: str,
        x: float = 72,
        y: float = 72,
        width: float = 4 * inch
    ) -> str:
        """
        Add a chart image to existing PDF
        
        Args:
            pdf_path: Path to PDF
            chart_path: Path to chart image
            x: X position
            y: Y position
            width: Image width
            
        Returns:
            Updated PDF path
        """
        if not HAS_REPORTLAB:
            return "Error: reportlab not installed"
        
        # Use canvas to add image
        c = canvas.Canvas(pdf_path)
        
        # Check if image exists
        chart_file = Path(chart_path)
        if chart_file.exists():
            c.drawImage(chart_path, x, y, width=width)
        
        c.save()
        
        return pdf_path


# Simple text-based report fallback
class SimpleTextReport:
    """Simple text report generator (fallback)"""
    
    def __init__(self, output_dir: str = "output/reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_report(
        self,
        cost_data: Dict[str, Any],
        title: str = "Azure Cost Estimation Report"
    ) -> str:
        """Generate a simple text report"""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"azure_cost_report_{timestamp}.txt"
        filepath = self.output_dir / filename
        
        lines = []
        lines.append("=" * 60)
        lines.append(title)
        lines.append("=" * 60)
        lines.append("")
        
        # Date
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"Generated: {date_str}")
        lines.append("")
        
        # Summary
        summary = cost_data.get("summary", {})
        lines.append("COST SUMMARY")
        lines.append("-" * 40)
        lines.append(f"Total Monthly: ${summary.get('total_monthly_cost_usd', 0):.2f}")
        lines.append(f"Total Hourly: ${summary.get('total_hourly_cost_usd', 0):.2f}")
        lines.append(f"Currency: {summary.get('currency', 'USD')}")
        lines.append(f"Region: {summary.get('region', 'N/A')}")
        lines.append("")
        
        # Services
        lines.append("SERVICE BREAKDOWN")
        lines.append("-" * 40)
        
        for service, details in cost_data.items():
            if service == "summary":
                continue
            
            if isinstance(details, dict):
                monthly = details.get("total_monthly", 0)
                lines.append(f"{service}: ${monthly:.2f}/month")
        
        lines.append("")
        lines.append("=" * 60)
        
        # Write file
        with open(filepath, "w") as f:
            f.write("\n".join(lines))
        
        return str(filepath)


# Singleton
_pdf_generator: Optional[PDFReportGenerator] = None


def get_pdf_generator() -> PDFReportGenerator:
    """Get PDF generator instance"""
    global _pdf_generator
    if _pdf_generator is None:
        _pdf_generator = PDFReportGenerator()
    return _pdf_generator