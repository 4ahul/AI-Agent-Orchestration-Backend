"""
Script to generate a sample PDF for testing the pipeline.
Run: python sample/generate_sample.py
"""
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.units import cm
except ImportError:
    print("Install reportlab: pip install reportlab")
    exit(1)

import os

OUTPUT = os.path.join(os.path.dirname(__file__), "sample_report.pdf")

doc = SimpleDocTemplate(OUTPUT, pagesize=A4, title="Q1 2024 Business Report")
styles = getSampleStyleSheet()
story = []

# Title
story.append(Paragraph("Global AI Solutions — Q1 2024 Business Report", styles["Title"]))
story.append(Spacer(1, 0.5 * cm))

# Executive Summary
story.append(Paragraph("1. Executive Summary", styles["Heading1"]))
story.append(Paragraph(
    "Global AI Solutions achieved exceptional growth in Q1 2024, with total revenue increasing by 42% "
    "year-over-year to ₹12.4 crore. The AI Venture Factory successfully launched two new "
    "enterprise products: AgentCore and DataLens. The company expanded its presence into "
    "Singapore and the UAE, bringing the total market count to 5.",
    styles["BodyText"]
))
story.append(Spacer(1, 0.3 * cm))

# Financial Performance
story.append(Paragraph("2. Financial Performance", styles["Heading1"]))
story.append(Paragraph(
    "Revenue growth was primarily driven by enterprise subscriptions (68%) and professional "
    "services (32%). Infrastructure costs rose by 18% due to increased GPU compute demand. "
    "EBITDA margin improved to 24% from 19% in Q4 2023.",
    styles["BodyText"]
))

# Table
data = [
    ["Metric", "Q1 2024", "Q4 2023", "Change"],
    ["Revenue (₹ Cr)", "12.4", "8.7", "+42%"],
    ["Gross Margin", "68%", "61%", "+7pp"],
    ["EBITDA Margin", "24%", "19%", "+5pp"],
    ["Active Customers", "340", "218", "+56%"],
]
t = Table(data, colWidths=[5 * cm, 3 * cm, 3 * cm, 3 * cm])
t.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f0f0")]),
    ("ALIGN", (1, 0), (-1, -1), "CENTER"),
]))
story.append(Spacer(1, 0.3 * cm))
story.append(t)
story.append(Spacer(1, 0.5 * cm))

# Product Updates
story.append(Paragraph("3. Product Updates", styles["Heading1"]))
story.append(Paragraph(
    "AgentCore v2.0 was released in February 2024, featuring multi-agent orchestration "
    "capabilities powered by LangChain and CrewAI. DataLens, our AI-driven analytics platform, "
    "entered beta with 42 enterprise pilot customers. Contact: product@globalaisolutions.ai",
    styles["BodyText"]
))
story.append(Spacer(1, 0.3 * cm))

# Outlook
story.append(Paragraph("4. Q2 2024 Outlook", styles["Heading1"]))
story.append(Paragraph(
    "The company targets ₹16 crore revenue in Q2 2024. Key initiatives include the launch "
    "of AgentCore Enterprise Edition, expansion into Japan, and hiring 35 engineers across "
    "Mumbai and Bangalore offices. For more information: candidate@example.com",
    styles["BodyText"]
))

doc.build(story)
print(f"✅ Sample PDF created: {OUTPUT}")
