import pytest
from pathlib import Path
from fastapi import HTTPException
from app.core.security import (
    mask_secret,
    validate_resume_upload,
    sanitize_storage_path,
    PDF_MAGIC,
    DOCX_MAGIC,
    MAX_RESUME_BYTES,
)


def test_mask_secret():
    assert mask_secret(None) == ""
    assert mask_secret("") == ""
    assert mask_secret("short") == "***"
    assert mask_secret("sk-proj-1234567890abcdef") == "sk-...cdef"
    assert mask_secret("AIzaSyDummyKey1234567890") == "AIz...7890"


def test_validate_resume_upload_valid_pdf():
    valid_pdf_bytes = PDF_MAGIC + b"-1.5\n%Valid minimal pdf content"
    ext, safe_name = validate_resume_upload("my_resume.pdf", valid_pdf_bytes)
    assert ext == ".pdf"
    assert safe_name.endswith(".pdf")
    assert len(safe_name) > 30  # UUID hex length


def test_validate_resume_upload_valid_docx():
    valid_docx_bytes = DOCX_MAGIC + b"\x00\x00minimal docx test bytes"
    ext, safe_name = validate_resume_upload("candidate.docx", valid_docx_bytes)
    assert ext == ".docx"
    assert safe_name.endswith(".docx")


def test_validate_resume_upload_disguised_file_fails():
    # File named .pdf but contains arbitrary script or executable header
    fake_pdf = b"#!/bin/bash\necho hello"
    with pytest.raises(HTTPException) as exc_info:
        validate_resume_upload("exploit.pdf", fake_pdf)
    assert exc_info.value.status_code == 400
    assert "Invalid PDF" in exc_info.value.detail


def test_validate_resume_upload_unsupported_extension():
    with pytest.raises(HTTPException) as exc_info:
        validate_resume_upload("exploit.exe", b"MZ\x90\x00executable")
    assert exc_info.value.status_code == 415


def test_validate_resume_upload_exceeds_size_limit():
    huge_bytes = PDF_MAGIC + b"0" * (MAX_RESUME_BYTES + 1024)
    with pytest.raises(HTTPException) as exc_info:
        validate_resume_upload("huge.pdf", huge_bytes)
    assert exc_info.value.status_code == 413


def test_sanitize_storage_path_valid(tmp_path: Path):
    safe_path = sanitize_storage_path(tmp_path, "resumes/user_123.pdf")
    assert str(safe_path).startswith(str(tmp_path.resolve()))
    assert safe_path.name == "user_123.pdf"


def test_sanitize_storage_path_traversal_attack(tmp_path: Path):
    with pytest.raises(ValueError) as exc_info:
        sanitize_storage_path(tmp_path, "../../etc/passwd")
    assert "Directory traversal" in str(exc_info.value)
