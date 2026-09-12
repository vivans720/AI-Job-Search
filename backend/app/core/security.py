"""
Core Security & Privacy Utilities (Phase 53)
Provides:
- API key masking for logs, error messages, and responses.
- Safe resume upload validation (MIME-types, magic headers, size limits, file path sanitization).
- Directory traversal guards for local storage.
"""
import os
import re
import uuid
from pathlib import Path
from fastapi import HTTPException, UploadFile, status

# Allowed MIME types and extensions for candidate resumes
ALLOWED_RESUME_EXTENSIONS = {".pdf", ".docx", ".txt"}
ALLOWED_RESUME_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}

# Maximum resume upload limit: 10MB
MAX_RESUME_BYTES = 10 * 1024 * 1024

# PDF Magic Bytes: %PDF- (0x25 0x50 0x44 0x46)
# ZIP / DOCX Magic Bytes: PK.. (0x50 0x4B 0x03 0x04)
PDF_MAGIC = b"%PDF"
DOCX_MAGIC = b"PK\x03\x04"


def mask_secret(secret: str | None, visible_prefix: int = 3, visible_suffix: int = 4) -> str:
    """
    Masks a sensitive API key or token for logging and responses.
    Example: 'sk-proj-1234567890abcdef' -> 'sk-...cdef'
    """
    if not secret:
        return ""
    secret = secret.strip()
    if len(secret) <= (visible_prefix + visible_suffix):
        return "***"
    return f"{secret[:visible_prefix]}...{secret[-visible_suffix:]}"


def validate_resume_upload(filename: str, file_bytes: bytes) -> tuple[str, str]:
    """
    Validates resume file extension, file size, and magic bytes to prevent upload of malicious payloads.
    Returns sanitized extension and a safe, random disk filename (UUID-based).
    """
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty resume file uploaded")

    if len(file_bytes) > MAX_RESUME_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Resume file size exceeds maximum limit of {MAX_RESUME_BYTES // (1024 * 1024)}MB",
        )

    # Sanitize base filename and extract lower extension
    safe_base = os.path.basename(filename)
    ext = os.path.splitext(safe_base)[1].lower()

    if ext not in ALLOWED_RESUME_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file format '{ext}'. Allowed formats: PDF, DOCX, TXT",
        )

    # Validate magic bytes for binary files
    if ext == ".pdf":
        if not file_bytes.startswith(PDF_MAGIC):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid PDF file format (corrupted header)",
            )
    elif ext == ".docx":
        if not file_bytes.startswith(DOCX_MAGIC):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid DOCX file format (corrupted header)",
            )

    # Generate isolated random filename
    secure_filename = f"{uuid.uuid4().hex}{ext}"
    return ext, secure_filename


def sanitize_storage_path(base_dir: str | Path, relative_path: str) -> Path:
    """
    Guards against directory traversal attacks (e.g. '../../etc/passwd').
    Ensures target path resolves strictly within base_dir.
    """
    base = Path(base_dir).resolve()
    target = (base / relative_path).resolve()
    if not str(target).startswith(str(base)):
        raise ValueError("Directory traversal attempt detected")
    return target
