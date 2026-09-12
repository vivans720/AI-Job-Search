# Security & Privacy Policy (Phase 53)

> **Document Classification**: Core Security, Privacy & Compliance Architecture  
> **Target Audience**: Security Auditors, Developers, Contributors, Candidates  
> **Status**: Active & Enforced

---

## 1. Local-First Architectural Principles

**AI Job Agent** is engineered from the ground up as a **local-first** application. All candidate credentials, resumes, vectors, and tracking records reside on the user's personal host machine.

### Non-Negotiable Privacy Guarantees
1. **Zero External Telemetry**: No analytics SDKs, Google Analytics, Sentry, Mixpanel, or third-party phone-home beacons exist anywhere in the backend or frontend code.
2. **Local Resume Storage Only**: Candidate resumes and raw text parsing exist purely on local disk and PostgreSQL database tables. No resume files are dispatched to external cloud file stores (e.g. AWS S3, Google Cloud Storage, Cloudinary).
3. **No Auto-Application Operations**: The system is strictly a read-only job discovery and recommendation engine. No automated form-filling, bot-assisted application submission, or headless account login automation exists.
4. **Local Embedding Execution**: Semantic embeddings (384-dimensional dense vectors) are computed locally on CPU via ONNX (`fastembed` with `BAAI/bge-small-en-v1.5`), ensuring zero cloud API costs and zero candidate text leakage during indexing.

---

## 2. Secrets Management & Credential Isolation

1. **Environment Variables**: All secret configuration items (database credentials, API keys) must be specified in `.env` (derived from `.env.example`).
2. **Git Repository Hygiene**:
   - The `.gitignore` policy strictly prohibits committing `.env`, `*.key`, `*.pem`, `*.crt`, `*.pfx`, and `service_account.json`.
   - CI and pre-commit routines execute `scripts/security_audit.py` to scan for accidental tokens (`sk-...`, `sk-ant-...`, `AIza...`, `AKIA...`).
3. **API Key Masking**:
   - Third-party cloud AI keys (OpenAI, Gemini, Anthropic, DeepSeek) entered via the onboarding wizard or stored in preferences are never serialized in full to logs, error traces, or public API responses.
   - Responses utilize `has_custom_api_key: bool` and masked string representations (`mask_secret()`, e.g. `sk-...cdef`).

---

## 3. Resume Ingestion & Storage Protections

1. **File Type & MIME Validation**:
   - Only `.pdf`, `.docx`, and `.txt` extensions are accepted.
   - Enforces magic byte checks (`%PDF` for PDF, `PK\x03\x04` for DOCX) to block disguised executable or shell payloads.
2. **Strict Size Limits**:
   - Maximum upload ceiling is clamped at 10MB (`MAX_RESUME_BYTES`), preventing memory exhaustion attacks on PDF parsers.
3. **Directory Traversal Defense**:
   - Storage operations use `sanitize_storage_path()` to guarantee that disk operations cannot break outside the designated local storage path using relative traversals (`../../`).
4. **Data Purging**:
   - Users maintain complete ownership and can delete their resume record at any time via `DELETE /api/v1/resumes/{resume_id}`.

---

## 4. Responsible & Ethical Crawling Guidelines

1. **Read-Only Discovery**: The crawler operates solely on public search and guest listing pages. It never attempts to bypass paywalls, breach password-protected portals, or crack CAPTCHA challenges.
2. **Conservative Rate Limiting**:
   - Dedicated `SourceRateLimiter` enforces strict request ceilings per platform (e.g., LinkedIn 5 req/min, Naukri 15 req/min, Internshala 20 req/min) to prevent burdening source servers.
3. **Failure Isolation via Circuit Breakers**:
   - If a source encounters blocking or perimeter challenges, the dedicated `CircuitBreaker` trips `OPEN` to back off immediately rather than slamming the domain with repeated retries.
4. **Original Canonical Links**:
   - The application routes the user directly to the employer's authentic job post (`application_url`) so the candidate applies legitimately through their own standard browser session.

---

## 5. Reporting Vulnerabilities

If you identify a security issue or privacy concern:
1. Do **not** open a public GitHub issue.
2. Report the vulnerability privately to the project maintainers.
3. Patches will be verified and released following responsible disclosure practices.
