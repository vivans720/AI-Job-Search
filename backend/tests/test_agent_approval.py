import uuid
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.agent_approval import AgentApproval
from app.models.job import Job
from app.models.preference import Preference
from app.models.saved_job import SavedJob
from app.models.user import User
from app.services.agent_approval_service import AgentApprovalService


@pytest.mark.asyncio
async def test_autonomy_policy_defaults_and_updates():
    user_id = uuid.uuid4()
    mock_db = AsyncMock()

    # Preference does not exist yet
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res

    # Check defaults
    policy = await AgentApprovalService.get_autonomy_policy(mock_db, user_id)
    assert policy["search"] == "autonomous"
    assert policy["save_job"] == "approval_required"
    assert policy["dismiss_job"] == "approval_required"
    assert policy["update_pipeline_status"] == "approval_required"

    # Update policy
    pref = Preference(user_id=user_id, autonomy_policy={})
    mock_res.scalar_one_or_none.return_value = pref

    updated = await AgentApprovalService.update_autonomy_policy(
        mock_db, user_id, {"save_job": "autonomous"}
    )
    assert updated["save_job"] == "autonomous"
    assert pref.autonomy_policy["save_job"] == "autonomous"


@pytest.mark.asyncio
async def test_create_and_resolve_approval_approve():
    user_id = uuid.uuid4()
    job_id = uuid.uuid4()
    approval_id = uuid.uuid4()

    mock_db = AsyncMock()

    # No duplicate pending
    dup_res = MagicMock()
    dup_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = dup_res

    approval = await AgentApprovalService.create_approval_request(
        db=mock_db,
        user_id=user_id,
        action_type="SAVE_JOB",
        job_id=job_id,
        payload={"job_id": str(job_id), "notes": "Top match"},
        reason="Agent recommended",
    )
    assert approval.status == "PENDING"
    assert approval.job_id == job_id
    assert approval.action_type == "SAVE_JOB"

    # Test resolve APPROVE
    approval.id = approval_id
    apprv_res = MagicMock()
    apprv_res.scalar_one_or_none.return_value = approval
    mock_db.execute.return_value = apprv_res

    with patch("app.services.agent_approval_service.save_or_update_job_status", new_callable=AsyncMock) as mock_save:
        mock_save.return_value = {"id": str(job_id), "status": "SAVED"}

        res = await AgentApprovalService.resolve_approval(
            db=mock_db,
            user_id=user_id,
            approval_id=approval_id,
            decision="APPROVE",
        )

        assert res["status"] == "APPROVED"
        assert res["executed_count"] == 1
        assert str(job_id) in res["executed_job_ids"]
        assert approval.status == "APPROVED"
        mock_save.assert_awaited_once_with(
            db=mock_db,
            user_id=user_id,
            job_id=job_id,
            status="SAVED",
            notes="Top match",
        )


@pytest.mark.asyncio
async def test_create_and_resolve_approval_reject():
    user_id = uuid.uuid4()
    job_id = uuid.uuid4()
    approval_id = uuid.uuid4()

    mock_db = AsyncMock()

    approval = AgentApproval(
        id=approval_id,
        user_id=user_id,
        action_type="SAVE_JOB",
        status="PENDING",
        job_id=job_id,
        payload={"job_id": str(job_id)},
        reason="Agent recommended",
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )

    apprv_res = MagicMock()
    apprv_res.scalar_one_or_none.return_value = approval
    mock_db.execute.return_value = apprv_res

    with patch("app.services.agent_approval_service.save_or_update_job_status", new_callable=AsyncMock) as mock_save:
        res = await AgentApprovalService.resolve_approval(
            db=mock_db,
            user_id=user_id,
            approval_id=approval_id,
            decision="REJECT",
            resolution_notes="Dismissed by candidate",
        )

        assert res["status"] == "REJECTED"
        assert res["executed_count"] == 0
        assert approval.status == "REJECTED"
        mock_save.assert_not_called()


@pytest.mark.asyncio
async def test_batch_save_partial_approval():
    user_id = uuid.uuid4()
    job1_id = uuid.uuid4()
    job2_id = uuid.uuid4()
    approval_id = uuid.uuid4()

    mock_db = AsyncMock()

    approval = AgentApproval(
        id=approval_id,
        user_id=user_id,
        action_type="BATCH_SAVE",
        status="PENDING",
        job_id=None,
        payload={"job_ids": [str(job1_id), str(job2_id)], "notes": "Batch"},
        reason="Agent recommendations",
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )

    apprv_res = MagicMock()
    apprv_res.scalar_one_or_none.return_value = approval
    mock_db.execute.return_value = apprv_res

    with patch("app.services.agent_approval_service.save_or_update_job_status", new_callable=AsyncMock) as mock_save:
        res = await AgentApprovalService.resolve_approval(
            db=mock_db,
            user_id=user_id,
            approval_id=approval_id,
            decision="APPROVE",
            partial_job_ids=[str(job1_id)],  # User selects only 1 of 2
        )

        assert res["status"] == "APPROVED"
        assert res["executed_count"] == 1
        assert str(job1_id) in res["executed_job_ids"]
        assert str(job2_id) not in res["executed_job_ids"]
        assert mock_save.await_count == 1


@pytest.mark.asyncio
async def test_expired_approval_cannot_resolve():
    user_id = uuid.uuid4()
    approval_id = uuid.uuid4()
    mock_db = AsyncMock()

    past = datetime.now(timezone.utc) - timedelta(hours=2)
    approval = AgentApproval(
        id=approval_id,
        user_id=user_id,
        action_type="SAVE_JOB",
        status="PENDING",
        created_at=past - timedelta(hours=24),
        expires_at=past,
    )

    apprv_res = MagicMock()
    apprv_res.scalar_one_or_none.return_value = approval
    mock_db.execute.return_value = apprv_res

    with pytest.raises(ValueError, match="expired"):
        await AgentApprovalService.resolve_approval(
            db=mock_db,
            user_id=user_id,
            approval_id=approval_id,
            decision="APPROVE",
        )
