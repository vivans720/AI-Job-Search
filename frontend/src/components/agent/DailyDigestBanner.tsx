"use client";

import React, { useState } from "react";
import {
  Sparkles,
  Calendar,
  Zap,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  Activity,
} from "lucide-react";
import { getApiUrl } from "@/lib/api";

export interface DailyDigestData {
  id: string;
  digest_date: string;
  summary: string;
  total_found: number;
  strong_matches_count: number;
  status: string;
  created_at: string;
  top_job_ids?: string[];
  metadata_info?: Record<string, unknown>;
}

interface DailyDigestBannerProps {
  digest: DailyDigestData | null;
  loading: boolean;
  onRefresh: () => void;
  onOpenActivity?: () => void;
}

export function DailyDigestBanner({
  digest,
  loading,
  onRefresh,
  onOpenActivity,
}: DailyDigestBannerProps) {
  const [expanded, setExpanded] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [triggerStatus, setTriggerStatus] = useState<string | null>(null);

  const handleRunScheduledSearch = async () => {
    setTriggering(true);
    setTriggerStatus(null);
    try {
      const res = await fetch(getApiUrl("/api/v1/digests/run-scheduled-search"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          freshness_hours: 24,
          dry_run: false,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setTriggerStatus(
          `Agent hunt completed: Discovered ${data.fresh_discovered_count} fresh roles, ${data.qualifying_matches_count} matches.`
        );
        onRefresh();
        setTimeout(() => setTriggerStatus(null), 5000);
      } else {
        setTriggerStatus("Autonomous search request failed.");
      }
    } catch {
      setTriggerStatus("Could not trigger search. Backend may be offline.");
    } finally {
      setTriggering(false);
    }
  };

  if (loading) {
    return (
      <div className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-xs flex items-center gap-3 animate-pulse">
        <div className="w-9 h-9 rounded-xl bg-slate-100" />
        <div className="space-y-1.5 flex-1">
          <div className="w-1/4 h-4 bg-slate-100 rounded" />
          <div className="w-2/3 h-3 bg-slate-100 rounded" />
        </div>
      </div>
    );
  }

  const isZeroMatch = digest?.status === "ZERO_MATCH" || (digest && digest.total_found === 0);

  return (
    <div className="relative overflow-hidden rounded-2xl border border-emerald-500/20 bg-gradient-to-br from-emerald-500/[0.04] via-teal-500/[0.02] to-transparent p-5 shadow-xs backdrop-blur-xs">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        {/* Left Info / Heading */}
        <div className="flex items-start gap-3.5 flex-1">
          <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-emerald-600 text-white shadow-xs shrink-0 mt-0.5">
            <Sparkles className="w-5 h-5" />
          </div>

          <div className="space-y-1">
            <div className="flex items-center gap-2.5 flex-wrap">
              <h2 className="text-sm sm:text-base font-bold tracking-tight text-slate-900 flex items-center gap-1.5">
                Hermes Morning Job Intelligence
              </h2>
              {digest?.digest_date && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-semibold bg-white border border-slate-200 text-slate-600">
                  <Calendar className="w-3 h-3 text-slate-400" />
                  {digest.digest_date}
                </span>
              )}
              <span
                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold tracking-wide uppercase ${
                  isZeroMatch
                    ? "bg-amber-50 text-amber-800 border border-amber-200"
                    : "bg-emerald-50 text-emerald-800 border border-emerald-200"
                }`}
              >
                {isZeroMatch ? "Zero-Match Clean Run" : "Active Briefing"}
              </span>
            </div>

            <p className="text-xs text-slate-600 leading-relaxed line-clamp-2 sm:line-clamp-none max-w-3xl">
              {digest?.summary ||
                "No morning briefing generated yet today. You can run an autonomous hunt now to scan active sources and match against your profile."}
            </p>
          </div>
        </div>

        {/* Right Metrics & Quick Triggers */}
        <div className="flex items-center gap-2.5 flex-wrap self-end lg:self-center shrink-0">
          {digest && (
            <div className="hidden sm:flex items-center gap-3 px-3.5 py-1.5 rounded-xl bg-white border border-slate-200/80 text-xs shadow-2xs">
              <div className="flex items-center gap-1.5">
                <span className="text-slate-400 font-medium">Found:</span>
                <strong className="text-slate-900 font-bold font-tabular">{digest.total_found}</strong>
              </div>
              <span className="text-slate-200">|</span>
              <div className="flex items-center gap-1.5">
                <span className="text-slate-400 font-medium">Strong Matches:</span>
                <strong className="text-emerald-700 font-bold font-tabular">
                  {digest.strong_matches_count}
                </strong>
              </div>
            </div>
          )}

          {onOpenActivity && (
            <button
              onClick={onOpenActivity}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-white hover:bg-slate-50 border border-slate-200/80 text-slate-700 text-xs font-semibold shadow-2xs transition-colors cursor-pointer"
              title="View live agent activity and tool execution runs"
            >
              <Activity className="w-3.5 h-3.5 text-emerald-600" />
              <span className="hidden sm:inline">Telemetry</span>
            </button>
          )}

          <button
            onClick={handleRunScheduledSearch}
            disabled={triggering}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 active:scale-[0.98] disabled:opacity-50 text-white text-xs font-semibold shadow-xs transition-all cursor-pointer"
            title="Trigger scheduled search and generate briefing"
          >
            <Zap className={`w-3.5 h-3.5 ${triggering ? "animate-spin" : ""}`} />
            <span>{triggering ? "Scanning..." : "Run Morning Hunt"}</span>
          </button>

          {digest?.summary && digest.summary.length > 180 && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="p-2 rounded-xl bg-white hover:bg-slate-50 border border-slate-200/80 text-slate-600 transition-colors cursor-pointer shadow-2xs"
              aria-label="Toggle full briefing"
            >
              {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>
          )}
        </div>
      </div>

      {/* Expanded Briefing Detail */}
      {expanded && digest?.summary && (
        <div className="mt-4 pt-4 border-t border-emerald-500/15 text-xs text-slate-700 space-y-2.5 animate-fadeIn">
          <div className="font-semibold text-slate-900 flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
            <span>Full Agent Briefing Analysis</span>
          </div>
          <div className="p-3.5 rounded-xl bg-white/90 border border-slate-200/80 whitespace-pre-line leading-relaxed font-mono text-[11px] text-slate-800 shadow-2xs">
            {digest.summary}
          </div>
        </div>
      )}

      {/* Trigger Notification Toast */}
      {triggerStatus && (
        <div className="mt-3 p-2.5 rounded-xl bg-emerald-100/80 border border-emerald-200 text-emerald-900 text-xs font-medium flex items-center gap-2 animate-fadeIn">
          <CheckCircle2 className="w-4 h-4 text-emerald-700 shrink-0" />
          <span>{triggerStatus}</span>
        </div>
      )}
    </div>
  );
}
