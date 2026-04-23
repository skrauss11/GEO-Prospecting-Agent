"""
GEO Visibility Snapshot — PDF generator
Branded PDF output for hot prospects using MadTech Growth brand colors.
"""

from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from fpdf import FPDF

# Brand colors (hex → RGB 0-255)
NAVY = (11, 17, 32)        # #0B1120
TERRACOTTA = (196, 93, 62)  # #C45D3E
WHITE = (255, 255, 255)
LIGHT_GRAY = (245, 245, 245)
DARK_GRAY = (80, 80, 80)
BLACK = (0, 0, 0)


class SnapshotPDF(FPDF):
    """MadTech Growth branded PDF snapshot."""

    def __init__(self):
        super().__init__(unit="mm", format="Letter")
        self.set_auto_page_break(auto=True, margin=20)
        self.set_margins(15, 15, 15)

    def header_bar(self):
        """Draw the top navy brand bar."""
        self.set_fill_color(*NAVY)
        self.rect(0, 0, 216, 25, style="F")
        self.set_text_color(*WHITE)
        self.set_font("Helvetica", "B", 16)
        self.set_xy(15, 8)
        self.cell(0, 10, "MadTech Growth", ln=False)
        self.set_font("Helvetica", "", 10)
        self.set_xy(15, 14)
        self.cell(0, 6, "GEO Visibility Snapshot", ln=False)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*DARK_GRAY)
        self.cell(0, 10, f"Prepared by MadTech Growth · {date.today().strftime('%B %d, %Y')} · Page {self.page_no()}", align="C")

    def cover_page(self, company: str, url: str, overall_score: float, grade: str, readiness: str):
        self.add_page()
        self.header_bar()

        # Large terracotta accent bar
        self.set_fill_color(*TERRACOTTA)
        self.rect(0, 25, 216, 4, style="F")

        y = 50
        self.set_xy(15, y)
        self.set_text_color(*NAVY)
        self.set_font("Helvetica", "B", 28)
        self.cell(0, 12, "GEO Visibility Snapshot", ln=True)

        self.set_xy(15, y + 18)
        self.set_font("Helvetica", "B", 18)
        self.cell(0, 10, company or urlparse(url).netloc.replace("www.", ""), ln=True)

        self.set_xy(15, y + 30)
        self.set_text_color(*DARK_GRAY)
        self.set_font("Helvetica", "", 11)
        self.cell(0, 6, url, ln=True)

        self.set_xy(15, y + 42)
        self.set_text_color(*TERRACOTTA)
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 8, f"Overall Score: {overall_score}/10   Grade: {grade}", ln=True)

        self.set_xy(15, y + 52)
        self.set_text_color(*DARK_GRAY)
        self.set_font("Helvetica", "", 11)
        self.cell(0, 6, f"LLM Readiness: {readiness}", ln=True)

        # Box with context
        self.set_xy(15, y + 68)
        self.set_fill_color(*LIGHT_GRAY)
        self.set_draw_color(*NAVY)
        self.set_line_width(0.5)
        self.rect(15, y + 68, 186, 35, style="FD")
        self.set_xy(18, y + 72)
        self.set_text_color(*NAVY)
        self.set_font("Helvetica", "B", 11)
        self.cell(0, 6, "What is GEO?", ln=True)
        self.set_xy(18, y + 79)
        self.set_font("Helvetica", "", 10)
        self.multi_cell(180, 5,
            "Generative Engine Optimization (GEO) ensures your brand is accurately "
            "represented in AI-generated answers. This snapshot measures how visible "
            "and accessible your site is to LLM crawlers and AI search engines.")

    def dimension_page(self, dimensions: dict):
        self.add_page()
        self.header_bar()
        self.set_fill_color(*TERRACOTTA)
        self.rect(0, 25, 216, 4, style="F")

        self.set_xy(15, 38)
        self.set_text_color(*NAVY)
        self.set_font("Helvetica", "B", 18)
        self.cell(0, 10, "Dimension Breakdown", ln=True)

        # Table header
        y = 55
        col_w = 90
        score_w = 30
        detail_w = 66
        row_h = 10

        self.set_fill_color(*NAVY)
        self.set_text_color(*WHITE)
        self.set_font("Helvetica", "B", 11)
        self.rect(15, y, col_w, row_h, style="F")
        self.set_xy(15, y + 2.5)
        self.cell(col_w, 6, "Dimension", align="L")

        self.rect(15 + col_w, y, score_w, row_h, style="F")
        self.set_xy(15 + col_w, y + 2.5)
        self.cell(score_w, 6, "Score", align="C")

        self.rect(15 + col_w + score_w, y, detail_w, row_h, style="F")
        self.set_xy(15 + col_w + score_w, y + 2.5)
        self.cell(detail_w, 6, "Detail", align="L")

        self.set_font("Helvetica", "", 10)
        y += row_h

        for dim_name, dim_data in dimensions.items():
            score = dim_data.get("score", 0)
            detail = dim_data.get("detail", "")
            label = dim_name.replace("_", " ").title()

            # Row background alternating
            if (y - 55) // row_h % 2 == 0:
                self.set_fill_color(*LIGHT_GRAY)
                self.rect(15, y, col_w + score_w + detail_w, row_h, style="F")

            # Score color
            if score >= 7:
                self.set_text_color(34, 139, 34)  # green
            elif score >= 5:
                self.set_text_color(255, 140, 0)  # orange
            else:
                self.set_text_color(*TERRACOTTA)

            self.set_xy(15, y + 2.5)
            self.set_font("Helvetica", "B", 10)
            self.set_text_color(*NAVY)
            self.cell(col_w, 6, label, align="L")

            self.set_xy(15 + col_w, y + 2.5)
            self.set_font("Helvetica", "B", 10)
            self.cell(score_w, 6, str(score), align="C")

            self.set_xy(15 + col_w + score_w, y + 2.5)
            self.set_font("Helvetica", "", 9)
            self.set_text_color(*DARK_GRAY)
            self.cell(detail_w, 6, detail[:35], align="L")

            y += row_h
            if y > 250:
                self.add_page()
                y = 40
                self.header_bar()

    def gaps_page(self, gaps: list[str], recommendations: list[str]):
        self.add_page()
        self.header_bar()
        self.set_fill_color(*TERRACOTTA)
        self.rect(0, 25, 216, 4, style="F")

        self.set_xy(15, 38)
        self.set_text_color(*NAVY)
        self.set_font("Helvetica", "B", 18)
        self.cell(0, 10, "Priority Gaps & Recommendations", ln=True)

        y = 55
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(*TERRACOTTA)
        self.set_xy(15, y)
        self.cell(0, 8, "Key Gaps Identified", ln=True)
        y += 10

        self.set_font("Helvetica", "", 11)
        self.set_text_color(*BLACK)
        for gap in gaps:
            self.set_xy(20, y)
            self.cell(5, 6, chr(127), align="L")  # bullet
            self.set_xy(26, y)
            self.multi_cell(175, 6, gap)
            y = self.get_y() + 3
            if y > 250:
                self.add_page()
                y = 40
                self.header_bar()

        y += 10
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(*TERRACOTTA)
        self.set_xy(15, y)
        self.cell(0, 8, "Recommendations", ln=True)
        y += 10

        self.set_font("Helvetica", "", 11)
        self.set_text_color(*BLACK)
        for rec in recommendations:
            self.set_xy(20, y)
            self.cell(5, 6, chr(127), align="L")
            self.set_xy(26, y)
            self.multi_cell(175, 6, rec)
            y = self.get_y() + 3
            if y > 250:
                self.add_page()
                y = 40
                self.header_bar()

        # CTA box
        y += 12
        self.set_fill_color(*LIGHT_GRAY)
        self.set_draw_color(*TERRACOTTA)
        self.set_line_width(0.8)
        self.rect(15, y, 186, 30, style="FD")
        self.set_xy(18, y + 4)
        self.set_text_color(*NAVY)
        self.set_font("Helvetica", "B", 11)
        self.cell(0, 6, "Next Step: GEO Audit", ln=True)
        self.set_xy(18, y + 12)
        self.set_font("Helvetica", "", 10)
        self.multi_cell(180, 5,
            "Schedule a 20-minute discovery call to review these findings in detail "
            "and build a prioritized GEO roadmap for your brand. "
            "Email: scott@madtechgrowth.com")


def generate_snapshot_pdf(result: dict, output_dir: Path) -> Path:
    """
    Generate a branded PDF snapshot from a geo_scanner result dict.
    Returns the saved file path.
    """
    company = result.get("company") or urlparse(result["url"]).netloc.replace("www.", "")
    safe_name = "".join(c if c.isalnum() else "_" for c in company).lower()[:40]
    today = date.today().isoformat()

    output_dir = output_dir / today
    output_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = output_dir / f"geo_snapshot_{safe_name}_{today}.pdf"

    pdf = SnapshotPDF()
    pdf.cover_page(
        company=company,
        url=result["url"],
        overall_score=result.get("overall_score", 0),
        grade=result.get("grade", "N/A"),
        readiness=result.get("llm_readiness", "Unknown"),
    )
    pdf.dimension_page(result.get("dimensions", {}))
    pdf.gaps_page(
        gaps=result.get("gaps", []),
        recommendations=result.get("recommendations", []),
    )
    pdf.output(str(pdf_path))
    return pdf_path
