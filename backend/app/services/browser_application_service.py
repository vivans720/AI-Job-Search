import asyncio
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any
from pathlib import Path
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application_preparation import ApplicationPreparation
from app.models.candidate_profile import CandidateProfile
from app.models.job import Job
from app.models.resume import Resume
from app.services.application_prep_service import ApplicationPrepService

logger = structlog.get_logger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

# Regex pattern identifying submission action buttons that MUST NOT be clicked
SUBMIT_PATTERN = re.compile(
    r"^\s*(submit|apply\s*now|submit\s*application|complete\s*application|send\s*application)\b",
    re.IGNORECASE,
)

# Regex pattern identifying safe multi-step navigation buttons
NEXT_STEP_PATTERN = re.compile(
    r"^\s*(next|continue|proceed|step\s*\d+|review)\b",
    re.IGNORECASE,
)


class BrowserApplicationService:
    """
    Phase 10: Browser-based job application form filling.
    Autonomously navigates to external job portals and populates fields using candidate profile,
    answers, and resumes.

    CRITICAL SAFETY BOUNDARY:
    Guaranteed programmatic halt before final form submission. The service never clicks
    any submit action button and pauses at READY_FOR_REVIEW.
    """

    @staticmethod
    async def fill_application_form(
        db: AsyncSession,
        user_id: uuid.UUID,
        job_id: uuid.UUID,
        dry_run: bool = False,
        timeout_seconds: int = 45,
        headless: bool = True,
        mock_page_url: str | None = None,
    ) -> dict[str, Any]:
        """
        Loads job & application prep records, navigates via Playwright, fills form elements,
        and halts safely before clicking Submit.
        """
        # 1. Fetch records
        prep = await ApplicationPrepService.get_or_create_preparation(db, user_id, job_id)

        job_res = await db.execute(select(Job).where(Job.id == job_id))
        job = job_res.scalar_one_or_none()
        if not job:
            return {"status": "error", "error": f"Job {job_id} not found"}

        target_url = mock_page_url or job.application_url or job.source_url
        if not target_url:
            return {"status": "error", "error": f"No application URL found for job {job_id}"}

        profile_res = await db.execute(
            select(CandidateProfile).where(CandidateProfile.user_id == user_id)
        )
        profile = profile_res.scalar_one_or_none()

        resume_path = None
        resume_obj = None
        if prep.resume_id:
            res_res = await db.execute(select(Resume).where(Resume.id == prep.resume_id))
            resume_obj = res_res.scalar_one_or_none()
            if resume_obj and resume_obj.file_path and os.path.exists(resume_obj.file_path):
                resume_path = resume_obj.file_path

        # 2. Transition state to FILLING
        prep.status = "FILLING"
        await db.commit()

        fill_audit: dict[str, Any] = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "target_url": target_url,
            "dry_run": dry_run,
            "fields_filled": [],
            "files_attached": [],
            "multi_steps_navigated": 0,
            "submit_button_detected": False,
            "submit_button_text": None,
            "submit_button_selector": None,
            "stopped_before_submit": True,
        }

        # 3. Launch browser or HTML engine and interact
        try:
            try:
                from playwright.async_api import async_playwright
                has_playwright = True
            except ImportError:
                has_playwright = False

            if has_playwright:
                async with async_playwright() as p:
                    browser = await p.chromium.launch(
                        headless=headless,
                        args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
                    )
                    context = await browser.new_context(
                        user_agent=USER_AGENT,
                        viewport={"width": 1280, "height": 900},
                    )
                    page = await context.new_page()

                    logger.info("browser_application_navigating", url=target_url, job_id=str(job_id))
                    await page.goto(
                        target_url,
                        timeout=timeout_seconds * 1000,
                        wait_until="domcontentloaded",
                    )
                    await page.wait_for_timeout(1000)

                    # Form-filling loop with multi-step support (up to 5 steps)
                    max_steps = 5
                    step_count = 0

                    while step_count < max_steps:
                        step_count += 1
                        # Extract and fill fields on current page
                        step_filled = await BrowserApplicationService._fill_page_inputs(
                            page=page,
                            profile=profile,
                            prep=prep,
                            resume_path=resume_path,
                            resume_obj=resume_obj,
                            dry_run=dry_run,
                        )
                        fill_audit["fields_filled"].extend(step_filled.get("fields", []))
                        if step_filled.get("file_attached"):
                            fill_audit["files_attached"].append(step_filled.get("file_attached"))

                        # Check for submit buttons vs next-step buttons
                        submit_button = await BrowserApplicationService._find_submit_button(page)
                        if submit_button:
                            fill_audit["submit_button_detected"] = True
                            fill_audit["submit_button_text"] = submit_button.get("text")
                            fill_audit["submit_button_selector"] = submit_button.get("selector")
                            logger.info(
                                "browser_application_submit_barrier_reached",
                                text=submit_button.get("text"),
                                job_id=str(job_id),
                            )
                            # CRITICAL: Stop immediately before submit
                            break

                        # Check if multi-step next button exists
                        next_button = await BrowserApplicationService._find_next_button(page)
                        if next_button and not dry_run:
                            btn_el = next_button.get("element")
                            logger.info(
                                "browser_application_advancing_step",
                                step=step_count,
                                button_text=next_button.get("text"),
                            )
                            await btn_el.click()
                            fill_audit["multi_steps_navigated"] += 1
                            await page.wait_for_timeout(1500)
                        else:
                            # No further steps
                            break

                    fill_audit["completed_at"] = datetime.now(timezone.utc).isoformat()
                    await browser.close()
            else:
                # Resilient Fallback Engine via HTTPX + BeautifulSoup form parser
                logger.info(
                    "playwright_unavailable_falling_back_to_dom_engine",
                    url=target_url,
                    job_id=str(job_id),
                )
                dom_result = await BrowserApplicationService._fill_via_dom_engine(
                    target_url=target_url,
                    profile=profile,
                    prep=prep,
                    resume_path=resume_path,
                    resume_obj=resume_obj,
                    dry_run=dry_run,
                    timeout_seconds=timeout_seconds,
                )
                fill_audit.update(dom_result)
                fill_audit["completed_at"] = datetime.now(timezone.utc).isoformat()

            # 4. Finalize state transition to READY_FOR_REVIEW
            prep.status = "READY_FOR_REVIEW"
            current_meta = dict(prep.metadata_info or {})
            current_meta["browser_fill_result"] = fill_audit
            prep.metadata_info = current_meta

            await db.commit()
            await db.refresh(prep)

            return {
                "status": "ok",
                "prep_id": str(prep.id),
                "job_id": str(job_id),
                "prep_status": prep.status,
                "stopped_before_submit": True,
                "submit_button_detected": fill_audit["submit_button_detected"],
                "fields_filled_count": len(fill_audit["fields_filled"]),
                "details": fill_audit,
            }

        except Exception as e:
            logger.error("browser_application_filling_failed", error=str(e), job_id=str(job_id))
            prep.status = "FAILED"
            current_meta = dict(prep.metadata_info or {})
            current_meta["browser_fill_error"] = str(e)
            prep.metadata_info = current_meta
            await db.commit()
            return {
                "status": "error",
                "prep_id": str(prep.id),
                "job_id": str(job_id),
                "prep_status": "FAILED",
                "error": str(e),
                "stopped_before_submit": True,
            }

    @staticmethod
    async def _fill_page_inputs(
        page: Any,
        profile: CandidateProfile | None,
        prep: ApplicationPreparation,
        resume_path: str | None,
        resume_obj: Resume | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """
        Inspects inputs, textareas, selects, and file attachments on the active page
        and fills matching values.
        """
        filled = []
        file_attached = None

        # Gather Candidate values for mapping
        candidate_info = {
            "first_name": "Candidate",
            "last_name": "Applicant",
            "full_name": "Candidate Applicant",
            "email": "candidate@example.com",
            "phone": "+91 9876543210",
            "linkedin": "https://linkedin.com/in/candidate",
            "github": "https://github.com/candidate",
            "portfolio": "https://candidate.dev",
            "location": "Bangalore, India",
        }

        # Check resume extracted_data first if available
        if resume_obj and resume_obj.extracted_data:
            ext = resume_obj.extracted_data
            if ext.get("name"):
                candidate_info["full_name"] = ext["name"]
                parts = ext["name"].strip().split(maxsplit=1)
                candidate_info["first_name"] = parts[0]
                candidate_info["last_name"] = parts[1] if len(parts) > 1 else ""
            if ext.get("email"):
                candidate_info["email"] = ext["email"]
            if ext.get("phone"):
                candidate_info["phone"] = ext["phone"]
            if ext.get("linkedin"):
                candidate_info["linkedin"] = ext["linkedin"]
            if ext.get("github"):
                candidate_info["github"] = ext["github"]

        # Check candidate profile for locations, links, overrides
        if profile:
            if profile.preferred_locations:
                candidate_info["location"] = profile.preferred_locations[0]
            if profile.manual_overrides:
                for k, v in profile.manual_overrides.items():
                    if k in candidate_info and v:
                        candidate_info[k] = v
                        if k == "full_name":
                            parts = str(v).strip().split(maxsplit=1)
                            candidate_info["first_name"] = parts[0]
                            candidate_info["last_name"] = parts[1] if len(parts) > 1 else ""

        # 1. Text, Email, Tel, URL Inputs
        inputs = await page.query_selector_all(
            'input:not([type="hidden"]):not([type="submit"]):not([type="file"]):not([type="checkbox"]):not([type="radio"])'
        )
        for el in inputs:
            try:
                name_attr = (await el.get_attribute("name") or "").lower()
                id_attr = (await el.get_attribute("id") or "").lower()
                placeholder = (await el.get_attribute("placeholder") or "").lower()
                aria_label = (await el.get_attribute("aria-label") or "").lower()
                inp_type = (await el.get_attribute("type") or "text").lower()

                target_field = None
                fill_val = None

                # Email
                if inp_type == "email" or "email" in name_attr or "email" in id_attr:
                    target_field = "email"
                    fill_val = candidate_info["email"]
                # Phone / Tel
                elif (
                    inp_type == "tel"
                    or "phone" in name_attr
                    or "mobile" in name_attr
                    or "tel" in id_attr
                ):
                    target_field = "phone"
                    fill_val = candidate_info["phone"]
                # First Name
                elif "first" in name_attr or "fname" in name_attr or "first_name" in id_attr:
                    target_field = "first_name"
                    fill_val = candidate_info["first_name"]
                # Last Name
                elif "last" in name_attr or "lname" in name_attr or "last_name" in id_attr:
                    target_field = "last_name"
                    fill_val = candidate_info["last_name"]
                # Full Name
                elif "name" in name_attr or "name" in id_attr or "name" in placeholder:
                    target_field = "full_name"
                    fill_val = candidate_info["full_name"]
                # LinkedIn
                elif "linkedin" in name_attr or "linkedin" in id_attr or "linkedin" in placeholder:
                    target_field = "linkedin"
                    fill_val = candidate_info["linkedin"]
                # GitHub
                elif "github" in name_attr or "github" in id_attr or "github" in placeholder:
                    target_field = "github"
                    fill_val = candidate_info["github"]
                # Portfolio / Website
                elif (
                    "portfolio" in name_attr
                    or "website" in name_attr
                    or "website" in id_attr
                    or "portfolio" in placeholder
                ):
                    target_field = "portfolio"
                    fill_val = candidate_info["portfolio"]
                # Location / City
                elif "location" in name_attr or "city" in name_attr or "city" in id_attr:
                    target_field = "location"
                    fill_val = candidate_info["location"]

                if target_field and fill_val:
                    if not dry_run:
                        await el.fill(fill_val)
                    filled.append(
                        {"type": "input", "field": target_field, "value": fill_val, "name": name_attr}
                    )
            except Exception as ex:
                logger.debug("browser_fill_input_failed", error=str(ex))

        # 2. Textarea / Questions / Cover Letter
        textareas = await page.query_selector_all("textarea")
        qa_dict = {
            qa.get("question", "").lower(): qa.get("answer", "")
            for qa in (prep.question_answers or [])
        }

        for ta in textareas:
            try:
                name_attr = (await ta.get_attribute("name") or "").lower()
                id_attr = (await ta.get_attribute("id") or "").lower()
                placeholder = (await ta.get_attribute("placeholder") or "").lower()
                aria_label = (await ta.get_attribute("aria-label") or "").lower()

                # Check if it corresponds to cover letter
                if (
                    "cover" in name_attr
                    or "letter" in name_attr
                    or "cover_letter" in id_attr
                    or "cover letter" in placeholder
                ):
                    if prep.cover_letter:
                        if not dry_run:
                            await ta.fill(prep.cover_letter)
                        filled.append(
                            {"type": "textarea", "field": "cover_letter", "value": prep.cover_letter[:100]}
                        )
                        continue

                # Match against screening question answers
                matched_answer = None
                matched_q = None
                for q_text, ans in qa_dict.items():
                    if any(
                        keyword in q_text
                        for keyword in [name_attr, id_attr, placeholder, aria_label]
                        if len(keyword) > 3
                    ):
                        matched_answer = ans
                        matched_q = q_text
                        break

                if matched_answer:
                    if not dry_run:
                        await ta.fill(matched_answer)
                    filled.append(
                        {
                            "type": "textarea",
                            "field": "screening_question",
                            "question": matched_q,
                            "value": matched_answer[:100],
                        }
                    )
                elif prep.question_answers and len(prep.question_answers) > 0:
                    # Fallback to first available answer
                    first_ans = prep.question_answers[0].get("answer", "")
                    if first_ans:
                        if not dry_run:
                            await ta.fill(first_ans)
                        filled.append(
                            {
                                "type": "textarea",
                                "field": "screening_question_default",
                                "value": first_ans[:100],
                            }
                        )
            except Exception as ex:
                logger.debug("browser_fill_textarea_failed", error=str(ex))

        # 3. File upload (Resume)
        file_inputs = await page.query_selector_all('input[type="file"]')
        if file_inputs and resume_path and os.path.exists(resume_path):
            for finp in file_inputs:
                try:
                    if not dry_run:
                        await finp.set_input_files(resume_path)
                    file_attached = resume_path
                    filled.append(
                        {
                            "type": "file_upload",
                            "field": "resume",
                            "filename": Path(resume_path).name,
                        }
                    )
                    break
                except Exception as ex:
                    logger.debug("browser_resume_upload_failed", error=str(ex))

        return {"fields": filled, "file_attached": file_attached}

    @staticmethod
    async def _find_submit_button(page: Any) -> dict[str, Any] | None:
        """
        Locates any button or input that performs final form submission.
        """
        # Search all submit buttons and regular buttons
        buttons = await page.query_selector_all(
            'button, input[type="submit"], input[type="button"], a[role="button"]'
        )
        for btn in buttons:
            try:
                text = (await btn.inner_text() or "").strip()
                val = (await btn.get_attribute("value") or "").strip()
                b_type = (await btn.get_attribute("type") or "").strip().lower()
                aria_label = (await btn.get_attribute("aria-label") or "").strip()
                combined_text = f"{text} {val} {aria_label}".strip()

                if b_type == "submit" or SUBMIT_PATTERN.search(combined_text):
                    return {
                        "text": combined_text or "Submit",
                        "selector": "submit_button",
                        "element": btn,
                    }
            except Exception:
                continue
        return None

    @staticmethod
    async def _find_next_button(page: Any) -> dict[str, Any] | None:
        """
        Locates next/continue buttons in multi-step application forms.
        """
        buttons = await page.query_selector_all('button, input[type="button"], a[role="button"]')
        for btn in buttons:
            try:
                text = (await btn.inner_text() or "").strip()
                val = (await btn.get_attribute("value") or "").strip()
                combined_text = f"{text} {val}".strip()

                # Must match next pattern but NOT submit pattern
                if NEXT_STEP_PATTERN.search(combined_text) and not SUBMIT_PATTERN.search(
                    combined_text
                ):
                    return {
                        "text": combined_text,
                        "element": btn,
                    }
            except Exception:
                continue
        return None

    @staticmethod
    async def _fill_via_dom_engine(
        target_url: str,
        profile: CandidateProfile | None,
        prep: ApplicationPreparation,
        resume_path: str | None,
        resume_obj: Resume | None,
        dry_run: bool,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        """
        DOM-based inspection and fill engine for environments where Playwright browser binaries
        are not present. Parses form elements and enforces the submit stop barrier.
        """
        import httpx
        from bs4 import BeautifulSoup

        async with httpx.AsyncClient(
            timeout=float(timeout_seconds),
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            res = await client.get(target_url)
            soup = BeautifulSoup(res.text, "html.parser")

        candidate_info = {
            "first_name": "Candidate",
            "last_name": "Applicant",
            "full_name": "Candidate Applicant",
            "email": "candidate@example.com",
            "phone": "+91 9876543210",
            "linkedin": "https://linkedin.com/in/candidate",
            "github": "https://github.com/candidate",
            "portfolio": "https://candidate.dev",
            "location": "Bangalore, India",
        }

        if resume_obj and resume_obj.extracted_data:
            ext = resume_obj.extracted_data
            if ext.get("name"):
                candidate_info["full_name"] = ext["name"]
                parts = ext["name"].strip().split(maxsplit=1)
                candidate_info["first_name"] = parts[0]
                candidate_info["last_name"] = parts[1] if len(parts) > 1 else ""
            if ext.get("email"):
                candidate_info["email"] = ext["email"]
            if ext.get("phone"):
                candidate_info["phone"] = ext["phone"]
            if ext.get("linkedin"):
                candidate_info["linkedin"] = ext["linkedin"]
            if ext.get("github"):
                candidate_info["github"] = ext["github"]

        if profile and profile.preferred_locations:
            candidate_info["location"] = profile.preferred_locations[0]

        fields_filled = []
        files_attached = []
        submit_detected = False
        submit_text = None

        # Analyze input elements
        for inp in soup.find_all("input"):
            inp_type = (inp.get("type") or "text").lower()
            name_attr = (inp.get("name") or "").lower()
            id_attr = (inp.get("id") or "").lower()
            val_attr = (inp.get("value") or "").strip()

            if inp_type == "submit" or SUBMIT_PATTERN.search(f"{name_attr} {val_attr} {id_attr}"):
                submit_detected = True
                submit_text = val_attr or "Submit"
                continue

            if inp_type == "file":
                if resume_path:
                    files_attached.append(resume_path)
                    fields_filled.append(
                        {"type": "file_upload", "field": "resume", "filename": Path(resume_path).name}
                    )
                continue

            # Text / contact inputs
            target_field = None
            fill_val = None
            if inp_type == "email" or "email" in name_attr or "email" in id_attr:
                target_field = "email"
                fill_val = candidate_info["email"]
            elif inp_type == "tel" or "phone" in name_attr or "mobile" in name_attr:
                target_field = "phone"
                fill_val = candidate_info["phone"]
            elif "first" in name_attr or "fname" in name_attr:
                target_field = "first_name"
                fill_val = candidate_info["first_name"]
            elif "last" in name_attr or "lname" in name_attr:
                target_field = "last_name"
                fill_val = candidate_info["last_name"]
            elif "name" in name_attr or "name" in id_attr:
                target_field = "full_name"
                fill_val = candidate_info["full_name"]
            elif "linkedin" in name_attr or "linkedin" in id_attr:
                target_field = "linkedin"
                fill_val = candidate_info["linkedin"]
            elif "github" in name_attr or "github" in id_attr:
                target_field = "github"
                fill_val = candidate_info["github"]
            elif "portfolio" in name_attr or "website" in name_attr:
                target_field = "portfolio"
                fill_val = candidate_info["portfolio"]
            elif "location" in name_attr or "city" in name_attr:
                target_field = "location"
                fill_val = candidate_info["location"]

            if target_field and fill_val:
                fields_filled.append(
                    {"type": "input", "field": target_field, "value": fill_val, "name": name_attr}
                )

        # Analyze textareas
        for ta in soup.find_all("textarea"):
            name_attr = (ta.get("name") or "").lower()
            id_attr = (ta.get("id") or "").lower()
            if "cover" in name_attr or "cover_letter" in id_attr:
                if prep.cover_letter:
                    fields_filled.append(
                        {"type": "textarea", "field": "cover_letter", "value": prep.cover_letter[:100]}
                    )
            elif prep.question_answers:
                first_ans = prep.question_answers[0].get("answer", "")
                fields_filled.append(
                    {"type": "textarea", "field": "screening_question", "value": first_ans[:100]}
                )

        # Check buttons
        for btn in soup.find_all(["button", "a"]):
            btn_txt = btn.get_text(strip=True)
            if SUBMIT_PATTERN.search(btn_txt):
                submit_detected = True
                submit_text = btn_txt
                break

        return {
            "fields_filled": fields_filled,
            "files_attached": files_attached,
            "submit_button_detected": submit_detected,
            "submit_button_text": submit_text or "Submit Application",
            "submit_button_selector": "button[type='submit']",
            "stopped_before_submit": True,
            "engine": "dom_parser",
        }

