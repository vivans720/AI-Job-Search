#!/usr/bin/env python3
import asyncio
import json
import sys
from pathlib import Path

# Add backend and mcp-server directories
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
mcp_dir = root_dir / "mcp-server"

for p in [str(backend_dir), str(mcp_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from server import server
from app.intelligence.llm_provider import get_llm_provider


async def run_agent_workflow(user_query: str | None = None):
    print("=" * 65)
    print("🤖 JOB AGENT INDIA — AUTONOMOUS DISCOVERY SESSION")
    print("=" * 65)

    # 1. Fetch Candidate Profile via MCP Tool
    print("\n[Step 1] Invoking MCP tool: get_candidate_profile()...")
    profile_res = await server.call_tool("get_candidate_profile", {})
    profile_data = json.loads(profile_res.content[0].text)

    print(f"   ✓ Candidate Profile Loaded:")
    print(f"     • Target Roles:    {', '.join(profile_data.get('target_roles', []))}")
    print(f"     • Excluded Roles:  {', '.join(profile_data.get('excluded_roles', []))}")
    print(f"     • Experience:      {profile_data.get('experience_level')} ({profile_data.get('experience_years')} yrs)")
    print(f"     • Canonical Skills: {len(profile_data.get('skills', []))} skills on profile")
    print(f"     • Locations:       {', '.join(profile_data.get('preferred_locations', []))}")

    # 2. Search Fresh Jobs via MCP Tool
    print("\n[Step 2] Invoking MCP tool: search_jobs(freshness_hours=24)...")
    search_args = {
        "query": user_query,
        "roles": profile_data.get("target_roles"),
        "freshness_hours": 24,
        "limit": 20,
    }
    search_res = await server.call_tool("search_jobs", search_args)
    search_data = json.loads(search_res.content[0].text)
    jobs = search_data.get("jobs", [])
    print(f"   ✓ Found {len(jobs)} fresh opportunities within the strict 24h window (Timezone: Asia/Kolkata).")

    if not jobs:
        print("   ℹ No fresh jobs found matching current profile.")
        return

    # 3. Rank Jobs via MCP Tool
    print("\n[Step 3] Invoking MCP tool: rank_jobs()...")
    job_ids = [j["id"] for j in jobs]
    rank_res = await server.call_tool("rank_jobs", {"job_ids": job_ids})
    ranked_jobs = json.loads(rank_res.content[0].text).get("ranked_jobs", [])

    print(f"   ✓ Evaluated 6-dimension match for {len(ranked_jobs)} listings.")

    # 4. Synthesize Recommendations via OmniRoute LLM
    print("\n[Step 4] Formulating recommendations with OmniRoute LLM...")
    llm = get_llm_provider()

    top_matches = ranked_jobs[:5]
    prompt_payload = {
        "candidate": {
            "target_roles": profile_data.get("target_roles"),
            "skills": profile_data.get("skills", [])[:15],
            "experience_years": profile_data.get("experience_years"),
        },
        "recommendations": top_matches,
    }

    system_prompt = (
        "You are Hermes Job Agent India. Synthesize a professional, high-signal briefing for the candidate.\n"
        "Rules:\n"
        "1. Never claim to apply automatically. The candidate applies manually.\n"
        "2. Only recommend jobs verified fresh within 24h.\n"
        "3. Highlight why each job matches the candidate's skills and target roles.\n"
        "4. Include direct application links.\n"
        "5. Keep the tone concise, actionable, and encouraging."
    )

    user_message = f"Here are the top ranked matches from the job engine:\n{json.dumps(prompt_payload, indent=2)}\n\nPlease summarize these opportunities for me."

    try:
        summary = await llm.complete(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
        )
    except Exception as e:
        summary = f"(LLM synthesis unavailable: {e}. Outputting deterministic rankings directly.)"

    print("\n" + "=" * 65)
    print("📋 RECOMMENDED OPPORTUNITIES (VERIFIED FRESH &le; 24 HOURS)")
    print("=" * 65)
    print(summary)

    print("\n" + "-" * 65)
    print("📌 DIRECT APPLICATION URLS (MANUAL APPLICATION ONLY):")
    print("-" * 65)
    for idx, j in enumerate(top_matches, start=1):
        print(f"{idx}. {j['title']} @ {j['company']} ({j['score']}% {j['recommendation']})")
        print(f"   🔗 Direct Link: {j['application_url']}")
        print(f"   Matched Skills: {', '.join(j.get('matched_skills', []))}")
        if j.get("missing_skills"):
            print(f"   Growth Areas:   {', '.join(j.get('missing_skills', []))}")
        print()

    print("=" * 65)
    print("✓ Workflow complete. Open links in your browser to submit applications.")
    print("=" * 65)


if __name__ == "__main__":
    query_arg = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(run_agent_workflow(query_arg))
