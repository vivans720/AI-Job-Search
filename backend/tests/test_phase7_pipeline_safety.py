import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.job import Job
from app.models.preference import Preference
from app.models.user import User
from app.services.agent_approval_service import AgentApprovalService
from app.services.job_service import VALID_STATUSES


def test_valid_statuses_includes_phase7_stages():
    """Verify that READY_TO_APPLY and PREPARING are in valid backend statuses."""
    assert "READY_TO_APPLY" in VALID_STATUSES
    assert "PREPARING" in VALID_STATUSES
    assert "APPLIED" in VALID_STATUSES
    assert "SAVED" in VALID_STATUSES


@pytest.mark.asyncio
async def test_update_pipeline_status_applied_strictly_gated_even_when_policy_autonomous():
    """
    Core Phase 7 Invariant:
    Even when update_pipeline_status autonomy policy is set to 'autonomous',
    requesting status 'APPLIED' must NEVER directly mutate state.
    It MUST return APPROVAL_REQUIRED and queue an approval request.
    """
    from tools.job_tools import handle_update_application_status

    job_id = uuid.uuid4()
    mock_db = AsyncMock()
    mock_user = User(id=uuid.uuid4(), email="candidate@example.com")
    mock_job = Job(id=job_id, title="AI Engineer", company_name="Acme AI", is_active=True)

    with patch("tools.job_tools.async_session_factory") as mock_session_factory, \
         patch("tools.job_tools.get_or_create_default_user", new_callable=AsyncMock) as mock_get_user, \
         patch("tools.job_tools.ensure_active_run", new_callable=AsyncMock) as mock_ensure_run, \
         patch("tools.job_tools.AgentApprovalService.check_is_action_autonomous", new_callable=AsyncMock) as mock_check_auto, \
         patch("tools.job_tools.AgentApprovalService.create_approval_request", new_callable=AsyncMock) as mock_create_approval, \
         patch("tools.job_tools.save_or_update_job_status", new_callable=AsyncMock) as mock_save_job:

        mock_session_factory.return_value.__aenter__.return_value = mock_db
        mock_get_user.return_value = mock_user
        mock_ensure_run.return_value = uuid.uuid4()
        # Even if candidate set policy to autonomous
        mock_check_auto.return_value = True

        mock_job_res = MagicMock()
        mock_job_res.scalar_one_or_none.return_value = mock_job
        mock_db.execute.return_value = mock_job_res

        mock_approval_obj = MagicMock()
        mock_approval_obj.id = uuid.uuid4()
        mock_create_approval.return_value = mock_approval_obj

        res = await handle_update_application_status(
            job_id=str(job_id),
            status="APPLIED",
            notes="Applied via website",
        )

        assert res["status"] == "APPROVAL_REQUIRED"
        assert res["target_status"] == "APPLIED"
        assert res["approval_id"] == str(mock_approval_obj.id)
        assert "strictly requires candidate confirmation" in res["message"]

        # Critical: Direct DB mutation must NOT have been called
        mock_save_job.assert_not_called()
        mock_create_approval.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_pipeline_status_ready_to_apply_autonomous_when_policy_allows():
    """
    Verify that moving to READY_TO_APPLY can be autonomous if policy allows.
    """
    from tools.job_tools import handle_update_application_status

    job_id = uuid.uuid4()
    mock_db = AsyncMock()
    mock_user = User(id=uuid.uuid4(), email="candidate@example.com")
    mock_job = Job(id=job_id, title="AI Engineer", company_name="Acme AI", is_active=True)

    with patch("tools.job_tools.async_session_factory") as mock_session_factory, \
         patch("tools.job_tools.get_or_create_default_user", new_callable=AsyncMock) as mock_get_user, \
         patch("tools.job_tools.ensure_active_run", new_callable=AsyncMock) as mock_ensure_run, \
         patch("tools.job_tools.AgentApprovalService.check_is_action_autonomous", new_callable=AsyncMock) as mock_check_auto, \
         patch("tools.job_tools.AgentApprovalService.create_approval_request", new_callable=AsyncMock) as mock_create_approval, \
         patch("tools.job_tools.save_or_update_job_status", new_callable=AsyncMock) as mock_save_job:

        mock_session_factory.return_value.__aenter__.return_value = mock_db
        mock_get_user.return_value = mock_user
        mock_check_auto.return_value = True

        mock_job_res = MagicMock()
        mock_job_res.scalar_one_or_none.return_value = mock_job
        mock_db.execute.return_value = mock_job_res

        mock_save_job.return_value = {
            "id": str(uuid.uuid4()),
            "job_id": str(job_id),
            "status": "READY_TO_APPLY",
        }

        res = await handle_update_application_status(
            job_id=str(job_id),
            status="READY_TO_APPLY",
            notes="Application materials prepared",
        )

        assert res["status"] == "READY_TO_APPLY"
        mock_save_job.assert_awaited_once()
        mock_create_approval.assert_not_called()


@pytest.mark.asyncio
async def test_approval_resolution_executes_applied_status():
    """
    Verify that when user approves the queued approval request,
    the APPLIED status is successfully persisted by AgentApprovalService.
    """
    user_id = uuid.uuid4()
    job_id = uuid.uuid4()
    approval_id = uuid.uuid4()

    mock_db = AsyncMock()

    from app.models.agent_approval import AgentApproval
    from datetime import datetime, timezone, timedelta

    approval = AgentApproval(
        id=approval_id,
        user_id=user_id,
        action_type="UPDATE_PIPELINE_STATUS",
        status="PENDING",
        job_id=job_id,
        payload={"job_id": str(job_id), "status": "APPLIED", "notes": "Confirmed application"},
        reason="Candidate submitted application",
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )

    apprv_res = MagicMock()
    apprv_res.scalar_one_or_none.return_value = approval
    mock_db.execute.return_value = apprv_res

    with patch("app.services.agent_approval_service.save_or_update_job_status", new_callable=AsyncMock) as mock_save:
        mock_save.return_value = {"id": str(job_id), "status": "APPLIED"}

        res = await AgentApprovalService.resolve_approval(
            db=mock_db,
            user_id=user_id,
            approval_id=approval_id,
            decision="APPROVE",
            resolution_notes="Confirmed I applied",
        )

        assert res["status"] == "APPROVED"
        assert res["executed_count"] == 1
        assert str(job_id) in res["executed_job_ids"]
        mock_save.assert_awaited_once_with(
            db=mock_db,
            user_id=user_id,
            job_id=job_id,
            status="APPLIED",
            notes="Confirmed application",
        )
