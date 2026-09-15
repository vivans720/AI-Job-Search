"use client";

import { useEffect, useRef, useState } from "react";
import { Bookmark, BookmarkX, ExternalLink, MapPin, RefreshCw, Undo2, X } from "lucide-react";
import { PageHeader, Card, Button, Badge, BadgeVariant } from "@/components/ui";
import { getApiUrl } from "@/lib/api";

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

interface PendingRemoval {
  item: SavedJob;
  timerId: NodeJS.Timeout;
}

interface TabConfig {
  id: string;
  label: string;
}

const TABS: TabConfig[] = [
  { id: "ALL", label: "All" },
  { id: "SAVED", label: "Saved" },
  { id: "APPLIED", label: "Applied" },
  { id: "INTERVIEW", label: "Interview" },
  { id: "OFFER", label: "Offer" },
  { id: "REJECTED", label: "Rejected" },
  { id: "IGNORED", label: "Ignored" },
];

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
  const [updatingIds, setUpdatingIds] = useState<Record<string, boolean>>({});
  const [pendingRemoval, setPendingRemoval] = useState<PendingRemoval | null>(null);
  const [networkError, setNetworkError] = useState<string | null>(null);

  const pendingRemovalRef = useRef<PendingRemoval | null>(null);
  pendingRemovalRef.current = pendingRemoval;

  const fetchSaved = async (status?: string) => {
    try {
      setNetworkError(null);
      const url =
        status && status !== "ALL"
          ? getApiUrl(`/api/v1/jobs/saved?status=${status}`)
          : getApiUrl("/api/v1/jobs/saved");
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setItems(data);
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
    fetchSaved(activeTab);
  }, [activeTab]);

  useEffect(() => {
    return () => {
      if (pendingRemovalRef.current) {
        clearTimeout(pendingRemovalRef.current.timerId);
      }
    };
  }, []);

  const updateStatus = async (jobId: string, newStatus: string) => {
    setUpdatingIds((prev) => ({ ...prev, [jobId]: true }));
    setNetworkError(null);

    const previousItems = [...items];
    setItems((prev) =>
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
      fetchSaved(activeTab);
    } catch {
      setItems(previousItems);
      setNetworkError("Could not update job stage. Reverted to previous status.");
    } finally {
      setUpdatingIds((prev) => {
        const next = { ...prev };
        delete next[jobId];
        return next;
      });
    }
  };

  const commitUnsave = async (jobId: string) => {
    try {
      await fetch(getApiUrl(`/api/v1/jobs/${jobId}/saved`), {
        method: "DELETE",
      });
    } catch {
      // Background failure handled
    }
  };

  const unsaveJob = (jobId: string) => {
    const target = items.find((j) => j.job_id === jobId);
    if (!target) return;

    if (pendingRemoval) {
      clearTimeout(pendingRemoval.timerId);
      commitUnsave(pendingRemoval.item.job_id);
    }

    setItems((prev) => prev.filter((j) => j.job_id !== jobId));

    const timerId = setTimeout(() => {
      commitUnsave(jobId);
      setPendingRemoval(null);
    }, 5000);

    setPendingRemoval({ item: target, timerId });
  };

  const undoUnsave = () => {
    if (!pendingRemoval) return;
    clearTimeout(pendingRemoval.timerId);
    setItems((prev) => [pendingRemoval.item, ...prev]);
    setPendingRemoval(null);
  };

  const dismissToast = () => {
    if (!pendingRemoval) return;
    clearTimeout(pendingRemoval.timerId);
    commitUnsave(pendingRemoval.item.job_id);
    setPendingRemoval(null);
  };

  const getStatusVariant = (status: string): BadgeVariant => {
    switch (status) {
      case "SAVED":
        return "sky";
      case "APPLIED":
        return "amber";
      case "INTERVIEW":
        return "purple";
      case "OFFER":
        return "emerald";
      case "REJECTED":
        return "rose";
      default:
        return "zinc";
    }
  };

  return (
    <div className="space-y-6 pb-16 relative">
      {/* Header */}
      <PageHeader
        badgeLabel="TRACKING REGISTRY"
        badgeMeta={`${items.length} Opportunities Tracked`}
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
            onClick={() => fetchSaved(activeTab)}
            className="font-semibold underline hover:text-rose-900 ml-2 cursor-pointer"
          >
            Retry
          </button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex flex-wrap gap-1 p-1 rounded-xl bg-slate-100/80 border border-slate-200/80 shadow-xs">
        {TABS.map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`px-3 py-2 sm:py-1.5 min-h-[44px] sm:min-h-0 flex items-center justify-center rounded-lg text-xs font-medium transition-all cursor-pointer ${
                isActive
                  ? "bg-white text-slate-900 shadow-xs font-semibold"
                  : "text-slate-600 hover:text-slate-900 hover:bg-white/60"
              }`}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Jobs List */}
      {loading ? (
        <Card className="py-20 text-center text-xs text-slate-400">
          <div className="flex flex-col items-center justify-center gap-2">
            <RefreshCw className="w-4 h-4 animate-spin text-slate-400" />
            <span>Loading tracked jobs...</span>
          </div>
        </Card>
      ) : items.length > 0 ? (
        <div className="space-y-3">
          {items.map((item) => {
            const monogram = getMonogram(item.company);
            const isUpdating = updatingIds[item.job_id] || false;

            return (
              <Card
                key={item.saved_id}
                variant="interactive"
                padding="md"
                className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 group"
              >
                <div className="flex items-start gap-3.5 min-w-0 flex-1">
                  <div className="w-11 h-11 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-center font-bold text-xs text-slate-700 shadow-xs shrink-0 tracking-wider group-hover:border-slate-300 transition-colors">
                    {monogram}
                  </div>

                  <div className="space-y-1.5 min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="text-base sm:text-lg font-bold text-slate-900 group-hover:text-emerald-700 transition-colors tracking-tight">
                        {item.title}
                      </h3>
                      <Badge variant={getStatusVariant(item.status)} size="sm">
                        {item.status}
                      </Badge>
                      {isUpdating && (
                        <span className="flex items-center gap-1 text-xs text-slate-500 font-medium">
                          <RefreshCw className="w-3.5 h-3.5 animate-spin text-emerald-600" />
                          <span>Updating...</span>
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-2.5 text-xs sm:text-[13px] text-slate-600 flex-wrap font-normal">
                      <span className="font-bold text-slate-900">{item.company}</span>
                      <span className="text-slate-300">·</span>
                      <span className="flex items-center gap-1 text-slate-700">
                        <MapPin className="w-3.5 h-3.5 text-slate-500" />
                        <span>{item.location}</span>
                      </span>
                      <span className="text-slate-300">·</span>
                      <span className="text-emerald-800 font-bold font-tabular">{item.salary || "Not disclosed"}</span>
                    </div>

                    {item.notes && (
                      <p className="text-xs text-slate-700 italic pt-0.5 px-3 py-1.5 rounded-lg bg-slate-50 border border-slate-200 inline-block max-w-full sm:max-w-xl truncate break-words">
                        {item.notes}
                      </p>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2.5 shrink-0 self-start lg:self-center flex-wrap pt-1 lg:pt-0">
                  <label htmlFor={`stage-select-${item.job_id}`} className="sr-only">
                    Application stage
                  </label>
                  <div className="relative">
                    <select
                      id={`stage-select-${item.job_id}`}
                      value={item.status}
                      disabled={isUpdating}
                      onChange={(e) => updateStatus(item.job_id, e.target.value)}
                      aria-label={`Change stage for ${item.title} at ${item.company}`}
                      className="bg-white border border-slate-200 hover:border-slate-300 disabled:opacity-50 text-slate-700 font-medium text-xs rounded-lg px-3 py-2.5 sm:py-1.5 min-h-[44px] sm:min-h-0 focus:outline-none focus:ring-2 focus:ring-slate-900/10 cursor-pointer shadow-xs transition-colors"
                    >
                      <option value="SAVED">Stage: Saved</option>
                      <option value="VIEWED">Stage: Viewed</option>
                      <option value="APPLIED">Stage: Applied</option>
                      <option value="INTERVIEW">Stage: Interview</option>
                      <option value="OFFER">Stage: Offer</option>
                      <option value="REJECTED">Stage: Rejected</option>
                      <option value="IGNORED">Stage: Ignored</option>
                    </select>
                  </div>

                  <a
                    href={item.application_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex"
                  >
                    <Button
                      variant="primary"
                      size="sm"
                      rightIcon={<ExternalLink className="w-3.5 h-3.5" />}
                      className="min-h-[44px] sm:min-h-0 px-3.5 sm:px-2.5"
                    >
                      Apply
                    </Button>
                  </a>

                  <button
                    type="button"
                    onClick={() => unsaveJob(item.job_id)}
                    aria-label={`Remove ${item.title} from saved jobs`}
                    className="p-3 sm:p-2 min-w-[44px] min-h-[44px] sm:min-w-0 sm:min-h-0 flex items-center justify-center text-slate-400 hover:text-rose-600 rounded-lg hover:bg-slate-100 border border-transparent transition-colors cursor-pointer"
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
        <div className="rounded-2xl border border-dashed border-slate-300 p-16 text-center bg-white space-y-2 shadow-card-subtle">
          <Bookmark className="w-8 h-8 text-slate-400 mx-auto mb-1" />
          <p className="text-sm font-semibold text-slate-800">
            No jobs tracked under status &quot;{TABS.find((t) => t.id === activeTab)?.label || activeTab}&quot;
          </p>
          <p className="text-xs text-slate-500">
            Bookmark opportunities in Job Discovery to organize them in your pipeline.
          </p>
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
    </div>
  );
}
