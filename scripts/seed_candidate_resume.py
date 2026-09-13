import asyncio
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.database import async_session_factory, init_pgvector
from app.services.user_service import get_or_create_default_user
from app.services.resume_service import process_and_save_resume
from app.services.profile_service import get_candidate_profile


async def seed_resume():
    root_dir = Path(__file__).resolve().parent.parent
    private_dir = root_dir / "data" / "private"
    resume_path = private_dir / "candidate_resume.pdf"

    if not resume_path.exists():
        pdfs = sorted(private_dir.glob("*.pdf"))
        if pdfs:
            resume_path = pdfs[0]
        else:
            print(f"Error: No resume PDF found in {private_dir}. Place candidate_resume.pdf there first.")
            return

    print(f"Reading resume from {resume_path} ({resume_path.stat().st_size} bytes)...")
    file_bytes = resume_path.read_bytes()

    await init_pgvector()

    async with async_session_factory() as session:
        user = await get_or_create_default_user(session)
        print(f"Active user: {user.email} (ID: {user.id})")

        print("Extracting text and analyzing candidate intelligence via OmniRoute...")
        resume, extracted = await process_and_save_resume(
            db=session,
            user_id=user.id,
            file_bytes=file_bytes,
            filename=resume_path.name,
            file_path=str(resume_path),
        )

        profile = await get_candidate_profile(session, user.id)

        print("\n" + "=" * 60)
        print("CANDIDATE PROFILE SEEDED SUCCESSFULLY")
        print("=" * 60)
        print(f"Resume ID:           {resume.id}")
        print(f"Resume Hash:         {resume.resume_hash[:16]}...")
        print(f"Experience Level:    {profile.experience_level} ({profile.experience_years} years)")
        print(f"Target Roles:        {', '.join(profile.target_roles)}")
        print(f"Languages:           {', '.join(profile.programming_languages)}")
        print(f"Frameworks:          {', '.join(profile.frameworks)}")
        print(f"Databases:           {', '.join(profile.databases)}")
        print(f"Cloud/DevOps:        {', '.join(profile.cloud)}")
        print(f"Tools:               {', '.join(profile.tools)}")
        print(f"Skills Total:        {len(profile.skills)} canonical skills")
        print(f"Vector Dimensions:   {len(profile.embedding) if profile.embedding is not None else 0}")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(seed_resume())
