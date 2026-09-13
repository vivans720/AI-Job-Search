"use client";

import { useEffect, useState } from "react";
import {
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  History,
  Clock,
  CalendarClock,
  Play,
  Binary,
} from "lucide-react";

interface Preferences {
  freshness_hours: number;
  experience_max_years: number;
  preferred_technologies: string[];
  preferred_industries?: string[];
  sync_interval_hours?: number;
  auto_sync_enabled?: boolean;
  last_auto_sync_at?: string | null;
  ai_provider?: string | null;
  ai_model?: string | null;
  ai_base_url?: string | null;
  has_custom_api_key?: boolean;
}

interface ScheduleInfo {
  auto_sync_enabled: boolean;
  sync_interval_hours: number;
  last_auto_sync_at: string | null;
  next_run_at: string | null;
  seconds_until_next_run: number | null;
}

interface SyncLogEntry {
  timestamp: string;
  source: string;
  status: string;
  total_discovered?: number;
  fresh_jobs?: number;
  canonical_saved?: number;
  duration_ms?: number;
  error?: string;
}

export default function SettingsPage() {
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Scheduler states
  const [schedule, setSchedule] = useState<ScheduleInfo | null>(null);
  const [updatingSchedule, setUpdatingSchedule] = useState(false);
  const [triggeringSchedule, setTriggeringSchedule] = useState(false);

  // Sync history states
  const [syncHistory, setSyncHistory] = useState<SyncLogEntry[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);





  // Phase 43 Job Intelligence Pipeline states
  const [pipelineRunning, setPipelineRunning] = useState<boolean>(false);
  const [pipelineResult, setPipelineResult] = useState<{
    status: string;
    total_requested: number;
    ai_enriched: number;
    embeddings_generated: number;
    matches_evaluated: number;
  } | null>(null);

  const handleTriggerPipelineEnrich = async () => {
    setPipelineRunning(true);
    try {
      const res = await fetch("http://localhost:8000/api/v1/jobs/pipeline/enrich", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ limit: 10 }),
      });
      if (res.ok) {
        const data = await res.json();
        setPipelineResult(data);
      }
    } catch {
      // Ignored
    } finally {
      setPipelineRunning(false);
    }
  };

  const fetchPrefs = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/v1/preferences");
      if (res.ok) {
        const data = await res.json();
        setPrefs(data);
      }
    } catch {
      // Backend offline
    } finally {
      setLoading(false);
    }
  };

  const fetchSchedule = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/v1/sources/schedule");
      if (res.ok) {
        const data = await res.json();
        setSchedule(data);
      }
    } catch {
      // Backend offline
    }
  };

  const fetchSyncHistory = async () => {
    setLoadingHistory(true);
    try {
      const res = await fetch("http://localhost:8000/api/v1/sources/history?limit=8");
      if (res.ok) {
        const data = await res.json();
        setSyncHistory(data.history || []);
      }
    } catch {
      // Sync history unreachable
    } finally {
      setLoadingHistory(false);
    }
  };



  const handleUpdateInterval = async (hours: number, enabled: boolean) => {
    setUpdatingSchedule(true);
    setMessage(null);
    try {
      const res = await fetch("http://localhost:8000/api/v1/preferences", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sync_interval_hours: hours,
          auto_sync_enabled: enabled,
        }),
      });
      if (res.ok) {
        const updated = await res.json();
        setPrefs(updated);
        await fetchSchedule();
        setMessage({
          type: "success",
          text: enabled
            ? `Automated sync interval set to every ${hours} hours.`
            : "Automated scheduled ingestion disabled.",
        });
      } else {
        setMessage({ type: "error", text: "Failed to update scheduler settings." });
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to update schedule.";
      setMessage({ type: "error", text: msg });
    } finally {
      setUpdatingSchedule(false);
    }
  };

  const handleTriggerScheduleNow = async () => {
    setTriggeringSchedule(true);
    setMessage(null);
    try {
      const res = await fetch("http://localhost:8000/api/v1/sources/schedule/trigger", {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        await fetchSchedule();
        setMessage({
          type: "success",
          text: data.message || "Scheduled sync triggered successfully.",
        });
        setTimeout(fetchSyncHistory, 2000);
      } else {
        setMessage({ type: "error", text: "Failed to trigger scheduled sync." });
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Trigger error.";
      setMessage({ type: "error", text: msg });
    } finally {
      setTriggeringSchedule(false);
    }
  };

  useEffect(() => {
    fetchPrefs();
    fetchSchedule();
    fetchSyncHistory();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-sm text-zinc-500 font-mono">
        <RefreshCw className="w-4 h-4 animate-spin mr-2 text-emerald-400" />
        Loading settings and audit telemetry...
      </div>
    );
  }

  if (!prefs) {
    return (
      <div className="p-8 rounded-2xl bg-obsidian-900/60 border border-white/[0.08] text-center text-sm text-zinc-400">
        Preferences service unreachable. Ensure FastAPI backend is running on port 8000.
      </div>
    );
  }

  const currentInterval = prefs.sync_interval_hours ?? 24;
  const isAutoEnabled = prefs.auto_sync_enabled ?? true;

  return (
    <div className="space-y-8 pb-16">
      {/* Action Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-white/[0.08]">
        <div>
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 text-xs font-mono uppercase tracking-wider mb-2">
            <span>Automated Ingestion & Diagnostics</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">System Settings & Scheduler</h1>
          <p className="text-sm text-zinc-400 mt-1">
            Configure automated crawl schedules, audit ingestion logs, and run telemetry diagnostics.
          </p>
        </div>
      </div>

      {message && (
        <div
          className={`p-4 rounded-xl flex items-center gap-3 text-xs border backdrop-blur-md transition-all ${
            message.type === "success"
              ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-300"
              : "bg-rose-500/10 border-rose-500/20 text-rose-300"
          }`}
        >
          {message.type === "success" ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
          ) : (
            <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
          )}
          <span className="font-medium">{message.text}</span>
        </div>
      )}



      {/* Phase 43: Job Intelligence Pipeline Control Card */}
      <div className="p-6 rounded-2xl bg-obsidian-900/60 border border-white/[0.08] shadow-surface-inset space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-400">
              <Binary className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">Phase 43 — Job Intelligence Pipeline</h3>
              <p className="text-[11px] text-zinc-400">
                Connects ingestion + AI skill normalization + 384d BGE embedding + savepoint persistence + 6D matching.
              </p>
            </div>
          </div>

          <button
            onClick={handleTriggerPipelineEnrich}
            disabled={pipelineRunning}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-purple-600/20 hover:bg-purple-600/30 border border-purple-500/30 text-purple-300 rounded-xl text-xs font-medium transition-colors"
          >
            <Play className={`w-3.5 h-3.5 ${pipelineRunning ? "animate-spin" : ""}`} />
            <span>{pipelineRunning ? "Enriching Pipeline..." : "Enrich Active Jobs"}</span>
          </button>
        </div>

        {/* Pipeline Architecture Badges */}
        <div className="p-3.5 rounded-xl bg-obsidian-950/40 border border-white/[0.04]">
          <div className="text-[10px] font-mono text-zinc-400 uppercase mb-2">Connected Pipeline Flow:</div>
          <div className="flex flex-wrap items-center gap-1.5 text-[11px] font-mono text-zinc-400">
            <span className="px-2 py-0.5 rounded bg-white/[0.04] text-zinc-300 border border-white/[0.08]">Raw Job</span>
            <span className="text-zinc-600">→</span>
            <span className="px-2 py-0.5 rounded bg-white/[0.04] text-zinc-300 border border-white/[0.08]">Parser</span>
            <span className="text-zinc-600">→</span>
            <span className="px-2 py-0.5 rounded bg-white/[0.04] text-zinc-300 border border-white/[0.08]">Normalizer</span>
            <span className="text-zinc-600">→</span>
            <span className="px-2 py-0.5 rounded bg-white/[0.04] text-zinc-300 border border-white/[0.08]">Freshness (≤24h)</span>
            <span className="text-zinc-600">→</span>
            <span className="px-2 py-0.5 rounded bg-white/[0.04] text-zinc-300 border border-white/[0.08]">Dedup L1-4</span>
            <span className="text-zinc-600">→</span>
            <span className="px-2 py-0.5 rounded bg-purple-500/10 text-purple-300 border border-purple-500/20">AI Extraction</span>
            <span className="text-zinc-600">→</span>
            <span className="px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">BGE 384d</span>
            <span className="text-zinc-600">→</span>
            <span className="px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">Savepoint Persist</span>
            <span className="text-zinc-600">→</span>
            <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">Candidate Matching</span>
          </div>
        </div>

        {pipelineResult && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-3 bg-obsidian-950/60 border border-white/[0.06] rounded-xl">
              <div className="text-[10px] uppercase font-mono text-zinc-400">Processed</div>
              <div className="text-lg font-bold text-zinc-200 mt-1 font-mono">
                {pipelineResult.total_requested}
              </div>
            </div>
            <div className="p-3 bg-obsidian-950/60 border border-white/[0.06] rounded-xl">
              <div className="text-[10px] uppercase font-mono text-purple-400">AI Enriched</div>
              <div className="text-lg font-bold text-purple-400 mt-1 font-mono">
                {pipelineResult.ai_enriched}
              </div>
            </div>
            <div className="p-3 bg-obsidian-950/60 border border-white/[0.06] rounded-xl">
              <div className="text-[10px] uppercase font-mono text-indigo-400">Embeddings</div>
              <div className="text-lg font-bold text-indigo-400 mt-1 font-mono">
                {pipelineResult.embeddings_generated}
              </div>
            </div>
            <div className="p-3 bg-obsidian-950/60 border border-white/[0.06] rounded-xl">
              <div className="text-[10px] uppercase font-mono text-emerald-400">Matches Evaluated</div>
              <div className="text-lg font-bold text-emerald-400 mt-1 font-mono">
                {pipelineResult.matches_evaluated}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Scheduler Configuration Card */}
      <div className="p-6 rounded-2xl bg-obsidian-900/60 border border-white/[0.08] shadow-surface-inset space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
              <CalendarClock className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">Automated Ingestion Schedule</h3>
              <p className="text-[11px] text-zinc-400">
                Periodic background worker runs crawl, freshness gate, and dedup pipeline automatically.
              </p>
            </div>
          </div>

          <button
            onClick={handleTriggerScheduleNow}
            disabled={triggeringSchedule}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600/20 hover:bg-emerald-600/30 border border-emerald-500/30 text-emerald-300 rounded-xl text-xs font-medium transition-colors"
          >
            <Play className={`w-3.5 h-3.5 ${triggeringSchedule ? "animate-spin" : ""}`} />
            <span>{triggeringSchedule ? "Triggering..." : "Run Schedule Now"}</span>
          </button>
        </div>

        {/* Schedule Interval Selection */}
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
          {[
            { label: "Every 6 hours", hours: 6, enabled: true },
            { label: "Every 12 hours", hours: 12, enabled: true },
            { label: "Every 24 hours", hours: 24, enabled: true },
            { label: "Manual Only", hours: 0, enabled: false },
          ].map((opt) => {
            const isSelected =
              (!opt.enabled && !isAutoEnabled) ||
              (opt.enabled && isAutoEnabled && currentInterval === opt.hours);

            return (
              <button
                key={opt.label}
                disabled={updatingSchedule}
                onClick={() => handleUpdateInterval(opt.hours, opt.enabled)}
                className={`p-4 rounded-xl border text-left transition-all ${
                  isSelected
                    ? "bg-emerald-950/40 border-emerald-500/40 text-white shadow-surface-glow"
                    : "bg-obsidian-950/40 border-white/[0.06] text-zinc-400 hover:text-zinc-200 hover:border-white/[0.12]"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-semibold">{opt.label}</span>
                  {isSelected && <span className="w-2 h-2 rounded-full bg-emerald-400"></span>}
                </div>
                <span className="text-[11px] text-zinc-500 block font-mono">
                  {opt.enabled ? `Runs 4x/day (${opt.hours}h window)` : "Triggered on demand only"}
                </span>
              </button>
            );
          })}
        </div>

        {/* Schedule Timing Status */}
        {schedule && (
          <div className="p-4 rounded-xl bg-obsidian-950/60 border border-white/[0.06] flex flex-wrap items-center justify-between gap-4 text-xs font-mono">
            <div className="flex items-center gap-2 text-zinc-400">
              <Clock className="w-4 h-4 text-zinc-500" />
              <span>
                Status:{" "}
                <strong className={schedule.auto_sync_enabled ? "text-emerald-400" : "text-amber-400"}>
                  {schedule.auto_sync_enabled ? `Active (${schedule.sync_interval_hours}h)` : "Disabled"}
                </strong>
              </span>
            </div>

            {schedule.next_run_at && (
              <div className="text-zinc-400">
                Next scheduled sync:{" "}
                <span className="text-zinc-200">
                  {new Date(schedule.next_run_at).toLocaleString("en-IN", {
                    hour: "2-digit",
                    minute: "2-digit",
                    day: "numeric",
                    month: "short",
                  })}
                </span>
              </div>
            )}

            {schedule.last_auto_sync_at && (
              <div className="text-zinc-400">
                Last run:{" "}
                <span className="text-zinc-300">
                  {new Date(schedule.last_auto_sync_at).toLocaleString("en-IN", {
                    hour: "2-digit",
                    minute: "2-digit",
                    day: "numeric",
                    month: "short",
                  })}
                </span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Sync Ingestion Audit History */}
      <div className="p-6 rounded-2xl bg-obsidian-900/60 border border-white/[0.08] shadow-surface-inset space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-lg bg-zinc-500/10 border border-white/[0.08] text-zinc-400">
              <History className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">Ingestion Audit Log</h3>
              <p className="text-[11px] text-zinc-400">Recent cron and manual trigger discovery runs</p>
            </div>
          </div>
          <button
            onClick={fetchSyncHistory}
            disabled={loadingHistory}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-obsidian-800 hover:bg-obsidian-700 border border-white/[0.08] text-zinc-300 rounded-xl text-xs font-medium transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loadingHistory ? "animate-spin text-emerald-400" : ""}`} />
            <span>Refresh Logs</span>
          </button>
        </div>

        {syncHistory.length > 0 ? (
          <div className="overflow-x-auto rounded-xl border border-white/[0.06]">
            <table className="w-full text-left text-xs text-zinc-300">
              <thead className="text-[11px] uppercase font-mono bg-obsidian-950/80 text-zinc-400 border-b border-white/[0.06]">
                <tr>
                  <th className="py-3 px-4">Timestamp (IST)</th>
                  <th className="py-3 px-4">Source Board</th>
                  <th className="py-3 px-4">Discovered</th>
                  <th className="py-3 px-4">Fresh</th>
                  <th className="py-3 px-4">Canonical Saved</th>
                  <th className="py-3 px-4">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04] bg-obsidian-950/40">
                {syncHistory.map((item, idx) => (
                  <tr key={idx} className="hover:bg-white/[0.02] transition-colors">
                    <td className="py-2.5 px-4 font-mono text-zinc-400">
                      {new Date(item.timestamp).toLocaleString("en-IN", {
                        hour: "2-digit",
                        minute: "2-digit",
                        second: "2-digit",
                        day: "numeric",
                        month: "short",
                      })}
                    </td>
                    <td className="py-2.5 px-4 font-medium text-white capitalize">{item.source}</td>
                    <td className="py-2.5 px-4 font-tabular">{item.total_discovered ?? "-"}</td>
                    <td className="py-2.5 px-4 text-cyan-400 font-tabular font-medium">{item.fresh_jobs ?? "-"}</td>
                    <td className="py-2.5 px-4 text-emerald-400 font-tabular font-semibold">{item.canonical_saved ?? "-"}</td>
                    <td className="py-2.5 px-4">
                      <span
                        className={`px-2 py-0.5 rounded-md text-[10px] font-mono ${
                          item.status === "success"
                            ? "bg-emerald-500/10 text-emerald-400"
                            : item.status === "error"
                              ? "bg-rose-500/10 text-rose-400"
                              : "bg-zinc-500/10 text-zinc-400"
                        }`}
                      >
                        {item.status}
                      </span>
                      {item.error && (
                        <span className="block text-[10px] text-rose-400/70 mt-0.5 max-w-[200px] truncate">
                          {item.error}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-xs text-zinc-500 py-6 text-center font-mono bg-obsidian-950/30 rounded-xl border border-white/[0.04]">
            No sync telemetry records logged yet.
          </div>
        )}
      </div>
    </div>
  );
}
