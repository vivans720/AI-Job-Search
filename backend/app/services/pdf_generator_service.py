import html
import json
import logging
from datetime import datetime, timezone
from typing import Any
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)


class PDFGeneratorService:
    @staticmethod
    def _escape(text: Any) -> str:
        if text is None:
            return ""
        return html.escape(str(text))

    @classmethod
    def render_resume_html(
        cls,
        candidate_data: dict[str, Any],
        job_data: dict[str, Any],
        tailored_data: dict[str, Any] | None = None,
        mode: str = "EXISTING",
    ) -> str:
        name = cls._escape(candidate_data.get("name") or "Candidate")
        email = cls._escape(candidate_data.get("email") or "")
        phone = cls._escape(candidate_data.get("phone") or "")
        location = cls._escape(candidate_data.get("location") or "")
        summary = cls._escape(candidate_data.get("summary") or "")

        if mode == "TAILORED" and tailored_data and tailored_data.get("tailored_summary"):
            summary = cls._escape(tailored_data.get("tailored_summary"))

        contact_items = [item for item in [email, phone, location] if item]
        contact_line = " &nbsp;|&nbsp; ".join(contact_items)

        # Categorized Skills formatting
        skill_groups = {}
        if mode == "TAILORED" and tailored_data and tailored_data.get("categorized_skills"):
            skill_groups = tailored_data.get("categorized_skills") or {}
        elif candidate_data.get("categorized_skills"):
            skill_groups = candidate_data.get("categorized_skills") or {}

        # Fallback to category grouping from candidate taxonomy if not structured
        if not skill_groups:
            raw_skills = candidate_data.get("skills") or []
            if raw_skills:
                skill_groups = {"Technical Skills": raw_skills}

        skills_html = ""
        for category, sk_list in skill_groups.items():
            if sk_list and isinstance(sk_list, list):
                cat_clean = cls._escape(str(category).strip())
                items_clean = cls._escape(", ".join(str(s) for s in sk_list if s))
                if items_clean:
                    skills_html += f"""
                    <div class="skill-row">
                        <span class="skill-category">{cat_clean}:</span>
                        <span class="skill-items">{items_clean}</span>
                    </div>
                    """

        # Experience formatting with per-role tailored bullets and budget
        work_experience = candidate_data.get("work_experience") or []
        tailored_exp_map = {}
        if mode == "TAILORED" and tailored_data and tailored_data.get("experience"):
            for exp_item in tailored_data.get("experience", []):
                idx = exp_item.get("source_experience_index")
                if idx is not None:
                    tailored_exp_map[int(idx)] = exp_item.get("selected_bullets") or []

        experience_html = ""
        # Budget experience display (max 4 jobs, prioritize chronological/recent)
        for i, exp in enumerate(work_experience[:4]):
            title = cls._escape(exp.get("title") or exp.get("role") or "")
            comp = cls._escape(exp.get("company") or "")
            duration = cls._escape(exp.get("duration") or exp.get("dates") or "")
            location_val = cls._escape(exp.get("location") or "")

            sub_header_parts = [p for p in [comp, location_val] if p]
            comp_loc_str = " &nbsp;|&nbsp; ".join(sub_header_parts)

            # Bullet selection
            bullets = []
            if mode == "TAILORED" and i in tailored_exp_map:
                bullets = [cls._escape(b.get("content") if isinstance(b, dict) else str(b)) for b in tailored_exp_map[i]]
            else:
                desc = exp.get("description") or exp.get("bullets") or []
                if isinstance(desc, str):
                    bullets = [cls._escape(desc)]
                elif isinstance(desc, list):
                    bullets = [cls._escape(b) for b in desc]

            # Dynamic line budget per role (3 for primary, 2-3 for secondary)
            bullet_limit = 4 if i == 0 else 3
            bullet_items_html = "".join(f"<li>{b}</li>" for b in bullets[:bullet_limit] if b)

            experience_html += f"""
            <div class="item">
                <div class="item-header">
                    <span class="item-title">{title}</span>
                    <span class="item-date">{duration}</span>
                </div>
                <div class="item-sub-header">
                    <span class="item-company">{comp_loc_str}</span>
                </div>
                <ul class="bullets">
                    {bullet_items_html}
                </ul>
            </div>
            """

        # Projects formatting with tech highlights
        projects = candidate_data.get("projects") or []
        tailored_proj_map = {}
        if mode == "TAILORED" and tailored_data and tailored_data.get("projects"):
            for proj_item in tailored_data.get("projects", []):
                p_idx = proj_item.get("source_project_index")
                if p_idx is not None:
                    tailored_proj_map[int(p_idx)] = proj_item.get("selected_bullets") or []

        projects_html = ""
        # Budget projects based on work experience volume
        max_proj = 2 if len(work_experience) >= 2 else 3
        for i, proj in enumerate(projects[:max_proj]):
            proj_title = cls._escape(proj.get("name") or proj.get("title") or "")
            tech_raw = proj.get("technologies") or proj.get("tech_stack") or []
            if isinstance(tech_raw, list):
                tech_str = cls._escape(", ".join(tech_raw))
            else:
                tech_str = cls._escape(str(tech_raw))

            bullets = []
            if mode == "TAILORED" and i in tailored_proj_map:
                bullets = [cls._escape(b.get("content") if isinstance(b, dict) else str(b)) for b in tailored_proj_map[i]]
            else:
                desc = proj.get("description") or proj.get("bullets") or []
                if isinstance(desc, str):
                    bullets = [cls._escape(desc)]
                elif isinstance(desc, list):
                    bullets = [cls._escape(b) for b in desc]

            tech_tag = f"<span class='tech-pill'>{tech_str}</span>" if tech_str else ""
            proj_bullets_html = "".join(f"<li>{b}</li>" for b in bullets[:2] if b)

            projects_html += f"""
            <div class="item">
                <div class="item-header">
                    <span class="item-title">{proj_title}</span>
                    {tech_tag}
                </div>
                <ul class="bullets">
                    {proj_bullets_html}
                </ul>
            </div>
            """

        # Education
        education = candidate_data.get("education") or []
        education_html = ""
        for edu in education[:2]:
            degree = cls._escape(edu.get("degree") or "")
            institution = cls._escape(edu.get("institution") or edu.get("university") or edu.get("school") or "")
            year = cls._escape(edu.get("graduation_year") or edu.get("year") or edu.get("duration") or "")
            grade = cls._escape(edu.get("grade") or "")
            degree_str = f"{degree} - {institution}"
            if grade:
                degree_str += f" ({grade})"

            education_html += f"""
            <div class="item education-item">
                <div class="item-header">
                    <span class="item-title">{degree_str}</span>
                    <span class="item-date">{year}</span>
                </div>
            </div>
            """

        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @page {{
    size: A4 portrait;
    margin: 8mm 10mm 8mm 10mm;
  }}
  * {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    color: #1e293b;
    background: #ffffff;
    line-height: 1.35;
    font-size: 9pt;
  }}
  .header {{
    text-align: center;
    border-bottom: 2px solid #0f172a;
    padding-bottom: 4px;
    margin-bottom: 6px;
  }}
  .name {{
    font-size: 16pt;
    font-weight: 700;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    color: #0f172a;
    margin-bottom: 2px;
  }}
  .contact {{
    font-size: 8.5pt;
    color: #475569;
    font-weight: 500;
  }}
  .section {{
    margin-bottom: 6px;
  }}
  .section-title {{
    font-size: 9.5pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: #0f172a;
    border-bottom: 1px solid #cbd5e1;
    padding-bottom: 1.5px;
    margin-bottom: 3.5px;
  }}
  .summary-text {{
    font-size: 8.8pt;
    color: #334155;
    text-align: justify;
    line-height: 1.3;
  }}
  .skill-row {{
    font-size: 8.8pt;
    line-height: 1.3;
    margin-bottom: 1.5px;
  }}
  .skill-category {{
    font-weight: 600;
    color: #0f172a;
  }}
  .skill-items {{
    color: #334155;
  }}
  .item {{
    margin-bottom: 4px;
  }}
  .item-header {{
    display: flex;
    justify-content: space-between;
    align-items: baseline;
  }}
  .item-title {{
    font-weight: 600;
    font-size: 9.2pt;
    color: #0f172a;
  }}
  .item-date {{
    font-size: 8.3pt;
    color: #475569;
    font-weight: 500;
  }}
  .item-sub-header {{
    font-size: 8.4pt;
    color: #334155;
    font-weight: 500;
    margin-top: 0.5px;
  }}
  .item-company {{
    font-style: italic;
  }}
  .tech-pill {{
    font-size: 8.2pt;
    color: #475569;
    font-style: italic;
  }}
  .bullets {{
    margin-left: 14px;
    margin-top: 1.5px;
  }}
  .bullets li {{
    font-size: 8.6pt;
    color: #334155;
    margin-bottom: 1.5px;
    line-height: 1.25;
  }}
  .education-item {{
    margin-bottom: 2px;
  }}
</style>
</head>
<body>
  <div class="header">
    <div class="name">{name}</div>
    <div class="contact">{contact_line}</div>
  </div>

  {"<div class='section'><div class='section-title'>Professional Summary</div><p class='summary-text'>" + summary + "</p></div>" if summary else ""}

  {"<div class='section'><div class='section-title'>Technical Competencies</div>" + skills_html + "</div>" if skills_html.strip() else ""}

  {"<div class='section'><div class='section-title'>Work Experience</div>" + experience_html + "</div>" if experience_html.strip() else ""}

  {"<div class='section'><div class='section-title'>Technical Projects</div>" + projects_html + "</div>" if projects_html.strip() else ""}

  {"<div class='section'><div class='section-title'>Education</div>" + education_html + "</div>" if education_html.strip() else ""}
</body>
</html>"""

    @classmethod
    def render_cover_letter_html(
        cls,
        candidate_data: dict[str, Any],
        job_data: dict[str, Any],
        cover_letter_data: dict[str, Any] | str,
    ) -> str:
        name = cls._escape(candidate_data.get("name") or "Applicant")
        email = cls._escape(candidate_data.get("email") or "")
        phone = cls._escape(candidate_data.get("phone") or "")
        location = cls._escape(candidate_data.get("location") or "")

        company = cls._escape(job_data.get("company_name") or job_data.get("company") or "Hiring Team")
        role = cls._escape(job_data.get("title") or "Position")

        contact_items = [item for item in [email, phone, location] if item]
        contact_line = " &nbsp;|&nbsp; ".join(contact_items)

        # Generate actual calendar date server-side (e.g. September 23, 2026)
        formatted_date = datetime.now(timezone.utc).strftime("%B %d, %Y")

        paragraphs = []
        if isinstance(cover_letter_data, dict):
            # Clean structured sections
            opening = cover_letter_data.get("opening")
            evidence = cover_letter_data.get("evidence_paragraph")
            company_conn = cover_letter_data.get("company_connection")
            closing = cover_letter_data.get("closing")
            for sec in [opening, evidence, company_conn, closing]:
                if sec and str(sec).strip():
                    paragraphs.append(cls._escape(str(sec).strip()))
        else:
            # Clean string fallback
            raw_text = str(cover_letter_data or "")
            for p in raw_text.split("\n\n"):
                cleaned = p.replace("**", "").strip()
                # Skip duplicate header if generated
                if (
                    cleaned.startswith(name)
                    or cleaned.startswith("---")
                    or cleaned.startswith("Date:")
                    or cleaned.startswith("Dear ")
                    or cleaned.startswith("To ")
                    or cleaned.startswith("Sincerely")
                ):
                    continue
                if cleaned:
                    paragraphs.append(cls._escape(cleaned))

        content_html = "".join(f"<p>{p}</p>" for p in paragraphs)

        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @page {{
    size: A4 portrait;
    margin: 18mm 20mm 18mm 20mm;
  }}
  * {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: #1e293b;
    background: #ffffff;
    line-height: 1.5;
    font-size: 10pt;
  }}
  .header {{
    border-bottom: 2px solid #0f172a;
    padding-bottom: 8px;
    margin-bottom: 16px;
  }}
  .name {{
    font-size: 18pt;
    font-weight: 700;
    letter-spacing: 0.5px;
    color: #0f172a;
    text-transform: uppercase;
    margin-bottom: 3px;
  }}
  .contact {{
    font-size: 9pt;
    color: #475569;
  }}
  .target {{
    margin-bottom: 16px;
    font-size: 9.5pt;
    color: #334155;
    line-height: 1.4;
  }}
  .salutation {{
    font-weight: 600;
    color: #0f172a;
    margin-bottom: 12px;
  }}
  .body-content {{
    text-align: justify;
  }}
  .body-content p {{
    margin-bottom: 12px;
    line-height: 1.45;
  }}
  .sign-off {{
    margin-top: 18px;
    font-size: 10pt;
    color: #0f172a;
    line-height: 1.4;
  }}
</style>
</head>
<body>
  <div class="header">
    <div class="name">{name}</div>
    <div class="contact">{contact_line}</div>
  </div>
  <div class="target">
    <div><strong>Date:</strong> {formatted_date}</div>
    <div><strong>Hiring Team:</strong> {company}</div>
    <div><strong>Role:</strong> {role}</div>
  </div>
  <div class="salutation">
    Dear Hiring Team at {company},
  </div>
  <div class="body-content">
    {content_html}
  </div>
  <div class="sign-off">
    Sincerely,<br>
    <strong>{name}</strong>
  </div>
</body>
</html>"""

    @classmethod
    async def generate_pdf_from_html(cls, html_content: str) -> bytes:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_content(html_content, wait_until="networkidle")
            pdf_bytes = await page.pdf(
                format="A4",
                print_background=True,
                prefer_css_page_size=True,
            )
            await browser.close()
            return pdf_bytes
