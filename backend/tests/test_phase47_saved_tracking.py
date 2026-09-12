import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock
from app.services.job_service import save_or_update_job_status, unsave_job, get_saved_jobs_for_user
from app.models.job import Job
from app.models.saved_job import SavedJob


@pytest.mark.asyncio
async def test_save_or_update_job_status_saved():
    """Verify save_or_update_job_status creates or updates with SAVED."""
    user_id = uuid.uuid4()
    job_id = uuid.uuid4()

    mock_job = Job(
        id=job_id,
        title="Software Engineer",
        company_name="Acme Corp",
        application_url="https://example.com/apply",
        source="linkedin",
    )

    mock_db = AsyncMock()
    mock_db.add = MagicMock()

    # When querying for Job
    mock_res_job = MagicMock()
    mock_res_job.scalar_one_or_none.return_value = mock_job

    # When querying for existing SavedJob (None initially)
    mock_res_saved = MagicMock()
    mock_res_saved.scalar_one_or_none.return_value = None

    mock_db.execute.side_effect = [mock_res_job, mock_res_saved]

    result = await save_or_update_job_status(
        mock_db,
        user_id=user_id,
        job_id=job_id,
        status="SAVED",
        notes="High interest",
    )

    assert result["job_id"] == str(job_id)
    assert result["status"] == "SAVED"
    assert result["notes"] == "High interest"
    assert mock_db.commit.called


@pytest.mark.asyncio
async def test_save_or_update_job_status_applied():
    """Verify marking a job as APPLIED."""
    user_id = uuid.uuid4()
    job_id = uuid.uuid4()

    mock_job = Job(
        id=job_id,
        title="Full Stack Developer",
        company_name="Beta Inc",
        application_url="https://example.com/apply-now",
        source="naukri",
    )

    mock_existing_saved = SavedJob(
        id=uuid.uuid4(),
        user_id=user_id,
        job_id=job_id,
        status="SAVED",
    )

    mock_db = AsyncMock()
    mock_res_job = MagicMock()
    mock_res_job.scalar_one_or_none.return_value = mock_job

    mock_res_saved = MagicMock()
    mock_res_saved.scalar_one_or_none.return_value = mock_existing_saved

    mock_db.execute.side_effect = [mock_res_job, mock_res_saved]

    result = await save_or_update_job_status(
        mock_db,
        user_id=user_id,
        job_id=job_id,
        status="APPLIED",
        notes="Directly applied via site",
    )

    assert result["job_id"] == str(job_id)
    assert result["status"] == "APPLIED"
    assert mock_existing_saved.status == "APPLIED"
    assert mock_db.commit.called


@pytest.mark.asyncio
async def test_unsave_job_found():
    """Verify unsave_job removes the tracked job and returns True."""
    user_id = uuid.uuid4()
    job_id = uuid.uuid4()

    mock_existing_saved = SavedJob(
        id=uuid.uuid4(),
        user_id=user_id,
        job_id=job_id,
        status="SAVED",
    )

    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_existing_saved
    mock_db.execute.return_value = mock_res

    removed = await unsave_job(mock_db, user_id=user_id, job_id=job_id)

    assert removed is True
    assert mock_db.delete.called
    assert mock_db.commit.called


@pytest.mark.asyncio
async def test_unsave_job_not_found():
    """Verify unsave_job returns False when job was not tracked."""
    user_id = uuid.uuid4()
    job_id = uuid.uuid4()

    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res

    removed = await unsave_job(mock_db, user_id=user_id, job_id=job_id)

    assert removed is False
    assert not mock_db.delete.called
