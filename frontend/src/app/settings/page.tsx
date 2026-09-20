"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  History,
  Clock,
  CalendarClock,
  Play,
  ChevronDown,
  ChevronRight,
  Info,
  Shield,
  Cpu,
} from "lucide-react";
import { getApiUrl } from "@/lib/api";

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

interface AutonomyPolicy {
  search: string;
  analyze: string;
  save_job: string;
  dismiss_job: string;
  update_pipeline_status: string;
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
  const [expandedRow, setExpandedRow] = useState<number | null>(null);
  const [statusFilter, setStatusFilter] = useState<"all" | "success" | "error">("all");

  // Agent Autonomy states
  const [autonomyPolicy, setAutonomyPolicy] = useState<AutonomyPolicy>({
    search: "autonomous",
    analyze: "autonomous",
    save_job: "approval_required",
    dismiss_job: "approval_required",
    update_pipeline_status: "approval_required",
  });
  const [updatingPolicy, setUpdatingPolicy] = useState(false);

  const fetchPrefs = async () => {
    try {
      const res = await fetch(getApiUrl("/api/v1/preferences"));
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
      const res = await fetch(getApiUrl("/api/v1/sources/schedule"));
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
      const res = await fetch(getApiUrl("/api/v1/sources/history?limit=20"));
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
      const res = await fetch(getApiUrl("/api/v1/preferences"), {
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
            ? `Automated search set to run every ${hours} hours.`
            : "Automated scheduled search disabled.",
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

  const fetchAutonomyPolicy = async () => {
    try {
      const res = await fetch(getApiUrl("/api/v1/agent/autonomy-policy"));
      if (res.ok) {
        const data = await res.json();
        if (data.autonomy_policy) {
          setAutonomyPolicy(data.autonomy_policy);
        }
      }
    } catch {
      // Backend offline
    }
  };

  const handleTogglePolicy = async (actionKey: keyof AutonomyPolicy) => {
    setUpdatingPolicy(true);
    setMessage(null);
    const nextVal = autonomyPolicy[actionKey] === "autonomous" ? "approval_required" : "autonomous";
    const updated = { ...autonomyPolicy, [actionKey]: nextVal };
    try {
      const res = await fetch(getApiUrl("/api/v1/agent/autonomy-policy"), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ autonomy_policy: updated }),
      });
      if (res.ok) {
        const data = await res.json();
        setAutonomyPolicy(data.autonomy_policy);
        setMessage({
          type: "success",
          text: `Autonomy for ${actionKey} set to ${nextVal}.`,
        });
      } else {
        setMessage({ type: "error", text: "Failed to update autonomy policy." });
      }
    } catch {
      setMessage({ type: "error", text: "Network error updating policy." });
    } finally {
      setUpdatingPolicy(false);
    }
  };

  const handleTriggerScheduleNow = async () => {
    setTriggeringSchedule(true);
    setMessage(null);
    try {
      const res = await fetch(getApiUrl("/api/v1/sources/schedule/trigger"), {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        await fetchSchedule();
        setMessage({
          type: "success",
          text: data.message || "Job search triggered successfully.",
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
    fetchAutonomyPolicy();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-sm text-slate-500 font-mono">
        <RefreshCw className="w-4 h-4 animate-spin mr-2 text-emerald-600" />
        Loading settings and audit telemetry...
      </div>
    );
  }

  if (!prefs) {
    return (
      <div className="p-8 rounded-2xl bg-white border border-slate-200 text-center text-sm text-slate-600 shadow-card-subtle">
        Preferences service unreachable. Ensure FastAPI backend is running on port 8000.
      </div>
    );
  }

  const currentInterval = prefs.sync_interval_hours ?? 24;
  const isAutoEnabled = prefs.auto_sync_enabled ?? true;

  const filteredHistory = syncHistory.filter((item) => {
    if (statusFilter === "all") return true;
    return item.status === statusFilter;
  });

  return (
    <div className="space-y-8 pb-16">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-200">
        <div className="space-y-1">
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Search Scheduler & Sync History</h1>
          <p className="text-xs text-slate-500 max-w-2xl leading-relaxed">
            Automate background discovery cycles across job boards and monitor fresh role ingestion.
          </p>
        </div>
      </div>

      {message && (
        <div
          className={`p-3.5 rounded-xl flex items-center gap-3 text-xs border transition-all ${
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

      {/* Scheduler Configuration Card */}
      <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-card-subtle space-y-6">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-blue-50 border border-blue-200 text-blue-600">
              <CalendarClock className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">Automated Job Discovery Cadence</h3>
              <p className="text-[11px] text-slate-500">
                Scheduled background worker scans boards, checks posting freshness, and filters duplicates.
              </p>
            </div>
          </div>

          <button
            onClick={handleTriggerScheduleNow}
            disabled={triggeringSchedule}
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-semibold transition-colors shadow-xs disabled:opacity-50"
          >
            <Play className={`w-3.5 h-3.5 fill-current ${triggeringSchedule ? "animate-spin" : ""}`} />
            <span>{triggeringSchedule ? "Searching now..." : "Run Search Now"}</span>
          </button>
        </div>

        {/* Schedule Interval Selection */}
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
          {[
            { label: "Every 6 hours", sublabel: "Runs 4x/day", hours: 6, enabled: true },
            { label: "Every 12 hours", sublabel: "Runs 2x/day", hours: 12, enabled: true },
            { label: "Every 24 hours", sublabel: "Runs 1x/day", hours: 24, enabled: true },
            { label: "Manual Only", sublabel: "Triggered on demand only", hours: 0, enabled: false },
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
                    ? "bg-emerald-50/70 border-emerald-400 text-slate-900 shadow-xs"
                    : "bg-white border-slate-200 text-slate-600 hover:text-slate-900 hover:border-slate-300 hover:bg-slate-50/60"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className={`text-xs font-bold ${isSelected ? "text-emerald-950" : "text-slate-800"}`}>
                    {opt.label}
                  </span>
                  {isSelected && <span className="w-2 h-2 rounded-full bg-emerald-600"></span>}
                </div>
                <span className="text-[11px] text-slate-500 block font-mono">
                  {opt.sublabel}
                </span>
              </button>
            );
          })}
        </div>

        {/* Schedule Timing Status */}
        {schedule && (
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex flex-wrap items-center justify-between gap-4 text-xs font-mono">
            <div className="flex items-center gap-2 text-slate-600">
              <Clock className="w-4 h-4 text-slate-400" />
              <span>
                Schedule Status:{" "}
                <strong className={schedule.auto_sync_enabled ? "text-emerald-700 font-bold" : "text-slate-700 font-bold"}>
                  {schedule.auto_sync_enabled ? `Active (Every ${schedule.sync_interval_hours}h)` : "Manual On-Demand"}
                </strong>
              </span>
            </div>

            {schedule.next_run_at && schedule.auto_sync_enabled && (
              <div className="text-slate-600">
                Next scheduled search:{" "}
                <span className="text-slate-900 font-semibold">
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
              <div className="text-slate-600">
                Last completed search:{" "}
                <span className="text-slate-900 font-semibold">
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

      {/* Agent Autonomy & Approval Gates (Phase 7) */}
      <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-card-subtle space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-purple-50 border border-purple-200 text-purple-600">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">Agent Autonomy & Approval Policy</h3>
              <p className="text-[11px] text-slate-500">
                Configure whether the agent can execute pipeline actions automatically or must pause for your review.
              </p>
            </div>
          </div>
          <Link
            href="/ai-provider"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 bg-slate-50 hover:bg-slate-100 text-slate-700 text-xs font-semibold transition-colors shrink-0 self-start sm:self-auto"
          >
            <Cpu className="w-3.5 h-3.5 text-emerald-600" />
            <span>Open Agent Config</span>
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[
            {
              key: "search" as keyof AutonomyPolicy,
              name: "Job Search & Retrieval",
              desc: "Querying external job boards and database.",
              fixed: true,
              value: "autonomous",
            },
            {
              key: "analyze" as keyof AutonomyPolicy,
              name: "Match Scoring & Ranking",
              desc: "Calculating skill match and ranking candidates.",
              fixed: true,
              value: "autonomous",
            },
            {
              key: "save_job" as keyof AutonomyPolicy,
              name: "Save Job to Pipeline",
              desc: "Bookmark newly recommended jobs to your saved list.",
              fixed: false,
              value: autonomyPolicy.save_job,
            },
            {
              key: "dismiss_job" as keyof AutonomyPolicy,
              name: "Dismiss Irrelevant Job",
              desc: "Hide jobs that do not fit candidate criteria.",
              fixed: false,
              value: autonomyPolicy.dismiss_job,
            },
            {
              key: "update_pipeline_status" as keyof AutonomyPolicy,
              name: "Update Application Stage",
              desc: "Progress job statuses (e.g. Preparing, Ready to Apply). 'Applied' status strictly requires explicit candidate confirmation.",
              fixed: false,
              value: autonomyPolicy.update_pipeline_status,
            },
          ].map((item) => {
            const isAuto = item.value === "autonomous";
            return (
              <div
                key={item.key}
                className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 flex items-center justify-between gap-4"
              >
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-slate-900">{item.name}</span>
                    <span
                      className={`px-1.5 py-0.5 rounded text-[10px] font-mono font-medium ${
                        isAuto
                          ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                          : "bg-amber-50 text-amber-700 border border-amber-200"
                      }`}
                    >
                      {isAuto ? "Autonomous" : "Approval Gate"}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-500">{item.desc}</p>
                </div>

                {!item.fixed ? (
                  <button
                    disabled={updatingPolicy}
                    onClick={() => handleTogglePolicy(item.key)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all shadow-xs border ${
                      isAuto
                        ? "bg-white border-slate-300 text-slate-700 hover:bg-slate-100"
                        : "bg-purple-600 border-purple-700 text-white hover:bg-purple-700"
                    }`}
                  >
                    {isAuto ? "Require Approval" : "Allow Auto"}
                  </button>
                ) : (
                  <span className="text-[11px] font-mono text-slate-400 italic">Always Auto</span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Sync Ingestion Audit History */}
      <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-card-subtle space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-lg bg-slate-100 border border-slate-200 text-slate-600">
              <History className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">Job Search Run History</h3>
              <p className="text-[11px] text-slate-500">Live log of automated and manual job discoveries</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Filter pills */}
            <div className="flex items-center bg-slate-100 p-0.5 rounded-lg border border-slate-200 text-xs">
              <button
                onClick={() => setStatusFilter("all")}
                className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors ${
                  statusFilter === "all" ? "bg-white text-slate-900 shadow-xs font-semibold" : "text-slate-500 hover:text-slate-900"
                }`}
              >
                All ({syncHistory.length})
              </button>
              <button
                onClick={() => setStatusFilter("success")}
                className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors ${
                  statusFilter === "success" ? "bg-white text-emerald-700 shadow-xs font-semibold" : "text-slate-500 hover:text-slate-900"
                }`}
              >
                Success
              </button>
              <button
                onClick={() => setStatusFilter("error")}
                className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors ${
                  statusFilter === "error" ? "bg-white text-rose-700 shadow-xs font-semibold" : "text-slate-500 hover:text-slate-900"
                }`}
              >
                Errors
              </button>
            </div>

            <button
              onClick={fetchSyncHistory}
              disabled={loadingHistory}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 rounded-xl text-xs font-semibold transition-colors shadow-xs"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loadingHistory ? "animate-spin text-emerald-600" : ""}`} />
              <span>Refresh</span>
            </button>
          </div>
        </div>

        {filteredHistory.length > 0 ? (
          <div className="overflow-x-auto rounded-xl border border-slate-200">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="text-[11px] uppercase font-mono bg-slate-50 text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="py-3 px-4 w-8"></th>
                  <th className="py-3 px-4">Timestamp (IST)</th>
                  <th className="py-3 px-4">Job Board</th>
                  <th className="py-3 px-4 text-right">Discovered</th>
                  <th className="py-3 px-4 text-right">
                    <span className="inline-flex items-center justify-end gap-1 w-full">
                      Fresh
                      <span title="Jobs posted within configured freshness window">
                        <Info className="w-3 h-3 text-slate-400 cursor-help" />
                      </span>
                    </span>
                  </th>
                  <th className="py-3 px-4 text-right">
                    <span className="inline-flex items-center justify-end gap-1 w-full">
                      New Jobs Saved
                      <span title="Unique non-duplicate jobs saved to your radar feed">
                        <Info className="w-3 h-3 text-slate-400 cursor-help" />
                      </span>
                    </span>
                  </th>
                  <th className="py-3 px-4 text-center">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {filteredHistory.map((item, idx) => {
                  const isExpanded = expandedRow === idx;
                  const discoveredCount = item.total_discovered ?? 0;
                  const freshCount = item.fresh_jobs ?? 0;
                  const savedCount = item.canonical_saved ?? 0;

                  return (
                    <tr key={idx} className="group hover:bg-slate-50/70 transition-colors">
                      <td className="py-2.5 pl-3 pr-1">
                        {item.error ? (
                          <button
                            onClick={() => setExpandedRow(isExpanded ? null : idx)}
                            className="p-1 hover:bg-slate-200 rounded text-slate-500"
                            title="Toggle error details"
                          >
                            {isExpanded ? (
                              <ChevronDown className="w-3.5 h-3.5" />
                            ) : (
                              <ChevronRight className="w-3.5 h-3.5" />
                            )}
                          </button>
                        ) : null}
                      </td>
                      <td className="py-2.5 px-4 font-mono text-slate-500">
                        {new Date(item.timestamp).toLocaleString("en-IN", {
                          hour: "2-digit",
                          minute: "2-digit",
                          second: "2-digit",
                          day: "numeric",
                          month: "short",
                        })}
                      </td>
                      <td className="py-2.5 px-4 font-semibold text-slate-900 capitalize">
                        {item.source.replace(/_/g, " ")}
                      </td>
                      <td className="py-2.5 px-4 text-right font-mono tabular-nums text-slate-700">
                        {discoveredCount > 0 ? discoveredCount : <span className="text-slate-400 font-normal">0</span>}
                      </td>
                      <td className="py-2.5 px-4 text-right font-mono tabular-nums">
                        {freshCount > 0 ? (
                          <span className="text-blue-700 font-semibold">{freshCount}</span>
                        ) : (
                          <span className="text-slate-400 font-normal">0</span>
                        )}
                      </td>
                      <td className="py-2.5 px-4 text-right font-mono tabular-nums">
                        {savedCount > 0 ? (
                          <span className="text-emerald-700 font-bold">{savedCount}</span>
                        ) : (
                          <span className="text-slate-400 font-normal">0</span>
                        )}
                      </td>
                      <td className="py-2.5 px-4 text-center">
                        <span
                          className={`inline-block px-2 py-0.5 rounded-md text-[10px] font-mono font-medium ${
                            item.status === "success"
                              ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                              : item.status === "error"
                                ? "bg-rose-50 text-rose-700 border border-rose-200"
                                : "bg-slate-100 text-slate-700"
                          }`}
                        >
                          {item.status}
                        </span>
                        {item.error && (
                          <div className="mt-1 text-left">
                            <span className="text-[10px] text-rose-600 max-w-[220px] truncate block font-mono">
                              {item.error}
                            </span>
                            {isExpanded && (
                              <div className="mt-2 p-2 bg-rose-50/80 border border-rose-200 rounded-lg text-[11px] text-rose-800 font-mono whitespace-pre-wrap">
                                {item.error}
                              </div>
                            )}
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-xs text-slate-500 py-8 text-center font-mono bg-slate-50 rounded-xl border border-slate-200">
            {statusFilter === "all"
              ? "No search runs recorded yet."
              : `No runs found with status: ${statusFilter}.`}
          </div>
        )}
      </div>
    </div>
  );
}
