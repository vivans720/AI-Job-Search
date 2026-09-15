"use client";

import React, { useState, useEffect } from "react";
import {
  X,
  MapPin,
  ExternalLink,
  Bookmark,
  BookmarkCheck,
  Check,
  ThumbsDown,
  Ban,
  Building2,
  Sparkles,
  AlertCircle,
} from "lucide-react";
import WhyThisJobCard from "@/components/jobs/WhyThisJobCard";

interface OtherSource {
  source: string;
  url?: string;
  application_url?: string;
}

interface MatchBreakdown {
  overall_score: number;
  skill_score: number;
  semantic_score: number;
  experience_score: number;
  role_score: number;
  location_score: number;
  preference_score: number;
  matched_skills: string[];
  missing_skills: string[];
  transferable_skills: string[];
  required_skills?: { matched: string[]; missing: string[] };
  preferred_skills?: { matched: string[]; missing: string[] };
  experience_eligible?: boolean;
  location_eligible?: boolean;
  confidence?: number;
  confidence_label?: string;
  explanation: string;
  recommendation: string;
}

export interface JobDetailData {
  id: string;
  title: string;
  company: string;
  company_logo_url?: string | null;
  location: string;
  remote_type: string;
  employment_type?: string;
  salary: string;
  salary_min?: number | null;
  salary_max?: number | null;
  experience: string;
  experience_min?: number | null;
  experience_max?: number | null;
  posted_at?: string;
  age_hours?: number;
  source: string;
  source_url?: string;
  application_url: string;
  description: string;
  required_skills: string[];
  preferred_skills?: string[];
  quality_score?: number;
  match?: MatchBreakdown;
  saved_status?: string;
  other_sources?: OtherSource[];
}

interface JobDetailDrawerProps {
  jobId: string | null;
  isOpen: boolean;
  onClose: () => void;
  onSave?: (job: JobDetailData) => void;
  onUnsave?: (job: JobDetailData) => void;
  onReject?: (job: JobDetailData) => void;
  onMarkApplied?: (job: JobDetailData) => void;
  onBanCompany?: (company: string) => void;
}

export default function JobDetailDrawer({
  jobId,
  isOpen,
  onClose,
  onSave,
  onUnsave,
  onReject,
  onMarkApplied,
  onBanCompany,
}: JobDetailDrawerProps) {
  const [job, setJob] = useState<JobDetailData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"overview" | "why" | "description">("overview");

  useEffect(() => {
    if (!isOpen || !jobId) {
      setJob(null);
      return;
    }

    const fetchDetail = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`http://localhost:8000/api/v1/jobs/${jobId}`);
        if (!res.ok) {
          throw new Error(`Failed to load job details (${res.status})`);
        }
        const data = await res.json();
        setJob(data);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Failed to load job information";
        setError(msg);
      } finally {
        setLoading(false);
      }
    };

    fetchDetail();
  }, [isOpen, jobId]);

  if (!isOpen) return null;

  const match = job?.match;
  const isSaved = job?.saved_status === "SAVED";

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-900/40 backdrop-blur-xs animate-fade-in">
      <div
        className="w-full max-w-2xl bg-white border-l border-slate-200 shadow-2xl flex flex-col h-full overflow-hidden"
        role="dialog"
        aria-modal="true"
      >
        {/* Top Header */}
        <div className="p-6 border-b border-slate-200 flex items-start justify-between gap-4 bg-slate-50/80">
          <div className="space-y-2.5 flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              {job?.source && (
                <span
                  className={`px-2.5 py-0.5 rounded text-[11px] font-bold uppercase tracking-wider ${
                    job.source === "linkedin"
                      ? "bg-blue-50 text-blue-800 border border-blue-300"
                      : job.source === "naukri"
                      ? "bg-indigo-50 text-indigo-800 border border-indigo-300"
                      : job.source === "internshala"
                      ? "bg-sky-50 text-sky-800 border border-sky-300"
                      : "bg-emerald-50 text-emerald-800 border border-emerald-300"
                  }`}
                >
                  {job.source}
                </span>
              )}

              {job?.employment_type && (
                <span className="px-2.5 py-0.5 rounded text-[11px] font-semibold bg-purple-50 text-purple-800 border border-purple-300">
                  {job.employment_type}
                </span>
              )}

              {match && (
                <span
                  className={`px-3 py-0.5 rounded-full text-xs font-bold font-tabular border ${
                    match.overall_score >= 80
                      ? "bg-emerald-50 text-emerald-800 border-emerald-300"
                      : match.overall_score >= 60
                      ? "bg-blue-50 text-blue-800 border-blue-300"
                      : match.overall_score >= 40
                      ? "bg-amber-50 text-amber-900 border-amber-300"
                      : "bg-rose-50 text-rose-800 border-rose-300"
                  }`}
                >
                  {Math.round(match.overall_score)}% Match
                </span>
              )}
            </div>

            <h2 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight leading-snug">
              {job?.title || "Job Details"}
            </h2>

            <div className="flex items-center gap-3 text-sm text-slate-600 flex-wrap">
              <span className="flex items-center gap-1.5 font-semibold text-slate-900">
                {job?.company_logo_url ? (
                  <img
                    src={job.company_logo_url}
                    alt={job.company}
                    className="w-4 h-4 object-contain rounded-xs shrink-0"
                    onError={(e) => {
                      (e.currentTarget as HTMLElement).style.display = "none";
                    }}
                  />
                ) : (
                  <Building2 className="w-4 h-4 text-slate-500" />
                )}
                <span>{job?.company}</span>
              </span>
              <span className="text-slate-300">·</span>
              <span className="flex items-center gap-1 text-slate-600 font-medium">
                <MapPin className="w-4 h-4 text-slate-500" />
                <span>{job?.location}</span>
                {job?.remote_type && (
                  <span className="text-slate-500 font-semibold">({job.remote_type})</span>
                )}
              </span>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-2 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors shrink-0"
            title="Close drawer (Esc)"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Action Controls Bar */}
        {job && (
          <div className="px-6 py-3 border-b border-slate-200 bg-white flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  if (isSaved) {
                    if (onUnsave) onUnsave(job);
                  } else {
                    if (onSave) onSave(job);
                  }
                }}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-semibold transition-all ${
                  isSaved
                    ? "bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-rose-50 hover:text-rose-700 hover:border-rose-200"
                    : "bg-white text-slate-700 border-slate-200 hover:text-emerald-700 hover:border-emerald-200 shadow-xs"
                }`}
                title={isSaved ? "Click to unsave" : "Save job"}
              >
                {isSaved ? <BookmarkCheck className="w-4 h-4 text-emerald-600" /> : <Bookmark className="w-4 h-4" />}
                <span>{isSaved ? "Saved" : "Save Job"}</span>
              </button>

              <button
                onClick={() => {
                  if (onMarkApplied) onMarkApplied(job);
                  onClose();
                }}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-amber-200 bg-amber-50 text-amber-800 hover:bg-amber-100 text-xs font-semibold transition-all shadow-xs"
                title="Mark as applied ✓ in tracking"
              >
                <Check className="w-3.5 h-3.5" />
                <span>Applied ✓</span>
              </button>

              <button
                onClick={() => {
                  if (onReject) onReject(job);
                  onClose();
                }}
                aria-label={`Hide ${job.title} from discovery`}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-200 bg-white text-slate-600 hover:text-rose-700 hover:border-rose-200 text-xs font-semibold transition-all shadow-xs"
                title="Hide job from discovery"
              >
                <ThumbsDown className="w-3.5 h-3.5" />
                <span>Not Interested</span>
              </button>

              <button
                onClick={() => {
                  if (onBanCompany && job.company) {
                    onBanCompany(job.company);
                    onClose();
                  }
                }}
                aria-label={`Ban ${job.company} and exclude all listings`}
                className="p-1.5 rounded-xl border border-slate-200 bg-white text-slate-700 hover:text-rose-600 hover:border-rose-200 hover:bg-slate-50 text-xs font-semibold transition-all shadow-xs"
                title={`Ban ${job.company} (Exclude all jobs from this company)`}
              >
                <Ban className="w-4 h-4" />
              </button>
            </div>

            <a
              href={job.application_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-4 py-1.5 bg-slate-900 hover:bg-slate-800 active:scale-[0.98] text-white rounded-xl text-xs font-semibold transition-all shadow-xs"
            >
              <span>Apply Directly</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </div>
        )}

        {/* Tab Navigation */}
        <div className="flex items-center border-b border-slate-200 px-6 bg-slate-50/50">
          <button
            onClick={() => setActiveTab("overview")}
            className={`py-3 px-3 text-xs font-medium border-b-2 transition-all ${
              activeTab === "overview"
                ? "border-emerald-600 text-emerald-800 font-semibold"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            Overview & Skills
          </button>
          <button
            onClick={() => setActiveTab("why")}
            className={`py-3 px-3 text-xs font-medium border-b-2 flex items-center gap-1.5 transition-all ${
              activeTab === "why"
                ? "border-emerald-600 text-emerald-800 font-semibold"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <Sparkles className="w-3.5 h-3.5 text-amber-500" />
            <span>Why This Job?</span>
          </button>
          <button
            onClick={() => setActiveTab("description")}
            className={`py-3 px-3 text-xs font-medium border-b-2 transition-all ${
              activeTab === "description"
                ? "border-emerald-600 text-emerald-800 font-semibold"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            Full Description
          </button>
        </div>

        {/* Drawer Body Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {loading ? (
            <div className="py-20 text-center text-xs text-slate-400 space-y-2">
              <div className="w-6 h-6 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin mx-auto" />
              <p>Loading full job intelligence...</p>
            </div>
          ) : error ? (
            <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          ) : job ? (
            <>
              {/* Tab: Overview */}
              {activeTab === "overview" && (
                <div className="space-y-6">
                  {/* Key Specifications Grid */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 space-y-1">
                      <span className="text-[11px] text-slate-500 uppercase font-bold tracking-wider block">Experience</span>
                      <span className="text-sm font-bold text-slate-900">{job.experience}</span>
                    </div>

                    <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 space-y-1">
                      <span className="text-[11px] text-slate-500 uppercase font-bold tracking-wider block">Compensation</span>
                      <span className="text-sm font-bold text-emerald-800">{job.salary || "Not disclosed"}</span>
                    </div>

                    <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 space-y-1">
                      <span className="text-[11px] text-slate-500 uppercase font-bold tracking-wider block">Workplace</span>
                      <span className="text-sm font-bold text-slate-900">{job.remote_type}</span>
                    </div>

                    <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 space-y-1">
                      <span className="text-[11px] text-slate-500 uppercase font-bold tracking-wider block">Freshness</span>
                      <span className="text-sm font-bold text-slate-900 font-tabular">
                        {job.age_hours !== undefined ? `${job.age_hours}h ago` : "Fresh"}
                      </span>
                    </div>
                  </div>

                  {/* Multi-source attribution */}
                  {job.other_sources && job.other_sources.length > 0 && (
                    <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 space-y-2 text-xs">
                      <span className="text-[11px] font-semibold text-slate-700 uppercase tracking-wider block">
                        Cross-Platform Lineage
                      </span>
                      <p className="text-slate-500 text-[11px]">
                        Discovered concurrently on multiple boards:
                      </p>
                      <div className="flex items-center gap-2 flex-wrap">
                        {job.other_sources.map((os, idx) => (
                          <span
                            key={idx}
                            className="px-2.5 py-1 rounded-lg bg-white border border-slate-200 text-xs font-medium text-slate-700 capitalize shadow-xs"
                          >
                            {os.source}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Required Skills */}
                  <div className="space-y-2.5">
                    <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                      Required Skills ({job.required_skills.length})
                    </h4>
                    <div className="flex flex-wrap gap-1.5">
                      {job.required_skills.map((s) => {
                        const isMatched = match?.matched_skills?.some(
                          (m) => m.toLowerCase() === s.toLowerCase()
                        );
                        return (
                          <span
                            key={s}
                            className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                              isMatched
                                ? "bg-emerald-50 text-emerald-800 border border-emerald-200 font-semibold"
                                : "bg-slate-100 text-slate-700 border border-slate-200"
                            }`}
                          >
                            {s} {isMatched && "✓"}
                          </span>
                        );
                      })}
                    </div>
                  </div>

                  {/* Preferred Skills */}
                  {job.preferred_skills && job.preferred_skills.length > 0 && (
                    <div className="space-y-2.5">
                      <h4 className="text-xs font-bold text-slate-600 uppercase tracking-wider">
                        Preferred Skills ({job.preferred_skills.length})
                      </h4>
                      <div className="flex flex-wrap gap-1.5">
                        {job.preferred_skills.map((s) => (
                          <span
                            key={s}
                            className="px-2.5 py-0.5 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-600 font-medium"
                          >
                            {s}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Match Rationale snippet */}
                  {match && (
                    <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80 space-y-2 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-slate-800">Match Assessment</span>
                        <span className="font-tabular font-bold text-emerald-700 text-sm">{match.overall_score}%</span>
                      </div>
                      <p className="text-slate-600 leading-relaxed">{match.explanation}</p>
                    </div>
                  )}
                </div>
              )}

              {/* Tab: Why This Job? */}
              {activeTab === "why" && (
                <div className="space-y-4">
                  <WhyThisJobCard jobId={job.id} />
                </div>
              )}

              {/* Tab: Description */}
              {activeTab === "description" && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                      Original Job Posting Description
                    </h4>
                    <span className="text-xs text-slate-500 font-medium">Source: {job.source}</span>
                  </div>

                  <div className="p-5 rounded-xl bg-slate-50 border border-slate-200 text-sm text-slate-800 leading-relaxed whitespace-pre-wrap font-sans max-w-none">
                    {job.description || "No full description provided for this listing."}
                  </div>
                </div>
              )}
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
