"use client";

import React, { useEffect, useState } from "react";
import {
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Square,
  Clock,
  X,
} from "lucide-react";

export interface SourceProgress {
  status: "pending" | "running" | "success" | "blocked" | "failed";
  discovered: number;
  saved: number;
  updated: number;
  duplicates: number;
  rejected: number;
  skills?: number;
  embeddings?: number;
}

export interface SyncResultSummary {
  status: "completed" | "partial_success" | "failed" | "blocked" | "cancelled";
  total_discovered?: number;
  canonical_saved?: number;
  updated_existing?: number;
  fresh_jobs?: number;
  sources_synced?: string[];
  error?: string;
}

export interface SyncProgressModalProps {
  isOpen: boolean;
  onClose: () => void;
  jobId: string | null;
  source: string;
  onSyncComplete?: (summary?: SyncResultSummary) => void;
  onCancelSync?: () => void;
}

export const SyncProgressModal: React.FC<SyncProgressModalProps> = ({
  isOpen,
  onClose,
  jobId,
  source,
  onSyncComplete,
  onCancelSync,
}) => {
  const [status, setStatus] = useState<"queued" | "running" | "completed" | "failed" | "cancelled">("queued");
  const [cancelling, setCancelling] = useState(false);
  const [sourcesProgress, setSourcesProgress] = useState<Record<string, SourceProgress>>({
    linkedin: { status: "pending", discovered: 0, saved: 0, updated: 0, duplicates: 0, rejected: 0, skills: 0, embeddings: 0 },
    naukri: { status: "pending", discovered: 0, saved: 0, updated: 0, duplicates: 0, rejected: 0, skills: 0, embeddings: 0 },
    internshala: { status: "pending", discovered: 0, saved: 0, updated: 0, duplicates: 0, rejected: 0, skills: 0, embeddings: 0 },
  });
  const [totals, setTotals] = useState({
    discovered: 0,
    newSaved: 0,
    updated: 0,
    duplicates: 0,
    rejected: 0,
    skills: 0,
    embeddings: 0,
  });
  const [error, setError] = useState<string | null>(null);
  const hasCompletedRef = React.useRef(false);
  const onSyncCompleteRef = React.useRef(onSyncComplete);
  onSyncCompleteRef.current = onSyncComplete;
  const onCloseRef = React.useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!isOpen) {
      hasCompletedRef.current = false;
      return;
    }

    if (!jobId) {
      setStatus("running");
      return;
    }

    hasCompletedRef.current = false;
    let isMounted = true;
    let pollTimer: NodeJS.Timeout | null = null;
    let autoCloseTimer: NodeJS.Timeout | null = null;

    const poll = async () => {
      try {
        const res = await fetch(`http://localhost:8000/api/v1/jobs/sync/status/${jobId}`);
        if (!res.ok) {
          if (isMounted && !hasCompletedRef.current) pollTimer = setTimeout(poll, 2000);
          return;
        }

        const data = await res.json();
        if (!isMounted || hasCompletedRef.current) return;

        const currentStatus = data.status || "running";
        setStatus(currentStatus);

        // Progress tracker from worker
        if (data.progress) {
          setSourcesProgress((prev) => ({ ...prev, ...data.progress }));
        }

        const isTerminal = ["completed", "failed", "blocked", "partial_success", "cancelled"].includes(currentStatus);

        // Final result stats if completed or partial_success
        if (currentStatus === "completed" || currentStatus === "partial_success") {
          const resStats = data.result || {};
          const sMap = resStats.sources || {};

          // Update source progress from completed summary if available
          setSourcesProgress((prev) => {
            const next = { ...prev };
            Object.keys(sMap).forEach((srcKey) => {
              const info = sMap[srcKey];
              next[srcKey] = {
                status: info.status || "success",
                discovered: info.discovered || 0,
                saved: info.accepted || 0,
                updated: 0,
                duplicates: 0,
                rejected: Math.max(0, (info.discovered || 0) - (info.accepted || 0)),
              };
            });
            return next;
          });

          setTotals({
            discovered: resStats.total_discovered || 0,
            newSaved: resStats.canonical_saved || 0,
            updated: resStats.updated_existing || 0,
            duplicates: resStats.deduplicated || 0,
            rejected:
              (resStats.filtered_by_freshness || 0) +
              (resStats.filtered_by_validation || 0) +
              (resStats.filtered_by_experience || 0),
            skills: (resStats.ai_extracted_skills || 0) + (resStats.normalized_skills || 0),
            embeddings: resStats.embeddings_generated || 0,
          });

          if (!hasCompletedRef.current) {
            hasCompletedRef.current = true;
            if (onSyncCompleteRef.current) {
              onSyncCompleteRef.current({
                status: currentStatus,
                total_discovered: resStats.total_discovered || 0,
                canonical_saved: resStats.canonical_saved || 0,
                updated_existing: resStats.updated_existing || 0,
                fresh_jobs: resStats.fresh_jobs || 0,
                sources_synced: resStats.sources_synced || (Object.keys(sMap).length > 0 ? Object.keys(sMap) : undefined),
              });
            }
            // Automatically close modal after brief visual delay
            autoCloseTimer = setTimeout(() => {
              if (isMounted && onCloseRef.current) onCloseRef.current();
            }, 1800);
          }
          return;
        } else if (currentStatus === "cancelled") {
          setError("Sync stopped by user.");
          if (!hasCompletedRef.current) {
            hasCompletedRef.current = true;
            if (onSyncCompleteRef.current) {
              onSyncCompleteRef.current({
                status: "cancelled",
                error: "Sync cancelled by user.",
              });
            }
          }
          return;
        } else if (currentStatus === "failed" || currentStatus === "blocked") {
          const errMsg = data.error || (currentStatus === "blocked" ? "Sync blocked by source perimeter." : "Ingestion pipeline encountered an error.");
          setError(errMsg);
          if (!hasCompletedRef.current) {
            hasCompletedRef.current = true;
            if (onSyncCompleteRef.current) {
              onSyncCompleteRef.current({
                status: currentStatus,
                error: errMsg,
              });
            }
          }
          return;
        }

        // Compute running totals from sourcesProgress
        if (data.progress) {
          let disc = 0,
            sav = 0,
            upd = 0,
            dup = 0,
            rej = 0,
            sk = 0,
            em = 0;
          Object.values(data.progress as Record<string, SourceProgress>).forEach((sp) => {
            disc += sp.discovered || 0;
            sav += sp.saved || 0;
            upd += sp.updated || 0;
            dup += sp.duplicates || 0;
            rej += sp.rejected || 0;
            sk += sp.skills || 0;
            em += sp.embeddings || 0;
          });
          setTotals({
            discovered: disc,
            newSaved: sav,
            updated: upd,
            duplicates: dup,
            rejected: rej,
            skills: sk,
            embeddings: em,
          });
        }

        if (!isTerminal && isMounted && !hasCompletedRef.current) {
          pollTimer = setTimeout(poll, 1200);
        }
      } catch {
        if (!isMounted || hasCompletedRef.current) return;
        pollTimer = setTimeout(poll, 2000);
      }
    };

    poll();

    return () => {
      isMounted = false;
      if (pollTimer) clearTimeout(pollTimer);
      if (autoCloseTimer) clearTimeout(autoCloseTimer);
    };
  }, [isOpen, jobId]);

  if (!isOpen) return null;

  const targetSources =
    source === "all" ? ["linkedin", "naukri", "internshala"] : [source.toLowerCase()];

  const getSourceStatusBadge = (st: SourceProgress["status"]) => {
    switch (st) {
      case "running":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 animate-pulse">
            <RefreshCw className="w-3 h-3 animate-spin" /> Ingesting
          </span>
        );
      case "success":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="w-3 h-3" /> Complete
          </span>
        );
      case "blocked":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <AlertCircle className="w-3 h-3" /> Blocked / Perimeter
          </span>
        );
      case "failed":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono bg-rose-500/10 text-rose-400 border border-rose-500/20">
            <AlertCircle className="w-3 h-3" /> Failed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono bg-zinc-800 text-zinc-400 border border-white/[0.06]">
            <Clock className="w-3 h-3" /> Queued
          </span>
        );
    }
  };

  const calculateSourcePercent = (srcKey: string) => {
    const sp = sourcesProgress[srcKey];
    if (!sp) return 0;
    if (sp.status === "success" || sp.status === "blocked" || sp.status === "failed") return 100;
    if (sp.status === "running") return 65;
    return 15;
  };

  const handleCancel = async () => {
    if (!jobId || cancelling) return;
    setCancelling(true);
    try {
      await fetch(`http://localhost:8000/api/v1/jobs/sync/cancel/${jobId}`, {
        method: "POST",
      });
      setStatus("cancelled");
      setError("Sync stopped by user.");
      if (onCancelSync) onCancelSync();
    } catch {
      setError("Failed to stop sync.");
    } finally {
      setCancelling(false);
    }
  };

  const getStatusBadgeClass = () => {
    switch (status) {
      case "completed":
        return "bg-emerald-100 text-emerald-800 border-emerald-300";
      case "cancelled":
        return "bg-amber-100 text-amber-800 border-amber-300";
      case "failed":
        return "bg-rose-100 text-rose-800 border-rose-300";
      case "running":
        return "bg-blue-100 text-blue-800 border-blue-300 animate-pulse";
      default:
        return "bg-slate-200 text-slate-700";
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs animate-fade-in">
      <div className="relative w-full max-w-xl rounded-2xl bg-white border border-slate-200 shadow-2xl overflow-hidden font-sans text-slate-800">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50">
          <div className="flex items-center gap-2.5">
            <div className={`p-2 rounded-xl border ${
              status === "completed"
                ? "bg-emerald-50 border-emerald-200 text-emerald-600"
                : status === "cancelled"
                ? "bg-amber-50 border-amber-200 text-amber-600"
                : "bg-blue-50 border-blue-200 text-blue-600"
            }`}>
              <RefreshCw className={`w-4 h-4 ${status === "running" || status === "queued" ? "animate-spin" : ""}`} />
            </div>
            <div>
              <h3 className="text-sm font-semibold tracking-tight text-slate-900 flex items-center gap-2">
                Ingestion Pipeline Telemetry
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded border uppercase font-bold ${getStatusBadgeClass()}`}>
                  {status}
                </span>
              </h3>
              <p className="text-[11px] text-slate-500 font-mono">
                Real-time crawl, parse, freshness gate & 5-level dedup
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Content */}
        <div className="p-6 space-y-6">
          {/* Per-source progress bars */}
          <div className="space-y-3.5">
            <h4 className="text-[11px] font-mono uppercase tracking-wider text-slate-500 font-bold">
              Live Source Crawlers
            </h4>

            {targetSources.map((srcKey) => {
              const sp = sourcesProgress[srcKey] || {
                status: "pending",
                discovered: 0,
                saved: 0,
                updated: 0,
                duplicates: 0,
                rejected: 0,
              };
              const pct = calculateSourcePercent(srcKey);

              return (
                <div
                  key={srcKey}
                  className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 space-y-2.5"
                >
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-slate-800 capitalize flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                      {srcKey}
                    </span>
                    <div className="flex items-center gap-3">
                      <span className="text-[11px] font-mono text-slate-500 font-tabular">
                        {sp.discovered} found
                      </span>
                      {getSourceStatusBadge(sp.status)}
                    </div>
                  </div>

                  {/* Visual Bar */}
                  <div className="h-1.5 w-full rounded-full bg-slate-200 overflow-hidden relative">
                    <div
                      className={`h-full transition-all duration-500 rounded-full ${
                        sp.status === "success"
                          ? "bg-emerald-500"
                          : sp.status === "blocked"
                          ? "bg-amber-500"
                          : sp.status === "failed"
                          ? "bg-rose-500"
                          : "bg-emerald-600 animate-pulse"
                      }`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>

          {/* Pipeline Flow Architecture Badges */}
          <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
            <span className="text-[10px] font-mono uppercase tracking-wider text-emerald-700 font-bold block">
              Automated Ingestion Sequence
            </span>
            <div className="flex flex-wrap items-center gap-1.5 text-[10px] font-mono text-slate-600">
              <span className="px-2 py-0.5 rounded bg-white text-slate-700 border border-slate-200 shadow-xs">1. Crawl</span>
              <span className="text-slate-300">·</span>
              <span className="px-2 py-0.5 rounded bg-white text-slate-700 border border-slate-200 shadow-xs">2. Normalizer</span>
              <span className="text-slate-300">·</span>
              <span className="px-2 py-0.5 rounded bg-white text-slate-700 border border-slate-200 shadow-xs">3. Freshness Gate</span>
              <span className="text-slate-300">·</span>
              <span className="px-2 py-0.5 rounded bg-white text-slate-700 border border-slate-200 shadow-xs">4. Cross-Dedup</span>
              <span className="text-slate-300">·</span>
              <span className="px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200 font-semibold">5. Skills Extraction</span>
              <span className="text-slate-300">·</span>
              <span className="px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200 font-semibold">6. BGE Vector</span>
              <span className="text-slate-300">·</span>
              <span className="px-2 py-0.5 rounded bg-emerald-100 text-emerald-900 border border-emerald-300 font-bold">7. 6D Match</span>
            </div>
          </div>

          {/* Ingestion Stage Metrics Grid */}
          <div>
            <h4 className="text-[11px] font-mono uppercase tracking-wider text-slate-500 mb-2.5 font-bold">
              Ingestion Funnel Telemetry
            </h4>

            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-xs">
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-center">
                <span className="block text-[10px] uppercase font-mono text-slate-500 font-semibold">Discovered</span>
                <span className="text-sm font-bold font-tabular text-slate-900">
                  {totals.discovered.toLocaleString()}
                </span>
              </div>

              <div className="p-3 rounded-xl bg-emerald-50/60 border border-emerald-200 text-center">
                <span className="block text-[10px] uppercase font-mono text-emerald-700 font-semibold">New Saved</span>
                <span className="text-sm font-bold font-tabular text-emerald-700">
                  {totals.newSaved.toLocaleString()}
                </span>
              </div>

              <div className="p-3 rounded-xl bg-sky-50/60 border border-sky-200 text-center">
                <span className="block text-[10px] uppercase font-mono text-sky-700 font-semibold">Updated</span>
                <span className="text-sm font-bold font-tabular text-sky-700">
                  {totals.updated.toLocaleString()}
                </span>
              </div>

              <div className="p-3 rounded-xl bg-amber-50/60 border border-amber-200 text-center">
                <span className="block text-[10px] uppercase font-mono text-amber-700 font-semibold">Duplicates</span>
                <span className="text-sm font-bold font-tabular text-amber-700">
                  {totals.duplicates.toLocaleString()}
                </span>
              </div>

              <div className="p-3 rounded-xl bg-rose-50/60 border border-rose-200 text-center">
                <span className="block text-[10px] uppercase font-mono text-rose-700 font-semibold">Rejected</span>
                <span className="text-sm font-bold font-tabular text-rose-700">
                  {totals.rejected.toLocaleString()}
                </span>
              </div>
            </div>
          </div>

          {error && (
            <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="flex items-center justify-between px-6 py-3.5 border-t border-slate-200 bg-slate-50 text-xs">
          <span className="text-slate-500 font-mono text-[11px]">
            {status === "completed"
              ? "Ingestion complete"
              : status === "cancelled"
              ? "Sync cancelled"
              : "Syncing in background worker..."}
          </span>
          <div className="flex items-center gap-2">
            {(status === "running" || status === "queued") && (
              <button
                onClick={handleCancel}
                disabled={cancelling}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 font-semibold transition-colors disabled:opacity-50 cursor-pointer"
              >
                <Square className="w-3 h-3 fill-rose-700" />
                <span>{cancelling ? "Stopping..." : "Stop Sync"}</span>
              </button>
            )}
            <button
              onClick={onClose}
              className="px-4 py-1.5 rounded-lg bg-white border border-slate-200 hover:bg-slate-100 text-slate-700 font-semibold transition-colors shadow-xs cursor-pointer"
            >
              {status === "completed" || status === "cancelled" ? "Done" : "Dismiss"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
