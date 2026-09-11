"use client";

import React, { useEffect, useState } from "react";
import {
  RefreshCw,
  CheckCircle2,
  AlertCircle,
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
}

export interface SyncProgressModalProps {
  isOpen: boolean;
  onClose: () => void;
  jobId: string | null;
  source: string;
  onSyncComplete?: () => void;
}

export const SyncProgressModal: React.FC<SyncProgressModalProps> = ({
  isOpen,
  onClose,
  jobId,
  source,
  onSyncComplete,
}) => {
  const [status, setStatus] = useState<"queued" | "running" | "completed" | "failed">("queued");
  const [sourcesProgress, setSourcesProgress] = useState<Record<string, SourceProgress>>({
    linkedin: { status: "pending", discovered: 0, saved: 0, updated: 0, duplicates: 0, rejected: 0 },
    naukri: { status: "pending", discovered: 0, saved: 0, updated: 0, duplicates: 0, rejected: 0 },
    internshala: { status: "pending", discovered: 0, saved: 0, updated: 0, duplicates: 0, rejected: 0 },
  });
  const [totals, setTotals] = useState({
    discovered: 0,
    newSaved: 0,
    updated: 0,
    duplicates: 0,
    rejected: 0,
  });
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;

    if (!jobId) {
      setStatus("running");
      return;
    }

    let isMounted = true;
    let pollTimer: NodeJS.Timeout;

    const poll = async () => {
      try {
        const res = await fetch(`http://localhost:8000/api/v1/jobs/sync/status/${jobId}`);
        if (!res.ok) return;

        const data = await res.json();
        if (!isMounted) return;

        setStatus(data.status || "running");

        // Progress tracker from worker
        if (data.progress) {
          setSourcesProgress((prev) => ({ ...prev, ...data.progress }));
        }

        // Final result stats if completed
        if (data.status === "completed") {
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
          });

          if (onSyncComplete) onSyncComplete();
          return;
        } else if (data.status === "failed") {
          setError(data.error || "Ingestion pipeline encountered an error.");
          return;
        }

        // Compute running totals from sourcesProgress
        if (data.progress) {
          let disc = 0,
            sav = 0,
            upd = 0,
            dup = 0,
            rej = 0;
          Object.values(data.progress as Record<string, SourceProgress>).forEach((sp) => {
            disc += sp.discovered || 0;
            sav += sp.saved || 0;
            upd += sp.updated || 0;
            dup += sp.duplicates || 0;
            rej += sp.rejected || 0;
          });
          setTotals({
            discovered: disc,
            newSaved: sav,
            updated: upd,
            duplicates: dup,
            rejected: rej,
          });
        }

        pollTimer = setTimeout(poll, 1200);
      } catch {
        if (!isMounted) return;
        pollTimer = setTimeout(poll, 2000);
      }
    };

    poll();

    return () => {
      isMounted = false;
      clearTimeout(pollTimer);
    };
  }, [isOpen, jobId, onSyncComplete]);

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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-obsidian-950/80 backdrop-blur-md animate-fade-in">
      <div className="relative w-full max-w-xl rounded-2xl bg-obsidian-900 border border-white/[0.12] shadow-2xl overflow-hidden font-sans text-zinc-100">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.08] bg-obsidian-950/60">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
              <RefreshCw className={`w-4 h-4 ${status !== "completed" ? "animate-spin" : ""}`} />
            </div>
            <div>
              <h3 className="text-sm font-semibold tracking-tight text-white flex items-center gap-2">
                Ingestion Pipeline Telemetry
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/[0.06] text-zinc-400 uppercase">
                  {status}
                </span>
              </h3>
              <p className="text-[11px] text-zinc-400 font-mono">
                Real-time crawl, parse, freshness gate & 5-level dedup
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/[0.08] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Content */}
        <div className="p-6 space-y-6">
          {/* Per-source progress bars */}
          <div className="space-y-4">
            <h4 className="text-xs font-mono uppercase tracking-wider text-zinc-400">
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
                  className="p-3.5 rounded-xl bg-obsidian-950/50 border border-white/[0.06] space-y-2.5"
                >
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-zinc-200 capitalize flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                      {srcKey}
                    </span>
                    <div className="flex items-center gap-3">
                      <span className="text-[11px] font-mono text-zinc-400">
                        {sp.discovered} found
                      </span>
                      {getSourceStatusBadge(sp.status)}
                    </div>
                  </div>

                  {/* Visual Bar */}
                  <div className="h-2 w-full rounded-full bg-obsidian-800 overflow-hidden relative">
                    <div
                      className={`h-full transition-all duration-500 rounded-full ${
                        sp.status === "success"
                          ? "bg-emerald-500"
                          : sp.status === "blocked"
                          ? "bg-amber-500"
                          : sp.status === "failed"
                          ? "bg-rose-500"
                          : "bg-gradient-to-r from-emerald-500 to-cyan-400 animate-pulse"
                      }`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>

          {/* Phase 38 Ingestion Stage Metrics Grid */}
          <div>
            <h4 className="text-xs font-mono uppercase tracking-wider text-zinc-400 mb-3">
              Ingestion Funnel Telemetry
            </h4>

            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5">
              <div className="p-3 rounded-xl bg-obsidian-950/70 border border-white/[0.06] text-center">
                <span className="block text-[10px] uppercase font-mono text-zinc-400">Discovered</span>
                <span className="text-base font-bold font-tabular text-zinc-100">
                  {totals.discovered.toLocaleString()}
                </span>
              </div>

              <div className="p-3 rounded-xl bg-obsidian-950/70 border border-white/[0.06] text-center">
                <span className="block text-[10px] uppercase font-mono text-emerald-400">New Saved</span>
                <span className="text-base font-bold font-tabular text-emerald-400">
                  {totals.newSaved.toLocaleString()}
                </span>
              </div>

              <div className="p-3 rounded-xl bg-obsidian-950/70 border border-white/[0.06] text-center">
                <span className="block text-[10px] uppercase font-mono text-cyan-400">Updated</span>
                <span className="text-base font-bold font-tabular text-cyan-400">
                  {totals.updated.toLocaleString()}
                </span>
              </div>

              <div className="p-3 rounded-xl bg-obsidian-950/70 border border-white/[0.06] text-center">
                <span className="block text-[10px] uppercase font-mono text-amber-400">Duplicates</span>
                <span className="text-base font-bold font-tabular text-amber-400">
                  {totals.duplicates.toLocaleString()}
                </span>
              </div>

              <div className="p-3 rounded-xl bg-obsidian-950/70 border border-white/[0.06] text-center">
                <span className="block text-[10px] uppercase font-mono text-rose-400">Rejected</span>
                <span className="text-base font-bold font-tabular text-rose-400">
                  {totals.rejected.toLocaleString()}
                </span>
              </div>
            </div>
          </div>

          {error && (
            <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="flex items-center justify-between px-6 py-3.5 border-t border-white/[0.08] bg-obsidian-950/60 text-xs">
          <span className="text-zinc-500 font-mono text-[11px]">
            {status === "completed" ? "Ingestion complete" : "Syncing in background worker..."}
          </span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-white/[0.08] hover:bg-white/[0.12] text-zinc-200 font-medium transition-colors"
          >
            {status === "completed" ? "Done" : "Dismiss"}
          </button>
        </div>
      </div>
    </div>
  );
};
