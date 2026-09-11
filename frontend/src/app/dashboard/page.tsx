"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  Sparkles,
  ArrowDown,
  TrendingUp,
  Bookmark,
  CheckCircle2,
  Clock,
  RefreshCw,
  AlertCircle,
  ExternalLink,
  ChevronRight,
  Flame,
  Zap,
} from "lucide-react";
import { SyncProgressModal } from "@/components/SyncProgressModal";

interface JobItem {
  id: string;
  title: string;
  company: string;
  location?: string;
  remote_type?: string;
  source: string;
  application_url: string;
  match?: {
    overall_score: number;
    recommendation: string;
  };
  age_hours?: number;
}

interface DashboardData {
  greeting: string;
  user_name?: string;
  funnel: {
    fresh_jobs_count: number;
    strong_matches_count: number;
    excellent_matches_count: number;
  };
  recommended_jobs: JobItem[];
  new_jobs: JobItem[];
  application_summary: {
    total_tracked: number;
    saved: number;
    applied: number;
    interviewing: number;
    offered: number;
    rejected: number;
  };
  skill_gaps: {
    skill: string;
    frequency: number;
    demand_percentage: number;
  }[];
  source_health: {
    healthy_count: number;
    total_sources: number;
    status: string;
    sources: Record<string, boolean>;
  };
  sync_status: {
    last_sync_time?: string;
    status: string;
    duration_seconds: number;
    jobs_discovered: number;
    jobs_added: number;
  };
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [syncModalOpen, setSyncModalOpen] = useState(false);
  const [syncJobId, setSyncJobId] = useState<string | null>(null);
  const [syncSource, setSyncSource] = useState<string>("all");

  const handleTriggerSync = async () => {
    try {
      setSyncJobId(null);
      setSyncSource("all");
      setSyncModalOpen(true);
      const res = await fetch("http://localhost:8000/api/v1/jobs/sync?source=all&freshness_hours=24", {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        if (data.job_id) {
          setSyncJobId(data.job_id);
        }
      }
    } catch (e) {
      console.error("Failed to trigger sync", e);
    }
  };

  const fetchDashboard = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetch("http://localhost:8000/api/v1/dashboard");
      if (!res.ok) {
        throw new Error(`Failed to load dashboard: ${res.statusText}`);
      }
      const json = await res.json();
      setData(json);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  const formatTime = (timestamp?: string) => {
    if (!timestamp) return "Never";
    try {
      const d = new Date(timestamp);
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", month: "short", day: "numeric" });
    } catch {
      return timestamp;
    }
  };

  if (loading && !data) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center min-h-[70vh] text-zinc-400 gap-3">
        <RefreshCw className="w-6 h-6 animate-spin text-emerald-400" />
        <p className="text-sm font-medium">Synthesizing intelligence dashboard...</p>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="p-8 max-w-4xl mx-auto">
        <div className="p-6 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-300 flex items-start gap-4">
          <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5 text-rose-400" />
          <div className="flex-1">
            <h3 className="font-semibold text-rose-200">Unable to load dashboard</h3>
            <p className="text-sm mt-1 text-rose-300/80">{error}</p>
            <button
              onClick={fetchDashboard}
              className="mt-4 px-4 py-1.5 text-xs font-medium rounded-lg bg-rose-500/20 hover:bg-rose-500/30 text-rose-200 border border-rose-500/30 transition-colors"
            >
              Try Again
            </button>
          </div>
        </div>
      </div>
    );
  }

  const funnel = data?.funnel || { fresh_jobs_count: 0, strong_matches_count: 0, excellent_matches_count: 0 };
  const appSummary = data?.application_summary || { total_tracked: 0, saved: 0, applied: 0, interviewing: 0, offered: 0, rejected: 0 };

  return (
    <div className="flex-1 p-6 md:p-10 max-w-7xl mx-auto space-y-8 animate-in fade-in duration-300">
      {/* Top Banner & Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/[0.07] pb-6">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-emerald-400">Live Mission Control</span>
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white mt-1">
            {data?.greeting}{data?.user_name ? `, ${data.user_name}` : ""}
          </h1>
          <p className="text-sm text-zinc-400 mt-1">
            Here is your real-time job synchronization funnel and application pipeline.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleTriggerSync}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-500/10 border border-emerald-500/30 hover:bg-emerald-500/20 text-emerald-300 text-sm font-medium transition-all shadow-sm shadow-emerald-950/20 hover:scale-[1.02] active:scale-[0.98]"
          >
            <RefreshCw className="w-4 h-4 text-emerald-400" />
            <span>Sync Now</span>
          </button>
          <Link
            href="/jobs?view=for_you"
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/[0.05] border border-white/10 hover:bg-white/[0.09] text-zinc-200 text-sm font-medium transition-all"
          >
            <span>Explore Matches</span>
            <ChevronRight className="w-4 h-4 text-zinc-400" />
          </Link>
        </div>
      </div>

      {/* Main Conversion Funnel Hero */}
      <div className="rounded-2xl p-6 bg-gradient-to-b from-white/[0.04] to-transparent border border-white/[0.08] relative overflow-hidden">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6 relative z-10">
          <div className="w-full md:w-1/3 p-4 rounded-xl bg-white/[0.02] border border-white/[0.05] flex flex-col items-center text-center">
            <div className="flex items-center gap-2 text-zinc-400 text-xs font-semibold uppercase tracking-wider mb-2">
              <Clock className="w-4 h-4 text-zinc-500" />
              <span>Discovered (24h)</span>
            </div>
            <span className="text-3xl sm:text-4xl font-extrabold text-white font-mono tracking-tight">
              {funnel.fresh_jobs_count.toLocaleString()}
            </span>
            <span className="text-xs text-zinc-400 mt-1">Fresh marketplace postings</span>
          </div>

          <div className="hidden md:flex flex-col items-center justify-center text-zinc-500">
            <ArrowDown className="w-5 h-5 -rotate-90 text-emerald-400/60 animate-pulse" />
          </div>

          <div className="w-full md:w-1/3 p-4 rounded-xl bg-emerald-500/[0.04] border border-emerald-500/20 flex flex-col items-center text-center">
            <div className="flex items-center gap-2 text-emerald-400 text-xs font-semibold uppercase tracking-wider mb-2">
              <TrendingUp className="w-4 h-4 text-emerald-400" />
              <span>Strong Matches (≥70%)</span>
            </div>
            <span className="text-3xl sm:text-4xl font-extrabold text-emerald-300 font-mono tracking-tight">
              {funnel.strong_matches_count.toLocaleString()}
            </span>
            <span className="text-xs text-emerald-400/80 mt-1">Role, skill & location alignment</span>
          </div>

          <div className="hidden md:flex flex-col items-center justify-center text-zinc-500">
            <ArrowDown className="w-5 h-5 -rotate-90 text-emerald-400/60 animate-pulse" />
          </div>

          <div className="w-full md:w-1/3 p-4 rounded-xl bg-emerald-500/[0.09] border border-emerald-500/30 flex flex-col items-center text-center shadow-lg shadow-emerald-950/30">
            <div className="flex items-center gap-2 text-emerald-300 text-xs font-semibold uppercase tracking-wider mb-2">
              <Sparkles className="w-4 h-4 text-emerald-300" />
              <span>Excellent Matches (≥85%)</span>
            </div>
            <span className="text-3xl sm:text-4xl font-extrabold text-emerald-200 font-mono tracking-tight">
              {funnel.excellent_matches_count.toLocaleString()}
            </span>
            <span className="text-xs text-emerald-300/80 mt-1">Highest target yield</span>
          </div>
        </div>
      </div>

      {/* Grid: 2 Columns */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Recommended & New Jobs */}
        <div className="lg:col-span-2 space-y-6">
          {/* Top Recommended Section */}
          <div className="rounded-2xl p-6 bg-obsidian-950/60 border border-white/[0.07] space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-emerald-400" />
                <h2 className="text-base font-semibold text-white">Top Recommended Fits</h2>
              </div>
              <Link
                href="/jobs?view=for_you"
                className="text-xs text-emerald-400 hover:text-emerald-300 font-medium flex items-center gap-1 transition-colors"
              >
                View all <ChevronRight className="w-3.5 h-3.5" />
              </Link>
            </div>

            {(!data?.recommended_jobs || data.recommended_jobs.length === 0) ? (
              <p className="text-sm text-zinc-500 py-6 text-center">No scored matches yet. Run a sync or adjust preferences.</p>
            ) : (
              <div className="divide-y divide-white/[0.04]">
                {data.recommended_jobs.map((job) => (
                  <div key={job.id} className="py-3.5 flex items-center justify-between gap-4 group hover:bg-white/[0.02] px-2 rounded-lg transition-colors">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <h3 className="text-sm font-medium text-zinc-100 truncate group-hover:text-emerald-300 transition-colors">
                          {job.title}
                        </h3>
                        <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-white/[0.06] text-zinc-400">
                          {job.source}
                        </span>
                      </div>
                      <p className="text-xs text-zinc-400 truncate mt-0.5">
                        {job.company} • {job.location || job.remote_type || "Remote"}
                      </p>
                    </div>

                    <div className="flex items-center gap-3">
                      {job.match && (
                        <div className="text-right">
                          <span className="text-xs font-mono font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                            {Math.round(job.match.overall_score)}%
                          </span>
                        </div>
                      )}
                      <a
                        href={job.application_url}
                        target="_blank"
                        rel="noreferrer"
                        className="p-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-zinc-400 hover:text-white transition-colors"
                        title="Apply"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* New Arrivals Section */}
          <div className="rounded-2xl p-6 bg-obsidian-950/60 border border-white/[0.07] space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Flame className="w-4 h-4 text-amber-400" />
                <h2 className="text-base font-semibold text-white">Fresh Marketplace Arrivals</h2>
              </div>
              <Link
                href="/jobs?sort_by=freshness"
                className="text-xs text-zinc-400 hover:text-zinc-200 font-medium flex items-center gap-1 transition-colors"
              >
                Browse latest <ChevronRight className="w-3.5 h-3.5" />
              </Link>
            </div>

            {(!data?.new_jobs || data.new_jobs.length === 0) ? (
              <p className="text-sm text-zinc-500 py-6 text-center">No fresh jobs in the last window.</p>
            ) : (
              <div className="divide-y divide-white/[0.04]">
                {data.new_jobs.map((job) => (
                  <div key={job.id} className="py-3.5 flex items-center justify-between gap-4 group hover:bg-white/[0.02] px-2 rounded-lg transition-colors">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <h3 className="text-sm font-medium text-zinc-100 truncate group-hover:text-amber-300 transition-colors">
                          {job.title}
                        </h3>
                        <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-white/[0.06] text-zinc-400">
                          {job.source}
                        </span>
                      </div>
                      <p className="text-xs text-zinc-400 truncate mt-0.5">
                        {job.company} • {job.location || job.remote_type || "Remote"}
                      </p>
                    </div>

                    <div className="flex items-center gap-3 text-right">
                      {job.age_hours !== undefined && (
                        <span className="text-xs text-zinc-500 font-mono">
                          {Math.round(job.age_hours)}h ago
                        </span>
                      )}
                      <a
                        href={job.application_url}
                        target="_blank"
                        rel="noreferrer"
                        className="p-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-zinc-400 hover:text-white transition-colors"
                        title="View job"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right 1 Col: Application Status, Skill Gaps & Source Health */}
        <div className="space-y-6">
          {/* Application Status Breakdown */}
          <div className="rounded-2xl p-6 bg-obsidian-950/60 border border-white/[0.07] space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Bookmark className="w-4 h-4 text-emerald-400" />
                <h2 className="text-base font-semibold text-white">Application Pipeline</h2>
              </div>
              <Link
                href="/saved"
                className="text-xs text-emerald-400 hover:text-emerald-300 font-medium flex items-center gap-1 transition-colors"
              >
                Track <ChevronRight className="w-3.5 h-3.5" />
              </Link>
            </div>

            <div className="grid grid-cols-2 gap-3 pt-2">
              <div className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.05]">
                <span className="text-[11px] text-zinc-400 uppercase font-semibold">Saved</span>
                <p className="text-2xl font-bold font-mono text-zinc-100 mt-1">{appSummary.saved}</p>
              </div>
              <div className="p-3 rounded-xl bg-blue-500/[0.04] border border-blue-500/20">
                <span className="text-[11px] text-blue-400 uppercase font-semibold">Applied</span>
                <p className="text-2xl font-bold font-mono text-blue-300 mt-1">{appSummary.applied}</p>
              </div>
              <div className="p-3 rounded-xl bg-amber-500/[0.04] border border-amber-500/20">
                <span className="text-[11px] text-amber-400 uppercase font-semibold">Interviewing</span>
                <p className="text-2xl font-bold font-mono text-amber-300 mt-1">{appSummary.interviewing}</p>
              </div>
              <div className="p-3 rounded-xl bg-emerald-500/[0.04] border border-emerald-500/20">
                <span className="text-[11px] text-emerald-400 uppercase font-semibold">Offer</span>
                <p className="text-2xl font-bold font-mono text-emerald-300 mt-1">{appSummary.offered}</p>
              </div>
            </div>
          </div>

          {/* Skill Gaps Widget */}
          <div className="rounded-2xl p-6 bg-obsidian-950/60 border border-white/[0.07] space-y-4">
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-violet-400" />
              <h2 className="text-base font-semibold text-white">Target Skill Gaps</h2>
            </div>
            <p className="text-xs text-zinc-400">
              Most requested skills in matching roles missing from your current profile:
            </p>

            {(!data?.skill_gaps || data.skill_gaps.length === 0) ? (
              <p className="text-xs text-zinc-500 py-3 text-center">No critical skill gaps identified.</p>
            ) : (
              <div className="space-y-2.5 pt-1">
                {data.skill_gaps.map((gap) => (
                  <div key={gap.skill} className="flex items-center justify-between text-xs">
                    <span className="font-medium text-zinc-200">{gap.skill}</span>
                    <div className="flex items-center gap-2">
                      <div className="w-20 h-1.5 rounded-full bg-white/[0.08] overflow-hidden">
                        <div
                          className="h-full bg-violet-400 rounded-full"
                          style={{ width: `${Math.min(gap.demand_percentage, 100)}%` }}
                        />
                      </div>
                      <span className="text-zinc-400 font-mono w-9 text-right">
                        {gap.demand_percentage}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Source Health & Last Sync */}
          <div className="rounded-2xl p-6 bg-obsidian-950/60 border border-white/[0.07] space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <h2 className="text-base font-semibold text-white">Source Health</h2>
              </div>
              <span className={`text-[11px] font-semibold uppercase px-2 py-0.5 rounded-full ${
                data?.source_health.status === "ok"
                  ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                  : "bg-amber-500/10 text-amber-400 border border-amber-500/20"
              }`}>
                {data?.source_health.healthy_count}/{data?.source_health.total_sources} Active
              </span>
            </div>

            <div className="space-y-2 pt-1">
              {Object.entries(data?.source_health.sources || {}).map(([name, ok]) => (
                <div key={name} className="flex items-center justify-between text-xs py-1">
                  <span className="capitalize text-zinc-300">{name}</span>
                  <span className={`flex items-center gap-1.5 font-medium ${ok ? "text-emerald-400" : "text-rose-400"}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${ok ? "bg-emerald-400" : "bg-rose-400"}`} />
                    {ok ? "Operational" : "Degraded"}
                  </span>
                </div>
              ))}
            </div>

            <div className="border-t border-white/[0.06] pt-3 text-[11px] text-zinc-400 flex items-center justify-between">
              <span>Last synchronized</span>
              <span className="font-mono text-zinc-300">
                {formatTime(data?.sync_status.last_sync_time)}
              </span>
            </div>
          </div>
        </div>
      </div>

      <SyncProgressModal
        isOpen={syncModalOpen}
        onClose={() => {
          setSyncModalOpen(false);
          setSyncJobId(null);
          fetchDashboard();
        }}
        jobId={syncJobId}
        source={syncSource}
        onSyncComplete={() => {
          fetchDashboard();
        }}
      />
    </div>
  );
}
