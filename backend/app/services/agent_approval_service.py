import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models.agent_approval import AgentApproval
from app.models.agent_activity import AgentEvent
from app.models.job import Job
from app.models.preference import Preference
from app.services.agent_activity_service import AgentActivityService
from app.services.job_service import get_job_by_id, save_or_update_job_status

logger = structlog.get_logger(__name__)

DEFAULT_AUTONOMY_POLICY = {
    "search": "autonomous",
    "analyze": "autonomous",
    "save_job": "approval_required",
    "dismiss_job": "approval_required",
    "update_pipeline_status": "approval_required",
}


class AgentApprovalService:
    @staticmethod
    async def get_autonomy_policy(db: AsyncSession, user_id: uuid.UUID) -> dict[str, str]:
        stmt = select(Preference).where(Preference.user_id == user_id)
        res = await db.execute(stmt)
        pref = res.scalar_one_or_none()
        if not pref or not pref.autonomy_policy:
            return dict(DEFAULT_AUTONOMY_POLICY)
        policy = dict(DEFAULT_AUTONOMY_POLICY)
        policy.update(pref.autonomy_policy)
        return policy

    @staticmethod
    async def update_autonomy_policy(
        db: AsyncSession, user_id: uuid.UUID, policy_updates: dict[str, str]
    ) -> dict[str, str]:
        stmt = select(Preference).where(Preference.user_id == user_id)
        res = await db.execute(stmt)
        pref = res.scalar_one_or_none()
        if not pref:
            pref = Preference(user_id=user_id, autonomy_policy=DEFAULT_AUTONOMY_POLICY)
            db.add(pref)

        current = dict(pref.autonomy_policy or DEFAULT_AUTONOMY_POLICY)
        for k, v in policy_updates.items():
            if v in ("autonomous", "approval_required"):
                current[k] = v
        pref.autonomy_policy = current
        await db.commit()
        await db.refresh(pref)
        return pref.autonomy_policy

    @staticmethod
    async def check_is_action_autonomous(
        db: AsyncSession, user_id: uuid.UUID, action_name: str
    ) -> bool:
        policy = await AgentApprovalService.get_autonomy_policy(db, user_id)
        mode = policy.get(action_name, "approval_required")
        return mode == "autonomous"

    @staticmethod
    async def create_approval_request(
        db: AsyncSession,
        user_id: uuid.UUID,
        action_type: str,
        payload: dict[str, Any],
        reason: str | None = None,
        job_id: uuid.UUID | None = None,
        run_id: uuid.UUID | None = None,
        expires_hours: int = 24,
    ) -> AgentApproval:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=expires_hours)

        # Check duplicate pending request for same job and action
        if job_id:
            dup_stmt = select(AgentApproval).where(
                AgentApproval.user_id == user_id,
                AgentApproval.action_type == action_type,
                AgentApproval.job_id == job_id,
                AgentApproval.status == "PENDING",
            )
            dup_res = await db.execute(dup_stmt)
            existing = dup_res.scalar_one_or_none()
            if existing:
                return existing

        approval = AgentApproval(
            user_id=user_id,
            run_id=run_id,
            action_type=action_type,
            status="PENDING",
            job_id=job_id,
            payload=payload,
            reason=reason,
            created_at=now,
            expires_at=expires_at,
        )
        db.add(approval)
        await db.commit()
        await db.refresh(approval)

        # Log pending event if run_id exists
        if run_id:
            await AgentActivityService.log_event(
                db=db,
                run_id=run_id,
                event_type="status_update",
                action_summary=f"Action '{action_type}' paused awaiting user approval",
                tool_name=action_type.lower(),
                payload={"approval_id": str(approval.id), "reason": reason},
            )

        return approval

    @staticmethod
    async def list_approvals(
        db: AsyncSession,
        user_id: uuid.UUID,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        # Auto-expire outdated requests
        now = datetime.now(timezone.utc)
        stmt = select(AgentApproval).where(AgentApproval.user_id == user_id)
        if status:
            stmt = stmt.where(AgentApproval.status == status.upper())
        stmt = stmt.order_by(desc(AgentApproval.created_at)).limit(limit)

        result = await db.execute(stmt)
        approvals = result.scalars().all()

        output = []
        for apprv in approvals:
            # Check expiration
            if apprv.status == "PENDING" and apprv.expires_at and apprv.expires_at < now:
                apprv.status = "EXPIRED"
                await db.commit()
                await db.refresh(apprv)

            item = {
                "id": apprv.id,
                "user_id": apprv.user_id,
                "run_id": apprv.run_id,
                "action_type": apprv.action_type,
                "status": apprv.status,
                "job_id": apprv.job_id,
                "payload": apprv.payload or {},
                "reason": apprv.reason,
                "created_at": apprv.created_at,
                "expires_at": apprv.expires_at,
                "resolved_at": apprv.resolved_at,
                "resolution_notes": apprv.resolution_notes,
                "job_summary": None,
            }

            if apprv.job_id:
                job_data = await get_job_by_id(db, apprv.job_id)
                if job_data:
                    item["job_summary"] = {
                        "id": job_data["id"],
                        "title": job_data["title"],
                        "company": job_data["company"],
                        "location": job_data["location"],
                        "salary": job_data["salary"],
                        "application_url": job_data["application_url"],
                    }

            output.append(item)

        return output

    @staticmethod
    async def resolve_approval(
        db: AsyncSession,
        user_id: uuid.UUID,
        approval_id: uuid.UUID,
        decision: str,
        partial_job_ids: list[str] | None = None,
        resolution_notes: str | None = None,
    ) -> dict[str, Any]:
        upper_decision = decision.upper()
        if upper_decision not in ("APPROVE", "REJECT"):
            raise ValueError(f"Invalid decision '{decision}'. Must be 'APPROVE' or 'REJECT'")

        stmt = select(AgentApproval).where(
            AgentApproval.id == approval_id, AgentApproval.user_id == user_id
        )
        res = await db.execute(stmt)
        approval = res.scalar_one_or_none()
        if not approval:
            raise ValueError(f"Approval request {approval_id} not found")

        now = datetime.now(timezone.utc)
        if approval.status != "PENDING":
            raise ValueError(f"Approval request is already {approval.status} and cannot be resolved")

        if approval.expires_at and approval.expires_at < now:
            approval.status = "EXPIRED"
            await db.commit()
            raise ValueError("Approval request has expired")

        executed_job_ids: list[str] = []

        if upper_decision == "REJECT":
            approval.status = "REJECTED"
            approval.resolved_at = now
            approval.resolution_notes = resolution_notes or "Rejected by candidate"
            await db.commit()
            await db.refresh(approval)

            if approval.run_id:
                await AgentActivityService.log_event(
                    db=db,
                    run_id=approval.run_id,
                    event_type="milestone",
                    action_summary=f"User rejected agent action {approval.action_type}",
                    tool_name=approval.action_type.lower(),
                    payload={"approval_id": str(approval.id), "status": "REJECTED"},
                )

            return {
                "approval_id": approval.id,
                "status": "REJECTED",
                "decision": "REJECT",
                "executed_count": 0,
                "executed_job_ids": [],
                "notes": approval.resolution_notes,
            }

        # APPROVE decision: execute the requested mutation
        action_type = approval.action_type.upper()
        payload = approval.payload or {}

        if action_type == "SAVE_JOB":
            target_job_id = approval.job_id or (
                uuid.UUID(payload["job_id"]) if "job_id" in payload else None
            )
            if target_job_id:
                await save_or_update_job_status(
                    db=db,
                    user_id=user_id,
                    job_id=target_job_id,
                    status="SAVED",
                    notes=payload.get("notes"),
                )
                executed_job_ids.append(str(target_job_id))

        elif action_type == "DISMISS_JOB":
            target_job_id = approval.job_id or (
                uuid.UUID(payload["job_id"]) if "job_id" in payload else None
            )
            if target_job_id:
                await save_or_update_job_status(
                    db=db,
                    user_id=user_id,
                    job_id=target_job_id,
                    status="IGNORED",
                    notes=payload.get("reason"),
                )
                executed_job_ids.append(str(target_job_id))

        elif action_type == "UPDATE_PIPELINE_STATUS":
            target_job_id = approval.job_id or (
                uuid.UUID(payload["job_id"]) if "job_id" in payload else None
            )
            target_status = payload.get("status", "SAVED")
            if target_job_id:
                await save_or_update_job_status(
                    db=db,
                    user_id=user_id,
                    job_id=target_job_id,
                    status=target_status,
                    notes=payload.get("notes"),
                )
                executed_job_ids.append(str(target_job_id))

        elif action_type == "BATCH_SAVE":
            raw_ids = payload.get("job_ids", [])
            # Support partial selection if user picked a subset
            selected_ids = partial_job_ids if partial_job_ids is not None else raw_ids
            for jid_str in selected_ids:
                try:
                    jid = uuid.UUID(jid_str)
                    await save_or_update_job_status(
                        db=db,
                        user_id=user_id,
                        job_id=jid,
                        status="SAVED",
                        notes=payload.get("notes", "Agent recommended"),
                    )
                    executed_job_ids.append(str(jid))
                except Exception as e:
                    logger.warning("batch_save_partial_job_failed", job_id=jid_str, error=str(e))

        approval.status = "APPROVED"
        approval.resolved_at = now
        approval.resolution_notes = resolution_notes or f"Approved {len(executed_job_ids)} items"
        await db.commit()
        await db.refresh(approval)

        if approval.run_id:
            await AgentActivityService.log_event(
                db=db,
                run_id=approval.run_id,
                event_type="milestone",
                action_summary=f"User approved agent action {approval.action_type} ({len(executed_job_ids)} jobs)",
                tool_name=approval.action_type.lower(),
                payload={
                    "approval_id": str(approval.id),
                    "status": "APPROVED",
                    "executed_job_ids": executed_job_ids,
                },
            )

        return {
            "approval_id": approval.id,
            "status": "APPROVED",
            "decision": "APPROVE",
            "executed_count": len(executed_job_ids),
            "executed_job_ids": executed_job_ids,
            "notes": approval.resolution_notes,
        }
