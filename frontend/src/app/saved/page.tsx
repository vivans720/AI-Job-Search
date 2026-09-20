"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Bookmark,
  BookmarkX,
  Bot,
  CheckSquare,
  ExternalLink,
  MapPin,
  RefreshCw,
  Search,
  Sparkles,
  Square,
  Trash2,
  Undo2,
  X,
} from "lucide-react";
import { PageHeader, Card, Button } from "@/components/ui";
import { getApiUrl } from "@/lib/api";
import { ApplicationHandoffModal } from "@/components/jobs/ApplicationHandoffModal";

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
  match_score?: number | null;
  match_recommendation?: string | null;
  match_explanation?: string | null;
}

interface PendingRemoval {
  item: SavedJob;
  timerId: NodeJS.Timeout;
}

interface TabConfig {
  id: string;
  label: string;
}

type SortOption = "date_desc" | "date_asc" | "title_asc" | "company_asc";

const TABS: TabConfig[] = [
  { id: "ALL", label: "All" },
  { id: "SAVED", label: "Saved" },
  { id: "PREPARING", label: "Preparing" },
  { id: "READY_TO_APPLY", label: "Ready to Apply" },
  { id: "APPLIED", label: "Applied" },
  { id: "INTERVIEW", label: "Interview" },
  { id: "OFFER", label: "Offer" },
  { id: "REJECTED", label: "Rejected" },
  { id: "IGNORED", label: "Ignored" },
];

const getMonogram = (name: string) => {
  if (!name) return "CO";
  const clean = name.replace(/[^a-zA-Z0-9\s]/g, "").trim();
  const parts = clean.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return clean.slice(0, 2).toUpperCase() || "CO";
};

const STAGE_CONFIG: Record<
  string,
  { label: string; pillClass: string; isComplete: boolean }
> = {
  SAVED: {
    label: "Saved",
    pillClass: "bg-sky-50 text-sky-800 border-sky-200 hover:border-sky-300",
    isComplete: false,
  },
  VIEWED: {
    label: "Viewed",
    pillClass: "bg-slate-50 text-slate-700 border-slate-200 hover:border-slate-300",
    isComplete: false,
  },
  PREPARING: {
    label: "Preparing",
    pillClass: "bg-indigo-50 text-indigo-800 border-indigo-200 hover:border-indigo-300",
    isComplete: false,
  },
  READY_TO_APPLY: {
    label: "Ready to Apply",
    pillClass: "bg-purple-50 text-purple-900 border-purple-200 hover:border-purple-300 font-bold",
    isComplete: false,
  },
  APPLIED: {
    label: "Applied",
    pillClass: "bg-amber-50 text-amber-900 border-amber-200 hover:border-amber-300",
    isComplete: true,
  },
  INTERVIEW: {
    label: "Interview",
    pillClass: "bg-purple-50 text-purple-900 border-purple-200 hover:border-purple-300",
    isComplete: true,
  },
  OFFER: {
    label: "Offer",
    pillClass: "bg-emerald-50 text-emerald-900 border-emerald-200 hover:border-emerald-300",
    isComplete: true,
  },
  REJECTED: {
    label: "Rejected",
    pillClass: "bg-rose-50 text-rose-800 border-rose-200 hover:border-rose-300",
    isComplete: true,
  },
  IGNORED: {
    label: "Ignored",
    pillClass: "bg-slate-100 text-slate-600 border-slate-200 hover:border-slate-300",
    isComplete: true,
  },
};

const getMatchBadgeStyle = (rec?: string | null) => {
  switch (rec) {
    case "STRONG_MATCH":
      return "bg-emerald-50 text-emerald-800 border-emerald-300";
    case "GOOD_MATCH":
      return "bg-teal-50 text-teal-800 border-teal-300";
    case "CONSIDER":
      return "bg-amber-50 text-amber-900 border-amber-300";
    case "LOW_PRIORITY":
      return "bg-orange-50 text-orange-900 border-orange-300";
    default:
      return "bg-slate-100 text-slate-700 border-slate-200";
  }
};

export default function SavedPage() {
  const [allItems, setAllItems] = useState<SavedJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState<SortOption>("date_desc");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [batchOperating, setBatchOperating] = useState(false);
  const [updatingIds, setUpdatingIds] = useState<Record<string, boolean>>({});
  const [pendingRemoval, setPendingRemoval] = useState<PendingRemoval | null>(null);
  const [networkError, setNetworkError] = useState<string | null>(null);
  const [selectedHandoffJob, setSelectedHandoffJob] = useState<SavedJob | null>(null);

  const pendingRemovalRef = useRef<PendingRemoval | null>(null);
  pendingRemovalRef.current = pendingRemoval;

  const fetchAllSaved = async () => {
    try {
      setNetworkError(null);
      const res = await fetch(getApiUrl("/api/v1/jobs/saved"));
      if (res.ok) {
        const data = await res.json();
        setAllItems(data);
      } else {
        setNetworkError("Unable to load saved opportunities. Check backend service.");
      }
    } catch {
      setNetworkError("Failed to reach registry service. Retrying when connection resumes.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAllSaved();
  }, []);

  useEffect(() => {
    return () => {
      if (pendingRemovalRef.current) {
        clearTimeout(pendingRemovalRef.current.timerId);
      }
    };
  }, []);

  const tabCounts = useMemo(() => {
    const counts: Record<string, number> = { ALL: allItems.length };
    for (const tab of TABS) {
      if (tab.id !== "ALL") {
        counts[tab.id] = 0;
      }
    }
    for (const item of allItems) {
      if (counts[item.status] !== undefined) {
        counts[item.status] += 1;
      }
    }
    return counts;
  }, [allItems]);

  const filteredAndSortedItems = useMemo(() => {
    let list = allItems;

    if (activeTab !== "ALL") {
      list = list.filter((j) => j.status === activeTab);
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      list = list.filter(
        (j) =>
          j.title.toLowerCase().includes(q) ||
          j.company.toLowerCase().includes(q) ||
          (j.location && j.location.toLowerCase().includes(q))
      );
    }

    return [...list].sort((a, b) => {
      if (sortBy === "title_asc") {
        return a.title.localeCompare(b.title);
      }
      if (sortBy === "company_asc") {
        return a.company.localeCompare(b.company);
      }
      if (sortBy === "date_asc") {
        return new Date(a.updated_at).getTime() - new Date(b.updated_at).getTime();
      }
      return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
    });
  }, [allItems, activeTab, searchQuery, sortBy]);

  const toggleSelect = (jobId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(jobId)) {
        next.delete(jobId);
      } else {
        next.add(jobId);
      }
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === filteredAndSortedItems.length && filteredAndSortedItems.length > 0) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filteredAndSortedItems.map((j) => j.job_id)));
    }
  };

  const updateStatus = async (jobId: string, newStatus: string) => {
    setUpdatingIds((prev) => ({ ...prev, [jobId]: true }));
    setNetworkError(null);

    const previousItems = [...allItems];
    setAllItems((prev) =>
      prev.map((job) => (job.job_id === jobId ? { ...job, status: newStatus } : job))
    );

    try {
      const res = await fetch(getApiUrl(`/api/v1/jobs/${jobId}/status`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus }),
      });
      if (!res.ok) {
        throw new Error("Server rejected status update");
      }
    } catch {
      setAllItems(previousItems);
      setNetworkError("Could not update job stage. Reverted to previous status.");
    } finally {
      setUpdatingIds((prev) => {
        const next = { ...prev };
        delete next[jobId];
        return next;
      });
    }
  };

  const handleBatchStatus = async (targetStatus: string) => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;

    setBatchOperating(true);
    setNetworkError(null);

    const previousItems = [...allItems];
    setAllItems((prev) =>
      prev.map((job) =>
        selectedIds.has(job.job_id) ? { ...job, status: targetStatus } : job
      )
    );

    try {
      const res = await fetch(getApiUrl("/api/v1/jobs/batch-status"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_ids: ids,
          status: targetStatus,
        }),
      });

      if (!res.ok) {
        throw new Error("Batch status update failed");
      }
      setSelectedIds(new Set());
    } catch {
      setAllItems(previousItems);
      setNetworkError("Batch update failed. Reverted changes.");
    } finally {
      setBatchOperating(false);
    }
  };

  const handleBatchUnsave = async () => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;

    setBatchOperating(true);
    setNetworkError(null);

    const idSet = new Set(ids);
    const previousItems = [...allItems];
    setAllItems((prev) => prev.filter((j) => !idSet.has(j.job_id)));
    setSelectedIds(new Set());

    try {
      await Promise.all(
        ids.map((id) =>
          fetch(getApiUrl(`/api/v1/jobs/${id}/saved`), { method: "DELETE" })
        )
      );
    } catch {
      setAllItems(previousItems);
      setNetworkError("Failed to remove some saved jobs.");
    } finally {
      setBatchOperating(false);
    }
  };

  const commitUnsave = async (jobId: string) => {
    try {
      await fetch(getApiUrl(`/api/v1/jobs/${jobId}/saved`), {
        method: "DELETE",
      });
    } catch {
      // Handled
    }
  };

  const unsaveJob = (jobId: string) => {
    const target = allItems.find((j) => j.job_id === jobId);
    if (!target) return;

    if (pendingRemoval) {
      clearTimeout(pendingRemoval.timerId);
      commitUnsave(pendingRemoval.item.job_id);
    }

    setAllItems((prev) => prev.filter((j) => j.job_id !== jobId));
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.delete(jobId);
      return next;
    });

    const timerId = setTimeout(() => {
      commitUnsave(jobId);
      setPendingRemoval(null);
    }, 5000);

    setPendingRemoval({ item: target, timerId });
  };

  const undoUnsave = () => {
    if (!pendingRemoval) return;
    clearTimeout(pendingRemoval.timerId);
    setAllItems((prev) => [pendingRemoval.item, ...prev]);
    setPendingRemoval(null);
  };

  const dismissToast = () => {
    if (!pendingRemoval) return;
    clearTimeout(pendingRemoval.timerId);
    commitUnsave(pendingRemoval.item.job_id);
    setPendingRemoval(null);
  };

  return (
    <div className="space-y-6 pb-16 relative">
      {/* Header */}
      <PageHeader
        badgeLabel="TRACKING REGISTRY"
        badgeMeta={`${allItems.length} Opportunities Tracked`}
        title="Saved Opportunities"
        description="Manage bookmarked roles, stage transitions, and interview progression."
      />

      {/* Network error banner */}
      {networkError && (
        <div
          role="alert"
          className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 flex items-center justify-between text-xs text-rose-800"
        >
          <span>{networkError}</span>
          <button
            type="button"
            onClick={fetchAllSaved}
            className="font-semibold underline hover:text-rose-900 ml-2 cursor-pointer"
          >
            Retry
          </button>
        </div>
      )}

      {/* Pipeline Tabs with counts */}
      <div
        role="tablist"
        aria-label="Filter opportunities by stage"
        className="flex flex-wrap gap-1 p-1 rounded-xl bg-slate-100/80 border border-slate-200/80 shadow-xs"
      >
        {TABS.map((tab) => {
          const isActive = activeTab === tab.id;
          const count = tabCounts[tab.id] ?? 0;
          return (
            <button
              key={tab.id}
              role="tab"
              id={`tab-${tab.id.toLowerCase()}`}
              aria-selected={isActive}
              aria-controls="tracked-jobs-panel"
              type="button"
              onClick={() => {
                setActiveTab(tab.id);
                setSelectedIds(new Set());
              }}
              className={`px-3 py-1.5 min-h-[38px] sm:min-h-0 flex items-center gap-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer ${
                isActive
                  ? "bg-white text-slate-900 shadow-xs font-semibold"
                  : "text-slate-600 hover:text-slate-900 hover:bg-white/60"
              }`}
            >
              <span>{tab.label}</span>
              <span
                className={`px-1.5 py-0.2 text-[10px] font-bold font-tabular rounded-full ${
                  isActive
                    ? "bg-slate-100 text-slate-800"
                    : "bg-slate-200/60 text-slate-600"
                }`}
              >
                {count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Search & Sort Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
          <input
            id="saved-jobs-search"
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            aria-label="Search saved opportunities by title, company, or city"
            placeholder="Search saved by title, company, or city..."
            className="w-full pl-10 pr-9 py-2 text-xs rounded-xl bg-white border border-slate-200 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-900/10 focus:border-slate-300 shadow-xs transition-colors"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery("")}
              aria-label="Clear search query"
              className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-600 rounded-md cursor-pointer"
              title="Clear search"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        <div className="flex items-center gap-2 text-xs self-start sm:self-auto">
          <label htmlFor="sort-select" className="text-slate-500 font-medium whitespace-nowrap">
            Sort by:
          </label>
          <select
            id="sort-select"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as SortOption)}
            className="bg-white border border-slate-200 text-slate-700 font-medium text-xs rounded-lg px-3 py-2 sm:py-1.5 focus:outline-none focus:ring-2 focus:ring-slate-900/10 cursor-pointer shadow-xs transition-colors"
          >
            <option value="date_desc">Recently Updated</option>
            <option value="date_asc">Oldest First</option>
            <option value="title_asc">Role Title (A–Z)</option>
            <option value="company_asc">Company (A–Z)</option>
          </select>
        </div>
      </div>

      {/* Batch Operations Bar */}
      {filteredAndSortedItems.length > 0 && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-3 py-2.5 bg-slate-50 border border-slate-200/80 rounded-xl text-xs overflow-x-auto">
          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={toggleSelectAll}
              className="flex items-center gap-1.5 text-slate-700 hover:text-slate-900 font-medium cursor-pointer"
            >
              {selectedIds.size === filteredAndSortedItems.length && filteredAndSortedItems.length > 0 ? (
                <CheckSquare className="w-4 h-4 text-emerald-600" />
              ) : (
                <Square className="w-4 h-4 text-slate-400" />
              )}
              <span>
                {selectedIds.size > 0
                  ? `${selectedIds.size} of ${filteredAndSortedItems.length} selected`
                  : `Select all (${filteredAndSortedItems.length})`}
              </span>
            </button>
            {selectedIds.size > 0 && (
              <button
                type="button"
                onClick={() => setSelectedIds(new Set())}
                className="text-slate-500 hover:text-slate-800 underline ml-1 cursor-pointer"
              >
                Clear
              </button>
            )}
          </div>

          {selectedIds.size > 0 && (
            <div className="flex items-center gap-1.5 shrink-0 overflow-x-auto pb-0.5 sm:pb-0">
              <span className="text-slate-500 hidden md:inline">Batch actions:</span>
              <Button
                variant="secondary"
                size="sm"
                disabled={batchOperating}
                onClick={() => handleBatchStatus("APPLIED")}
              >
                Mark Applied
              </Button>
              <Button
                variant="secondary"
                size="sm"
                disabled={batchOperating}
                onClick={() => handleBatchStatus("INTERVIEW")}
              >
                Mark Interview
              </Button>
              <Button
                variant="secondary"
                size="sm"
                disabled={batchOperating}
                onClick={() => handleBatchStatus("REJECTED")}
              >
                Mark Rejected
              </Button>
              <Button
                variant="destructive"
                size="sm"
                disabled={batchOperating}
                leftIcon={<Trash2 className="w-3.5 h-3.5" />}
                onClick={handleBatchUnsave}
              >
                Unsave ({selectedIds.size})
              </Button>
            </div>
          )}
        </div>
      )}

      {/* Jobs List */}
      {loading ? (
        <Card className="py-20 text-center text-xs text-slate-400">
          <div className="flex flex-col items-center justify-center gap-2">
            <RefreshCw className="w-4 h-4 animate-spin text-slate-400" />
            <span>Loading tracked jobs...</span>
          </div>
        </Card>
      ) : filteredAndSortedItems.length > 0 ? (
        <div
          id="tracked-jobs-panel"
          role="tabpanel"
          aria-labelledby={`tab-${activeTab.toLowerCase()}`}
          className="space-y-3"
        >
          {filteredAndSortedItems.map((item) => {
            const monogram = getMonogram(item.company);
            const isUpdating = updatingIds[item.job_id] || false;
            const isSelected = selectedIds.has(item.job_id);
            const currentStage = STAGE_CONFIG[item.status] || {
              label: item.status,
              pillClass: "bg-slate-100 text-slate-700 border-slate-200 hover:border-slate-300",
              isComplete: false,
            };

            return (
              <Card
                key={item.saved_id}
                variant="interactive"
                padding="md"
                className={`flex flex-col lg:flex-row lg:items-center justify-between gap-4 group transition-colors ${
                  isSelected ? "border-emerald-300 bg-emerald-50/20" : ""
                }`}
              >
                <div className="flex items-start gap-3 min-w-0 flex-1">
                  <button
                    type="button"
                    onClick={() => toggleSelect(item.job_id)}
                    aria-label={`Select ${item.title}`}
                    className="mt-2 text-slate-400 hover:text-slate-700 cursor-pointer shrink-0"
                  >
                    {isSelected ? (
                      <CheckSquare className="w-4 h-4 text-emerald-600" />
                    ) : (
                      <Square className="w-4 h-4" />
                    )}
                  </button>

                  <div className="w-10 h-10 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-center font-bold text-xs text-slate-700 shadow-xs shrink-0 tracking-wider group-hover:border-slate-300 transition-colors">
                    {monogram}
                  </div>

                  <div className="space-y-1.5 min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="text-base sm:text-lg font-bold text-slate-900 group-hover:text-emerald-700 transition-colors tracking-tight">
                        {item.title}
                      </h3>
                      {item.match_score !== null && item.match_score !== undefined && (
                        <span
                          className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[11px] font-bold border tracking-tight ${getMatchBadgeStyle(
                            item.match_recommendation
                          )}`}
                        >
                          <Sparkles className="w-3 h-3 text-emerald-600" />
                          <span className="font-tabular">{Math.round(item.match_score)}% Match</span>
                          {item.match_recommendation && (
                            <span className="text-[10px] font-semibold opacity-80">
                              · {item.match_recommendation.replace("_", " ")}
                            </span>
                          )}
                        </span>
                      )}
                      {isUpdating && (
                        <span className="flex items-center gap-1 text-xs text-slate-500 font-medium">
                          <RefreshCw className="w-3.5 h-3.5 animate-spin text-emerald-600" />
                          <span>Updating...</span>
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-2 text-xs sm:text-[13px] text-slate-600 flex-wrap font-normal">
                      <span className="font-semibold text-slate-900">{item.company}</span>
                      <span className="text-slate-300">·</span>
                      <span className="flex items-center gap-1 text-slate-600">
                        <MapPin className="w-3.5 h-3.5 text-slate-400" />
                        <span>{item.location}</span>
                      </span>
                      <span className="text-slate-300">·</span>
                      {item.salary ? (
                        <span className="text-emerald-800 font-bold font-tabular">{item.salary}</span>
                      ) : (
                        <span className="text-slate-400 font-medium">Salary unlisted</span>
                      )}
                    </div>

                    {/* AI Fit Rationale if available */}
                    {item.match_explanation && (
                      <div className="flex items-center gap-1.5 text-xs text-emerald-900 bg-emerald-50/70 border border-emerald-200/80 rounded-lg px-2.5 py-1 max-w-full sm:max-w-2xl">
                        <Bot className="w-3.5 h-3.5 text-emerald-700 shrink-0" />
                        <span className="truncate">{item.match_explanation}</span>
                      </div>
                    )}

                    {item.notes && (
                      <p className="text-xs text-slate-600 italic pt-0.5 px-3 py-1.5 rounded-lg bg-slate-50 border border-slate-200 inline-block max-w-full sm:max-w-xl truncate break-words">
                        {item.notes}
                      </p>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0 self-start lg:self-center flex-wrap pt-1 lg:pt-0">
                  <label htmlFor={`stage-select-${item.job_id}`} className="sr-only">
                    Application stage
                  </label>
                  <div className="relative inline-flex items-center">
                    <select
                      id={`stage-select-${item.job_id}`}
                      value={item.status}
                      disabled={isUpdating}
                      onChange={(e) => updateStatus(item.job_id, e.target.value)}
                      aria-label={`Change stage for ${item.title} at ${item.company}`}
                      className={`appearance-none border font-semibold text-xs rounded-lg pl-3 pr-7 py-2 sm:py-1.5 min-h-[40px] sm:min-h-0 focus:outline-none focus:ring-2 focus:ring-slate-900/10 cursor-pointer shadow-xs transition-colors ${currentStage.pillClass}`}
                    >
                      <option value="SAVED">Saved</option>
                      <option value="VIEWED">Viewed</option>
                      <option value="PREPARING">Preparing</option>
                      <option value="READY_TO_APPLY">Ready to Apply</option>
                      <option value="APPLIED">Applied</option>
                      <option value="INTERVIEW">Interview</option>
                      <option value="OFFER">Offer</option>
                      <option value="REJECTED">Rejected</option>
                      <option value="IGNORED">Ignored</option>
                    </select>
                    <span className="pointer-events-none absolute right-2.5 flex items-center text-current opacity-60">
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                      </svg>
                    </span>
                  </div>

                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setSelectedHandoffJob(item)}
                    leftIcon={<Sparkles className="w-3.5 h-3.5 text-purple-600" />}
                    className="min-h-[40px] sm:min-h-0 px-3 sm:px-2.5 bg-purple-50 hover:bg-purple-100 border-purple-200 text-purple-900"
                    title="Prepare application materials & handoff"
                  >
                    Kit
                  </Button>

                  <a
                    href={item.application_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex"
                  >
                    <Button
                      variant={currentStage.isComplete ? "secondary" : "primary"}
                      size="sm"
                      rightIcon={<ExternalLink className="w-3.5 h-3.5" />}
                      className="min-h-[40px] sm:min-h-0 px-3 sm:px-2.5"
                    >
                      {currentStage.isComplete ? "View Posting" : "Apply"}
                    </Button>
                  </a>

                  <button
                    type="button"
                    onClick={() => unsaveJob(item.job_id)}
                    aria-label={`Remove ${item.title} from saved jobs`}
                    className="p-3 sm:p-2 min-w-[40px] min-h-[40px] sm:min-w-0 sm:min-h-0 flex items-center justify-center text-slate-400 hover:text-rose-600 rounded-lg hover:bg-slate-100 border border-transparent transition-colors cursor-pointer"
                    title="Remove from saved jobs"
                  >
                    <BookmarkX className="w-4 h-4" />
                  </button>
                </div>
              </Card>
            );
          })}
        </div>
      ) : (
        <div
          id="tracked-jobs-panel"
          role="tabpanel"
          aria-labelledby={`tab-${activeTab.toLowerCase()}`}
          className="rounded-2xl border border-dashed border-slate-300 p-16 text-center bg-white space-y-2 shadow-card-subtle"
        >
          <Bookmark className="w-8 h-8 text-slate-400 mx-auto mb-1" />
          <p className="text-sm font-semibold text-slate-800">
            {searchQuery
              ? `No saved jobs match "${searchQuery}"`
              : `No jobs tracked under status "${TABS.find((t) => t.id === activeTab)?.label || activeTab}"`}
          </p>
          <p className="text-xs text-slate-500">
            {searchQuery
              ? "Try adjusting search query or clearing filters."
              : "Bookmark opportunities in Job Discovery to organize them in your pipeline."}
          </p>
          {searchQuery && (
            <div className="pt-2">
              <Button variant="secondary" size="sm" onClick={() => setSearchQuery("")}>
                Clear Search
              </Button>
            </div>
          )}
        </div>
      )}

      {/* Interactive Undo Toast */}
      {pendingRemoval && (
        <div
          role="status"
          aria-live="polite"
          className="fixed bottom-6 right-6 z-50 flex items-center gap-3 px-4 py-3 bg-slate-900 text-white rounded-xl shadow-xl border border-slate-800 animate-in fade-in slide-in-from-bottom-2 duration-200"
        >
          <span className="text-xs text-slate-200">
            Removed <span className="font-semibold text-white">&quot;{pendingRemoval.item.title}&quot;</span>
          </span>

          <button
            type="button"
            onClick={undoUnsave}
            className="flex items-center gap-1.5 px-3 py-2 sm:py-1 min-h-[44px] sm:min-h-0 text-xs font-semibold text-emerald-400 hover:text-emerald-300 hover:bg-slate-800 rounded-lg transition-colors cursor-pointer"
          >
            <Undo2 className="w-3.5 h-3.5" />
            Undo
          </button>

          <button
            type="button"
            onClick={dismissToast}
            aria-label="Dismiss notification"
            className="p-2 sm:p-1 min-w-[44px] min-h-[44px] sm:min-w-0 sm:min-h-0 flex items-center justify-center text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors cursor-pointer"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {selectedHandoffJob && (
        <ApplicationHandoffModal
          isOpen={!!selectedHandoffJob}
          onClose={() => setSelectedHandoffJob(null)}
          jobId={selectedHandoffJob.job_id}
          jobTitle={selectedHandoffJob.title}
          companyName={selectedHandoffJob.company}
          applicationUrl={selectedHandoffJob.application_url}
          onMarkApplied={() => {
            fetchAllSaved();
            setSelectedHandoffJob(null);
          }}
        />
      )}
    </div>
  );
}
