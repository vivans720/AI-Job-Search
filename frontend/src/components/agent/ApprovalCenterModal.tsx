"use client";

import React, { useEffect, useState } from "react";
import {
  ShieldAlert,
  CheckCircle2,
  XCircle,
  Clock,
  ExternalLink,
  RefreshCw,
  X,
  AlertCircle,
  Check,
} from "lucide-react";
import { getApiUrl } from "@/lib/api";

export interface AgentApprovalItem {
  id: string;
  user_id: string;
  run_id: string | null;
  action_type: string;
  status: string;
  job_id: string | null;
  payload: {
    job_id?: string;
    job_ids?: string[];
    status?: string;
    notes?: string;
    reason?: string;
  };
  reason: string | null;
  created_at: string;
  expires_at: string | null;
  resolved_at: string | null;
  resolution_notes: string | null;
  job_summary?: {
    id: string;
    title: string;
    company: string;
    location: string;
    salary: string;
    application_url: string;
  } | null;
}

interface ApprovalCenterModalProps {
  isOpen: boolean;
  onClose: () => void;
  onResolved?: () => void;
}

export function ApprovalCenterModal({ isOpen, onClose, onResolved }: ApprovalCenterModalProps) {
  const [approvals, setApprovals] = useState<AgentApprovalItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedBatchIds, setSelectedBatchIds] = useState<Record<string, string[]>>({});
  const [resolvingId, setResolvingId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"PENDING" | "HISTORY">("PENDING");
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const fetchApprovals = async () => {
    setLoading(true);
    try {
      const url =
        activeTab === "PENDING"
          ? getApiUrl("/api/v1/agent/approvals?status=PENDING")
          : getApiUrl("/api/v1/agent/approvals?limit=30");
      const res = await fetch(url);
      if (res.ok) {
        const data: AgentApprovalItem[] = await res.json();
        setApprovals(data);
        // Preselect all batch ids for batch actions
        const initialBatch: Record<string, string[]> = {};
        data.forEach((apprv) => {
          if (apprv.action_type === "BATCH_SAVE" && apprv.payload?.job_ids) {
            initialBatch[apprv.id] = [...apprv.payload.job_ids];
          }
        });
        setSelectedBatchIds(initialBatch);
      }
    } catch {
      // Backend offline
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchApprovals();
    }
  }, [isOpen, activeTab]);

  if (!isOpen) return null;

  const handleResolve = async (
    approvalId: string,
    decision: "APPROVE" | "REJECT",
    isBatch = false
  ) => {
    setResolvingId(approvalId);
    setMessage(null);
    try {
      const partialIds = isBatch ? selectedBatchIds[approvalId] : undefined;
      const res = await fetch(getApiUrl(`/api/v1/agent/approvals/${approvalId}/resolve`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          decision,
          partial_job_ids: partialIds,
          resolution_notes:
            decision === "APPROVE"
              ? `Approved by candidate via Approval Center`
              : `Dismissed by candidate via Approval Center`,
        }),
      });

      if (res.ok) {
        setMessage({
          type: "success",
          text: `Action successfully ${decision === "APPROVE" ? "approved & executed" : "rejected"}.`,
        });
        await fetchApprovals();
        if (onResolved) onResolved();
      } else {
        const err = await res.json();
        setMessage({ type: "error", text: err.detail || "Failed to resolve approval." });
      }
    } catch {
      setMessage({ type: "error", text: "Network error during resolution." });
    } finally {
      setResolvingId(null);
    }
  };

  const toggleBatchJob = (approvalId: string, jobId: string) => {
    setSelectedBatchIds((prev) => {
      const current = prev[approvalId] || [];
      if (current.includes(jobId)) {
        return { ...prev, [approvalId]: current.filter((id) => id !== jobId) };
      } else {
        return { ...prev, [approvalId]: [...current, jobId] };
      }
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-2xl bg-white rounded-2xl shadow-2xl border border-slate-200 flex flex-col max-h-[85vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-100">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-purple-50 border border-purple-200 text-purple-600">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900">Agent Approval Center</h2>
              <p className="text-xs text-slate-500">
                Review and approve recommended job actions before they update your pipeline
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tabs & Status Alert */}
        <div className="px-5 pt-3 border-b border-slate-100 flex items-center justify-between">
          <div className="flex gap-4">
            <button
              onClick={() => setActiveTab("PENDING")}
              className={`pb-2.5 text-xs font-semibold border-b-2 transition-colors ${
                activeTab === "PENDING"
                  ? "border-purple-600 text-purple-700"
                  : "border-transparent text-slate-500 hover:text-slate-800"
              }`}
            >
              Pending Reviews ({approvals.filter((a) => a.status === "PENDING").length})
            </button>
            <button
              onClick={() => setActiveTab("HISTORY")}
              className={`pb-2.5 text-xs font-semibold border-b-2 transition-colors ${
                activeTab === "HISTORY"
                  ? "border-purple-600 text-purple-700"
                  : "border-transparent text-slate-500 hover:text-slate-800"
              }`}
            >
              Approval History
            </button>
          </div>

          <button
            onClick={fetchApprovals}
            disabled={loading}
            className="text-[11px] text-slate-500 hover:text-slate-800 flex items-center gap-1 font-mono pb-2"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin text-purple-600" : ""}`} />
            Refresh
          </button>
        </div>

        {/* Messages */}
        {message && (
          <div
            className={`mx-5 mt-3 p-3 rounded-xl flex items-center gap-2.5 text-xs border ${
              message.type === "success"
                ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                : "bg-rose-50 border-rose-200 text-rose-800"
            }`}
          >
            {message.type === "success" ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
            )}
            <span className="font-semibold">{message.text}</span>
          </div>
        )}

        {/* Content Body */}
        <div className="p-5 overflow-y-auto space-y-4 flex-1">
          {loading && approvals.length === 0 ? (
            <div className="py-16 text-center text-xs font-mono text-slate-400 flex items-center justify-center gap-2">
              <RefreshCw className="w-4 h-4 animate-spin text-purple-600" />
              Loading approval requests...
            </div>
          ) : approvals.length === 0 ? (
            <div className="py-16 text-center text-xs font-mono text-slate-400 bg-slate-50 rounded-xl border border-slate-100">
              {activeTab === "PENDING"
                ? "No pending approvals! Autonomous agent actions are up-to-date."
                : "No past approval records found."}
            </div>
          ) : (
            approvals.map((apprv) => {
              const isBatch = apprv.action_type === "BATCH_SAVE";
              const isPending = apprv.status === "PENDING";
              const batchCount = apprv.payload?.job_ids?.length || 0;
              const currentSelected = selectedBatchIds[apprv.id] || [];

              return (
                <div
                  key={apprv.id}
                  className={`p-4 rounded-xl border transition-all ${
                    isPending
                      ? "bg-white border-purple-200/80 shadow-card-subtle"
                      : "bg-slate-50/70 border-slate-200"
                  }`}
                >
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <div className="flex items-center gap-2">
                      <span
                        className={`px-2 py-0.5 rounded-md text-[10px] font-mono font-bold uppercase tracking-wider ${
                          apprv.action_type === "SAVE_JOB" || apprv.action_type === "BATCH_SAVE"
                            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                            : apprv.action_type === "DISMISS_JOB"
                              ? "bg-rose-50 text-rose-700 border border-rose-200"
                              : "bg-blue-50 text-blue-700 border border-blue-200"
                        }`}
                      >
                        {apprv.action_type.replace(/_/g, " ")}
                      </span>

                      <span
                        className={`px-2 py-0.5 rounded-md text-[10px] font-mono font-semibold ${
                          apprv.status === "PENDING"
                            ? "bg-amber-50 text-amber-700 border border-amber-200"
                            : apprv.status === "APPROVED"
                              ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                              : "bg-slate-100 text-slate-600 border border-slate-200"
                        }`}
                      >
                        {apprv.status}
                      </span>
                    </div>

                    <span className="text-[10px] font-mono text-slate-400">
                      {new Date(apprv.created_at).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                  </div>

                  {/* Agent Recommendation Statement */}
                  <div className="text-xs text-slate-700 mb-3 bg-slate-50 p-2.5 rounded-lg border border-slate-100">
                    <strong className="text-slate-900 block mb-0.5 font-medium">Agent note:</strong>
                    {apprv.reason || "Recommending job pipeline modification based on match criteria."}
                  </div>

                  {/* Specific Job Detail if Single Job */}
                  {apprv.job_summary && (
                    <div className="flex items-center justify-between p-3 rounded-lg bg-purple-50/40 border border-purple-100 mb-3 text-xs">
                      <div>
                        <div className="font-bold text-slate-900">{apprv.job_summary.title}</div>
                        <div className="text-[11px] text-slate-500">
                          {apprv.job_summary.company} • {apprv.job_summary.location}
                        </div>
                      </div>
                      {apprv.job_summary.application_url && (
                        <a
                          href={apprv.job_summary.application_url}
                          target="_blank"
                          rel="noreferrer"
                          className="p-1.5 text-purple-600 hover:text-purple-800 rounded bg-white border border-purple-200"
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                        </a>
                      )}
                    </div>
                  )}

                  {/* Batch Selection Details */}
                  {isBatch && (
                    <div className="mb-3 text-xs font-mono text-slate-600 bg-slate-100/70 p-2.5 rounded-lg">
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="font-bold">Batch Target ({batchCount} jobs)</span>
                        <span className="text-[11px] text-purple-700 font-semibold">
                          {currentSelected.length} of {batchCount} selected
                        </span>
                      </div>
                      <div className="max-h-28 overflow-y-auto space-y-1 pr-1">
                        {apprv.payload?.job_ids?.map((jid) => {
                          const isSelected = currentSelected.includes(jid);
                          return (
                            <label
                              key={jid}
                              className="flex items-center gap-2 p-1.5 rounded hover:bg-white cursor-pointer transition-colors"
                            >
                              <input
                                type="checkbox"
                                checked={isSelected}
                                disabled={!isPending}
                                onChange={() => toggleBatchJob(apprv.id, jid)}
                                className="rounded text-purple-600 focus:ring-purple-500"
                              />
                              <span className="text-[11px] font-mono text-slate-700 truncate">
                                Job ID: {jid}
                              </span>
                            </label>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Resolution Notes in History */}
                  {!isPending && apprv.resolution_notes && (
                    <div className="text-[11px] text-slate-500 font-mono mt-1">
                      Resolution: {apprv.resolution_notes}
                    </div>
                  )}

                  {/* Action Buttons for Pending */}
                  {isPending && (
                    <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
                      <button
                        onClick={() => handleResolve(apprv.id, "REJECT", isBatch)}
                        disabled={resolvingId === apprv.id}
                        className="px-3 py-1.5 text-xs font-semibold text-rose-700 bg-rose-50 hover:bg-rose-100 border border-rose-200 rounded-lg transition-colors flex items-center gap-1"
                      >
                        <XCircle className="w-3.5 h-3.5" />
                        Reject
                      </button>

                      <button
                        onClick={() => handleResolve(apprv.id, "APPROVE", isBatch)}
                        disabled={
                          resolvingId === apprv.id || (isBatch && currentSelected.length === 0)
                        }
                        className="px-4 py-1.5 text-xs font-semibold text-white bg-purple-600 hover:bg-purple-700 rounded-lg transition-colors shadow-xs flex items-center gap-1 disabled:opacity-50"
                      >
                        {resolvingId === apprv.id ? (
                          <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <Check className="w-3.5 h-3.5" />
                        )}
                        {isBatch
                          ? `Approve Selected (${currentSelected.length})`
                          : "Approve Action"}
                      </button>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className="p-4 bg-slate-50 border-t border-slate-200 flex items-center justify-between text-xs text-slate-500">
          <div className="flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-slate-400" />
            <span>Approvals automatically expire after 24 hours.</span>
          </div>
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-white border border-slate-300 hover:bg-slate-100 text-slate-700 rounded-lg font-semibold transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
