"use client";

import { useEffect, useState } from "react";
import {
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  History,
} from "lucide-react";

interface Preferences {
  freshness_hours: number;
  experience_max_years: number;
  preferred_technologies: string[];
  preferred_industries?: string[];
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

export default function AuditLogsPage() {
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const [loading, setLoading] = useState(true);
  const [message] = useState<{ type: "success" | "error"; text: string } | null>(null);

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

  useEffect(() => {
    fetchPrefs();
    fetchSyncHistory();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-sm text-zinc-500 font-mono">
        <RefreshCw className="w-4 h-4 animate-spin mr-2 text-emerald-400" />
        Loading ingestion audit logs...
      </div>
    );
  }

  if (!prefs) {
    return (
      <div className="p-8 rounded-2xl bg-obsidian-900/60 border border-white/[0.08] text-center text-sm text-zinc-400">
        Audit log service unreachable.
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-16">
      {/* Action Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-white/[0.08]">
        <div>
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-mono uppercase tracking-wider mb-2">
            <span>Ingestion Audit Logs</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Ingestion Audit Logs</h1>
          <p className="text-sm text-zinc-400 mt-1">
            Only ingestion audit logs are visible.
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

      {/* Sync Ingestion Audit History */}
      <div className="p-6 rounded-2xl bg-obsidian-900/60 border border-white/[0.08] shadow-surface-inset space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-lg bg-zinc-500/10 border border-white/[0.08] text-zinc-400">
              <History className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">Ingestion Audit Log</h3>
              <p className="text-[11px] text-zinc-400">Recent cron and trigger discovery runs</p>
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
