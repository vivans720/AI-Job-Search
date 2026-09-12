#!/usr/bin/env python3
"""
scripts/security_audit.py

Security & Privacy audit scanner for AI Job Agent.
Checks:
1. Hardcoded API keys and secrets in codebase (sk-, sk-ant-, AIza, AKIA, private keys).
2. Private candidate files accidentally committed / tracked in git.
3. Proper .gitignore enforcement for uploads, resumes, private directories.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

SECRET_PATTERNS = [
    (r"sk-[a-zA-Z0-9_-]{20,}", "OpenAI API Key / Token"),
    (r"sk-ant-[a-zA-Z0-9_-]{20,}", "Anthropic API Key"),
    (r"AIza[0-9A-Za-z-_]{35}", "Google API Key"),
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID"),
    (r"ghp_[a-zA-Z0-9]{36}", "GitHub Personal Access Token"),
    (r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----", "Private Key Header"),
]

IGNORE_DIRS = {
    ".git",
    "node_modules",
    ".next",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

IGNORE_FILES = {
    "package-lock.json",
    ".env.example",
    "security_audit.py",
}

UNTRACKED_ALLOWED_PRIVATE = {
    "data/private",
    "backend/data/resumes",
    "storage/resumes",
    "uploads",
}


def check_git_tracked_private_artifacts(root_dir: Path) -> list[str]:
    """Check whether git is tracking any private resume or credential artifacts."""
    findings = []
    try:
        cmd = ["git", "ls-files"]
        env = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null")
        res = subprocess.run(cmd, cwd=root_dir, capture_output=True, text=True, env=env)
        if res.returncode == 0:
            tracked = res.stdout.splitlines()
            for f in tracked:
                lower = f.lower()
                if lower.endswith((".pdf", ".docx", ".doc", ".pem", ".key", ".pfx", ".p12")) and "test" not in lower:
                    findings.append(f"Git-tracked private file detected: {f}")
                for priv in UNTRACKED_ALLOWED_PRIVATE:
                    if f.startswith(priv) and not f.endswith(".gitkeep"):
                        findings.append(f"Git-tracked private file in {priv}: {f}")
    except Exception as e:
        findings.append(f"Could not run git ls-files: {e}")
    return findings


def audit_workspace(root_dir: Path) -> tuple[list[str], list[str]]:
    secret_findings: list[str] = []
    privacy_findings = check_git_tracked_private_artifacts(root_dir)

    for path in root_dir.rglob("*"):
        if not path.is_file():
            continue

        parts = set(path.parts)
        if parts & IGNORE_DIRS:
            continue

        rel_path = str(path.relative_to(root_dir))
        if path.name in IGNORE_FILES:
            continue

        # Skip local untracked private files if git ignores them
        if any(rel_path.startswith(p) for p in UNTRACKED_ALLOWED_PRIVATE):
            continue

        # Scan text files for secret patterns
        if path.suffix in [".py", ".ts", ".tsx", ".js", ".json", ".yaml", ".yml", ".md", ".env"]:
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for pattern, desc in SECRET_PATTERNS:
                matches = re.finditer(pattern, content)
                for m in matches:
                    matched_str = m.group(0)
                    if any(dummy in matched_str.lower() for dummy in ["dummy", "mock", "test", "example", "placeholder", "your-key"]):
                        continue
                    masked = matched_str[:6] + "..." + matched_str[-4:] if len(matched_str) > 10 else "***"
                    secret_findings.append(f"Potential secret [{desc}] in {rel_path}: {masked}")

    return secret_findings, privacy_findings


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    print(f"Scanning workspace for security & privacy hygiene: {root}")
    secrets, privacy = audit_workspace(root)

    status = 0
    if privacy:
        print(f"\n❌ Found {len(privacy)} candidate privacy issue(s):")
        for p in privacy:
            print(f"  - {p}")
        status = 1
    else:
        print("\n✅ Zero tracked candidate resume/private data artifacts in git.")

    if secrets:
        print(f"\n❌ Found {len(secrets)} potential secret leak(s):")
        for s in secrets:
            print(f"  - {s}")
        status = 1
    else:
        print("✅ Zero hardcoded secret patterns found in code.")

    return status


if __name__ == "__main__":
    sys.exit(main())
