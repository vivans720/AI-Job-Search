"use client";

import { useEffect, useState } from "react";
import { Bookmark, ExternalLink, Trash2, MapPin } from "lucide-react";

interface SavedJob {
  saved_id: string;
  job_id: string;
  title: string;
  company: string;
  location: string;
  salary: string;
  status: string;
  notes?: string;
  application_url: string;
  posted_at?: string;
  updated_at: string;
}

const STATUSES = ["ALL", "SAVED", "APPLIED", "INTERVIEW", "OFFER", "REJECTED", "IGNORED"];

const getMonogram = (name: string) => {
  if (!name) return "CO";
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
};

export default function SavedPage() {
  const [items, setItems] = useState<SavedJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("ALL");

  const fetchSaved = async (status?: string) => {
    try {
      const url =
        status && status !== "ALL"
          ? `http://localhost:8000/api/v1/jobs/saved?status=${status}`
          : "http://localhost:8000/api/v1/jobs/saved";
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setItems(data);
      }
    } catch {
      // Backend offline
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSaved(activeTab);
  }, [activeTab]);

  const updateStatus = async (jobId: string, newStatus: string) => {
    try {
      const res = await fetch(`http://localhost:8000/api/v1/jobs/${jobId}/status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus }),
      });
      if (res.ok) {
        fetchSaved(activeTab);
      }
    } catch {
      // Handle error
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "SAVED":
        return "bg-blue-500/10 text-blue-300 border-blue-500/25";
      case "APPLIED":
        return "bg-amber-500/10 text-amber-300 border-amber-500/25";
      case "INTERVIEW":
        return "bg-purple-500/10 text-purple-300 border-purple-500/25";
      case "OFFER":
        return "bg-emerald-500/10 text-emerald-300 border-emerald-500/25";
      case "REJECTED":
        return "bg-rose-500/10 text-rose-300 border-rose-500/25";
      default:
        return "bg-zinc-800 text-zinc-300 border-white/[0.08]";
    }
  };

  return (
    <div className="space-y-6 pb-16">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-white/[0.07]">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              TRACKING REGISTRY
            </span>
            <span className="text-xs text-zinc-500">·</span>
            <span className="text-xs text-zinc-400">{items.length} Opportunities Tracked</span>
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-zinc-100">Saved Opportunities</h2>
          <p className="text-xs text-zinc-400">
            Manage bookmarked roles, stage transitions, and interview progression.
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap gap-1.5 p-1 rounded-xl bg-obsidian-900/70 border border-white/[0.08] shadow-surface-inset">
        {STATUSES.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              activeTab === tab
                ? "bg-white/[0.12] text-zinc-100 border border-white/[0.2] shadow-surface-inset font-semibold"
                : "text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.03]"
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Jobs List */}
      {loading ? (
        <div className="py-20 text-center text-xs text-zinc-500 rounded-2xl bg-obsidian-900/40 border border-white/[0.06]">
          Loading tracked jobs...
        </div>
      ) : items.length > 0 ? (
        <div className="space-y-3">
          {items.map((item) => {
            const monogram = getMonogram(item.company);

            return (
              <div
                key={item.saved_id}
                className="p-5 rounded-2xl bg-obsidian-900/60 border border-white/[0.08] shadow-surface-inset flex flex-col md:flex-row md:items-center justify-between gap-4 hover:border-white/[0.16] hover:bg-obsidian-900/90 transition-all group"
              >
                <div className="flex items-start gap-3.5">
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-zinc-800 to-zinc-900 border border-white/[0.08] flex items-center justify-center font-bold text-xs text-zinc-200 shadow-sm shrink-0 mt-0.5">
                    {monogram}
                  </div>

                  <div className="space-y-1">
                    <div className="flex items-center gap-2.5 flex-wrap">
                      <h3 className="text-sm font-semibold text-zinc-100 group-hover:text-emerald-400 transition-colors">
                        {item.title}
                      </h3>
                      <span className={`px-2 py-0.5 rounded-md text-[10px] font-semibold border ${getStatusBadge(item.status)}`}>
                        {item.status}
                      </span>
                    </div>

                    <div className="flex items-center gap-2 text-xs text-zinc-400 flex-wrap">
                      <span className="font-medium text-zinc-300">{item.company}</span>
                      <span className="text-zinc-600">·</span>
                      <span className="flex items-center gap-1">
                        <MapPin className="w-3 h-3 text-zinc-500" />
                        <span>{item.location}</span>
                      </span>
                      <span className="text-zinc-600">·</span>
                      <span className="text-emerald-400 font-medium">{item.salary || "Not disclosed"}</span>
                    </div>

                    {item.notes && (
                      <p className="text-[11px] text-zinc-400 italic pt-1 bg-white/[0.02] px-2 py-1 rounded-md border border-white/[0.04] inline-block">
                        {item.notes}
                      </p>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0 self-end md:self-center">
                  <select
                    value={item.status}
                    onChange={(e) => updateStatus(item.job_id, e.target.value)}
                    className="bg-obsidian-950 border border-white/[0.08] text-zinc-200 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-emerald-500/40"
                  >
                    <option value="SAVED">Saved</option>
                    <option value="VIEWED">Viewed</option>
                    <option value="APPLIED">Applied</option>
                    <option value="INTERVIEW">Interview</option>
                    <option value="OFFER">Offer</option>
                    <option value="REJECTED">Rejected</option>
                    <option value="IGNORED">Ignored</option>
                  </select>

                  <a
                    href={item.application_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 active:scale-[0.98] text-white rounded-lg text-xs font-medium transition-colors shadow-sm"
                  >
                    <span>Apply</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>

                  <button
                    onClick={() => updateStatus(item.job_id, "IGNORED")}
                    className="p-2 text-zinc-500 hover:text-rose-400 rounded-lg hover:bg-white/[0.04] transition-colors"
                    title="Remove from active"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="rounded-2xl border border-dashed border-white/[0.08] p-16 text-center bg-obsidian-900/30 space-y-2">
          <Bookmark className="w-8 h-8 text-zinc-600 mx-auto mb-1" />
          <p className="text-sm font-medium text-zinc-300">No jobs tracked under status &quot;{activeTab}&quot;</p>
          <p className="text-xs text-zinc-500">
            Bookmark opportunities in Job Discovery to organize them in your pipeline.
          </p>
        </div>
      )}
    </div>
  );
}
