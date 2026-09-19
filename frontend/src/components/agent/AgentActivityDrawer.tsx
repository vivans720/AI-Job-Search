"use client";

import React, { useEffect, useState, useCallback } from "react";
import { X, Activity, RefreshCw } from "lucide-react";
import { AgentRun, fetchAgentRuns } from "@/lib/api";
import { AgentRunTimeline } from "./AgentRunTimeline";
import { useAgentActivity } from "@/hooks/useAgentActivity";

interface AgentActivityDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  activeRunId?: string | null;
}

export const AgentActivityDrawer: React.FC<AgentActivityDrawerProps> = ({
  isOpen,
  onClose,
  activeRunId,
}) => {
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(activeRunId || null);
  const [loadingRuns, setLoadingRuns] = useState(false);

  const { run, events } = useAgentActivity(selectedRunId);

  useEffect(() => {
    if (activeRunId) {
      setSelectedRunId(activeRunId);
    }
  }, [activeRunId]);

  const loadRuns = useCallback(async () => {
    try {
      setLoadingRuns(true);
      const data = await fetchAgentRuns(15, 0);
      setRuns(data);
      if (!selectedRunId && data.length > 0) {
        setSelectedRunId(data[0].id);
      }
    } catch (e) {
      console.error("Failed to load agent runs", e);
    } finally {
      setLoadingRuns(false);
    }
  }, [selectedRunId]);

  useEffect(() => {
    if (isOpen) {
      loadRuns();
    }
  }, [isOpen, loadRuns]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-xs transition-opacity" onClick={onClose} />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-2xl bg-white shadow-2xl flex flex-col">
          {/* Top Bar */}
          <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50/70">
            <div className="flex items-center gap-2.5">
              <Activity className="w-5 h-5 text-emerald-600" />
              <h3 className="text-base font-semibold text-slate-900">Agent Observability & Activity</h3>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={loadRuns}
                className="p-1.5 rounded-lg text-slate-500 hover:text-slate-700 hover:bg-slate-200/60 transition"
                title="Refresh Runs"
              >
                <RefreshCw className={`w-4 h-4 ${loadingRuns ? "animate-spin" : ""}`} />
              </button>
              <button
                onClick={onClose}
                className="p-1.5 rounded-lg text-slate-500 hover:text-slate-700 hover:bg-slate-200/60 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Drawer Body */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {/* Run Selector Pills */}
            {runs.length > 0 && (
              <div>
                <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-2">
                  Recent Runs
                </label>
                <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-none">
                  {runs.map((r) => {
                    const isSelected = r.id === selectedRunId;
                    return (
                      <button
                        key={r.id}
                        onClick={() => setSelectedRunId(r.id)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium border text-left whitespace-nowrap transition ${
                          isSelected
                            ? "bg-emerald-50 border-emerald-300 text-emerald-800 shadow-xs"
                            : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50"
                        }`}
                      >
                        <span className="font-semibold block truncate max-w-[140px]">{r.summary || "Agent Session"}</span>
                        <span className="text-[10px] text-slate-400 capitalize">{r.status}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Main Timeline Stream */}
            <AgentRunTimeline run={run} events={events} />
          </div>
        </div>
      </div>
    </div>
  );
};
