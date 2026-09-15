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

  return (
    <div className="space-y-8 pb-16">
      {/* Action Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-200">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 font-mono tracking-wider uppercase">
              AUTOMATED INGESTION & DIAGNOSTICS
            </span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">System Settings & Scheduler</h1>
          <p className="text-xs text-slate-500 max-w-2xl leading-relaxed">
            Configure automated crawl schedules, audit ingestion logs, and run telemetry diagnostics.
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
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-blue-50 border border-blue-200 text-blue-600">
              <CalendarClock className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">Automated Ingestion Schedule</h3>
              <p className="text-[11px] text-slate-500">
                Periodic background worker runs crawl, freshness gate, and dedup pipeline automatically.
              </p>
            </div>
          </div>

          <button
            onClick={handleTriggerScheduleNow}
            disabled={triggeringSchedule}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 text-emerald-700 rounded-xl text-xs font-semibold transition-colors shadow-xs"
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
                    ? "bg-emerald-50/70 border-emerald-300 text-slate-900 shadow-xs"
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
                  {opt.enabled ? `Runs 4x/day (${opt.hours}h window)` : "Triggered on demand only"}
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
                Status:{" "}
                <strong className={schedule.auto_sync_enabled ? "text-emerald-700 font-bold" : "text-amber-700 font-bold"}>
                  {schedule.auto_sync_enabled ? `Active (${schedule.sync_interval_hours}h)` : "Disabled"}
                </strong>
              </span>
            </div>

            {schedule.next_run_at && (
              <div className="text-slate-600">
                Next scheduled sync:{" "}
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
                Last run:{" "}
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

      {/* Sync Ingestion Audit History */}
      <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-card-subtle space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-lg bg-slate-100 border border-slate-200 text-slate-600">
              <History className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">Ingestion Audit Log</h3>
              <p className="text-[11px] text-slate-500">Recent cron and manual trigger discovery runs</p>
            </div>
          </div>
          <button
            onClick={fetchSyncHistory}
            disabled={loadingHistory}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 rounded-xl text-xs font-semibold transition-colors shadow-xs"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loadingHistory ? "animate-spin text-emerald-600" : ""}`} />
            <span>Refresh Logs</span>
          </button>
        </div>

        {syncHistory.length > 0 ? (
          <div className="overflow-x-auto rounded-xl border border-slate-200">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="text-[11px] uppercase font-mono bg-slate-50 text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="py-3 px-4">Timestamp (IST)</th>
                  <th className="py-3 px-4">Source Board</th>
                  <th className="py-3 px-4">Discovered</th>
                  <th className="py-3 px-4">Fresh</th>
                  <th className="py-3 px-4">Canonical Saved</th>
                  <th className="py-3 px-4">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {syncHistory.map((item, idx) => (
                  <tr key={idx} className="hover:bg-slate-50/70 transition-colors">
                    <td className="py-2.5 px-4 font-mono text-slate-500">
                      {new Date(item.timestamp).toLocaleString("en-IN", {
                        hour: "2-digit",
                        minute: "2-digit",
                        second: "2-digit",
                        day: "numeric",
                        month: "short",
                      })}
                    </td>
                    <td className="py-2.5 px-4 font-semibold text-slate-900 capitalize">{item.source}</td>
                    <td className="py-2.5 px-4 font-tabular">{item.total_discovered ?? "-"}</td>
                    <td className="py-2.5 px-4 text-blue-600 font-tabular font-semibold">{item.fresh_jobs ?? "-"}</td>
                    <td className="py-2.5 px-4 text-emerald-600 font-tabular font-bold">{item.canonical_saved ?? "-"}</td>
                    <td className="py-2.5 px-4">
                      <span
                        className={`px-2 py-0.5 rounded-md text-[10px] font-mono font-medium ${
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
                        <span className="block text-[10px] text-rose-600 mt-0.5 max-w-[200px] truncate">
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
          <div className="text-xs text-slate-500 py-6 text-center font-mono bg-slate-50 rounded-xl border border-slate-200">
            No sync telemetry records logged yet.
          </div>
        )}
      </div>
    </div>
  );
}
