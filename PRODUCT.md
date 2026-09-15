# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary users are early-career software engineers and freshers (0–2 years of experience) in India navigating an overcrowded entry-level tech job market. They face rampant stale job postings, ghost jobs, and opaque keyword-matching algorithms.

## Product Purpose

AI Job Agent India exists to eliminate the noise in entry-level tech hiring across India by finding genuinely active opportunities (< 24 hours old), transparently scoring alignment against candidate skills rather than pedigree or job title inflation, and tracking application workflows without taking control away from the candidate.

## Positioning

Deterministic 24-hour freshness enforcement anchored in Asia/Kolkata (IST) combined with transparent, non-destructive skill-first matching (65% required skills, 10% preferred, 10% transferable, 5% experience, 5% location, 5% preferences) and zero-cloud embedding privacy. Unlike typical aggregators or automated spam bots, jobs are never dropped silently, and auto-applying without candidate consent is strictly prohibited.

## Operating Context

- Web application accessed primarily via desktop/laptop browsers (Next.js 15.1, React 19, Tailwind CSS).
- Interacts with Indian hiring platforms (Internshala, Naukri, LinkedIn) and AI agent clients via Model Context Protocol (MCP stdio/SSE).
- Local-first AI options (Ollama, FastEmbed 384d vectors) with configurable fallback to cloud LLMs (Gemini, Claude, OpenAI, Groq).

## Capabilities and Constraints

- **Strict Freshness**: Dynamic relative timestamps parsed to UTC and filtered against strict <= 24h IST window.
- **Recall-First Matching**: Non-destructive ranking; lower-scoring jobs remain visible with transparent score breakdowns.
- **Application Integrity**: State machine tracks stages (`DISCOVERED`, `SAVED`, `VIEWED`, `APPLIED`, `INTERVIEW`, `REJECTED`, `OFFER`); no unauthorized automated submissions.
- **Local Vectors**: Dense vector embeddings generated locally via FastEmbed (`BAAI/bge-small-en-v1.5`) at zero API cost.

## Brand Commitments

- **Name**: AI Job Agent India
- **Tone**: Focused, transparent, calm, empowering, and pragmatic.
- **Commitment**: No dark patterns, no fake freshness metrics, no false promises of auto-applications.

## Evidence on Hand

- Verified ingestion pipelines from Internshala, Naukri, and LinkedIn.
- Active PostgreSQL 16 + pgvector storage and Redis queue.
- Working Next.js dashboard with Discovery Radar (`/jobs`), Pipeline Tracker (`/saved`), Profile/Resume parser (`/profile`, `/resume`), and AI Diagnostics (`/ai-provider`).

## Product Principles

1. **Freshness is Truth**: Stale jobs waste fresher hope; jobs older than 24 hours are rejected by default.
2. **Skill Over Pedigree**: Code capability and transferable skills outrank inflated titles or college brand.
3. **The Candidate Retains Agency**: Present transparent facts and scores; the candidate decides when and where to apply.
4. **Resilient & Privacy-Conscious**: Default to local execution and zero-cloud cost where possible.
