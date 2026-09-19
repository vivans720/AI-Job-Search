"use client";

import React from "react";
import { CheckCircle2, Circle, AlertCircle, Loader2, Clock, Wrench } from "lucide-react";
import { AgentEvent, AgentRun } from "@/lib/api";

interface AgentRunTimelineProps {
  run: AgentRun | null;
  events: AgentEvent[];
}

export const AgentRunTimeline: React.FC<AgentRunTimelineProps> = ({ run, events }) => {
  if (!run && events.length === 0) {
    return (
      <div className="p-8 text-center text-slate-500 border border-dashed border-slate-200 rounded-xl">
        <Clock className="w-8 h-8 mx-auto mb-2 text-slate-400 stroke-1" />
        <p className="text-sm font-medium">No agent activity yet.</p>
        <p className="text-xs text-slate-400 mt-0.5">Start an autonomous search session to monitor live progress.</p>
      </div>
    );
  }

  const isRunning = run?.status === "running";

  return (
    <div className="bg-white border border-slate-200/80 rounded-xl shadow-xs overflow-hidden">
      {/* Header banner */}
      <div className="px-4 py-3.5 bg-slate-50/70 border-b border-slate-200/80 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-600 font-semibold text-xs">
            AI
          </div>
          <div>
            <h4 className="text-sm font-semibold text-slate-900">Agent Activity Stream</h4>
            <p className="text-xs text-slate-500">{run?.summary || "Autonomous Job Search Agent"}</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {isRunning ? (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200 animate-pulse">
              <Loader2 className="w-3 h-3 animate-spin" />
              Active
            </span>
          ) : run?.status === "completed" ? (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200">
              <CheckCircle2 className="w-3 h-3 text-emerald-600" />
              Completed
            </span>
          ) : run?.status === "failed" ? (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-red-50 text-red-700 border border-red-200">
              <AlertCircle className="w-3 h-3 text-red-600" />
              Failed
            </span>
          ) : null}
        </div>
      </div>

      {/* Events timeline */}
      <div className="p-4 sm:p-5">
        <div className="relative pl-6 space-y-4 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
          {events.map((ev, index) => {
            const isError = ev.event_type === "tool_error";
            const isLast = index === events.length - 1;

            return (
              <div key={ev.id || index} className="relative flex items-start gap-3 group">
                <div
                  className={`absolute -left-6 mt-0.5 w-5 h-5 rounded-full flex items-center justify-center bg-white border ${
                    isError
                      ? "border-red-400 text-red-600"
                      : isLast && isRunning
                      ? "border-emerald-500 text-emerald-600 ring-4 ring-emerald-50"
                      : "border-emerald-500 text-emerald-600"
                  }`}
                >
                  {isError ? (
                    <AlertCircle className="w-3 h-3" />
                  ) : isLast && isRunning ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  ) : (
                    <CheckCircle2 className="w-3.5 h-3.5" />
                  )}
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline justify-between gap-2">
                    <p className="text-sm font-medium text-slate-800 leading-snug">
                      {ev.action_summary}
                    </p>
                    <span className="text-[11px] font-mono text-slate-400 shrink-0">
                      {ev.duration_ms != null ? `${ev.duration_ms}ms` : ""}
                    </span>
                  </div>

                  {ev.tool_name && (
                    <div className="mt-1 flex items-center gap-2">
                      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono font-medium bg-slate-100 text-slate-600 border border-slate-200">
                        <Wrench className="w-2.5 h-2.5" />
                        {ev.tool_name}
                      </span>
                      {ev.payload?.item_count != null && (
                        <span className="text-[11px] text-slate-500">
                          {String(ev.payload.item_count)} items
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}

          {isRunning && (
            <div className="relative flex items-start gap-3">
              <div className="absolute -left-6 mt-0.5 w-5 h-5 rounded-full flex items-center justify-center bg-white border border-slate-300 text-slate-400">
                <Circle className="w-2 h-2 fill-slate-300" />
              </div>
              <p className="text-xs text-slate-400 italic">Agent working...</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
