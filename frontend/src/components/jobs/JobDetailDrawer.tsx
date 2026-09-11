"use client";

import React, { useState, useEffect } from "react";
import {
  X,
  MapPin,
  ExternalLink,
  Bookmark,
  BookmarkCheck,
  ThumbsDown,
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
  onReject?: (job: JobDetailData) => void;
}

export default function JobDetailDrawer({
  jobId,
  isOpen,
  onClose,
  onSave,
  onReject,
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
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm animate-fade-in">
      <div
        className="w-full max-w-2xl bg-obsidian-950 border-l border-white/[0.08] shadow-2xl flex flex-col h-full overflow-hidden"
        role="dialog"
        aria-modal="true"
      >
        {/* Top Header */}
        <div className="p-6 border-b border-white/[0.08] flex items-start justify-between gap-4 bg-obsidian-900/60">
          <div className="space-y-2 flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              {job?.source && (
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                    job.source === "linkedin"
                      ? "bg-blue-500/10 text-blue-400 border border-blue-500/25"
                      : job.source === "naukri"
                      ? "bg-indigo-500/10 text-indigo-400 border border-indigo-500/25"
                      : job.source === "internshala"
                      ? "bg-sky-500/10 text-sky-400 border border-sky-500/25"
                      : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/25"
                  }`}
                >
                  {job.source}
                </span>
              )}

              {job?.employment_type && (
                <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-purple-500/10 text-purple-400 border border-purple-500/20">
                  {job.employment_type}
                </span>
              )}

              {match && (
                <span
                  className={`px-2.5 py-0.5 rounded-full text-xs font-semibold font-tabular border ${
                    match.overall_score >= 80
                      ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
                      : match.overall_score >= 60
                      ? "bg-blue-500/15 text-blue-300 border-blue-500/30"
                      : match.overall_score >= 40
                      ? "bg-amber-500/15 text-amber-300 border-amber-500/30"
                      : "bg-rose-500/15 text-rose-300 border-rose-500/30"
                  }`}
                >
                  {Math.round(match.overall_score)}% Match
                </span>
              )}
            </div>

            <h2 className="text-xl font-bold text-zinc-100 truncate">
              {job?.title || "Job Details"}
            </h2>

            <div className="flex items-center gap-3 text-xs text-zinc-400 flex-wrap">
              <span className="flex items-center gap-1 font-medium text-zinc-300">
                <Building2 className="w-3.5 h-3.5 text-zinc-500" />
                <span>{job?.company}</span>
              </span>
              <span className="text-zinc-600">·</span>
              <span className="flex items-center gap-1">
                <MapPin className="w-3.5 h-3.5 text-zinc-500" />
                <span>{job?.location}</span>
                {job?.remote_type && (
                  <span className="text-zinc-500">({job.remote_type})</span>
                )}
              </span>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-2 rounded-xl text-zinc-400 hover:text-white hover:bg-white/[0.08] transition-colors shrink-0"
            title="Close drawer (Esc)"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Action Controls Bar */}
        {job && (
          <div className="px-6 py-3 border-b border-white/[0.06] bg-obsidian-900/30 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <button
                onClick={() => onSave && onSave(job)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-semibold transition-all ${
                  isSaved
                    ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"
                    : "bg-obsidian-900 text-zinc-300 border-white/[0.08] hover:text-emerald-300 hover:border-emerald-500/30"
                }`}
              >
                {isSaved ? <BookmarkCheck className="w-4 h-4 text-emerald-400" /> : <Bookmark className="w-4 h-4" />}
                <span>{isSaved ? "Saved" : "Save Job"}</span>
              </button>

              <button
                onClick={() => {
                  if (onReject) onReject(job);
                  onClose();
                }}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-white/[0.08] bg-obsidian-900 text-zinc-400 hover:text-rose-400 hover:border-rose-500/30 text-xs font-semibold transition-all"
                title="Hide job from discovery"
              >
                <ThumbsDown className="w-3.5 h-3.5" />
                <span>Not Interested</span>
              </button>
            </div>

            <a
              href={job.application_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 active:scale-[0.98] text-white rounded-xl text-xs font-semibold transition-all shadow-sm"
            >
              <span>Apply Directly</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </div>
        )}

        {/* Tab Navigation */}
        <div className="flex items-center border-b border-white/[0.08] px-6 bg-obsidian-900/20">
          <button
            onClick={() => setActiveTab("overview")}
            className={`py-3 px-3 text-xs font-medium border-b-2 transition-all ${
              activeTab === "overview"
                ? "border-emerald-500 text-emerald-300 font-semibold"
                : "border-transparent text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Overview & Skills
          </button>
          <button
            onClick={() => setActiveTab("why")}
            className={`py-3 px-3 text-xs font-medium border-b-2 flex items-center gap-1.5 transition-all ${
              activeTab === "why"
                ? "border-emerald-500 text-emerald-300 font-semibold"
                : "border-transparent text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <Sparkles className="w-3.5 h-3.5 text-amber-400" />
            <span>Why This Job?</span>
          </button>
          <button
            onClick={() => setActiveTab("description")}
            className={`py-3 px-3 text-xs font-medium border-b-2 transition-all ${
              activeTab === "description"
                ? "border-emerald-500 text-emerald-300 font-semibold"
                : "border-transparent text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Full Description
          </button>
        </div>

        {/* Drawer Body Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {loading ? (
            <div className="py-20 text-center text-xs text-zinc-500 space-y-2">
              <div className="w-6 h-6 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin mx-auto" />
              <p>Loading full job intelligence...</p>
            </div>
          ) : error ? (
            <div className="p-4 rounded-xl bg-rose-950/30 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
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
                    <div className="p-3 rounded-xl bg-obsidian-900/60 border border-white/[0.06] space-y-1">
                      <span className="text-[10px] text-zinc-500 uppercase font-semibold block">Experience</span>
                      <span className="text-xs font-medium text-zinc-200">{job.experience}</span>
                    </div>

                    <div className="p-3 rounded-xl bg-obsidian-900/60 border border-white/[0.06] space-y-1">
                      <span className="text-[10px] text-zinc-500 uppercase font-semibold block">Compensation</span>
                      <span className="text-xs font-medium text-emerald-400">{job.salary || "Not disclosed"}</span>
                    </div>

                    <div className="p-3 rounded-xl bg-obsidian-900/60 border border-white/[0.06] space-y-1">
                      <span className="text-[10px] text-zinc-500 uppercase font-semibold block">Workplace</span>
                      <span className="text-xs font-medium text-zinc-200">{job.remote_type}</span>
                    </div>

                    <div className="p-3 rounded-xl bg-obsidian-900/60 border border-white/[0.06] space-y-1">
                      <span className="text-[10px] text-zinc-500 uppercase font-semibold block">Freshness</span>
                      <span className="text-xs font-medium text-zinc-200">
                        {job.age_hours !== undefined ? `${job.age_hours}h ago` : "Fresh"}
                      </span>
                    </div>
                  </div>

                  {/* Multi-source attribution */}
                  {job.other_sources && job.other_sources.length > 0 && (
                    <div className="p-3.5 rounded-xl bg-obsidian-900/40 border border-white/[0.06] space-y-2 text-xs">
                      <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider block">
                        Cross-Platform Deduplication Lineage
                      </span>
                      <p className="text-zinc-500 text-[11px]">
                        Discovered concurrently on multiple boards:
                      </p>
                      <div className="flex items-center gap-2 flex-wrap">
                        {job.other_sources.map((os, idx) => (
                          <span
                            key={idx}
                            className="px-2.5 py-1 rounded-lg bg-obsidian-950 border border-white/[0.08] text-xs font-medium text-zinc-300 capitalize"
                          >
                            {os.source}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Required Skills */}
                  <div className="space-y-2.5">
                    <h4 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
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
                                ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 font-semibold"
                                : "bg-obsidian-900 text-zinc-300 border border-white/[0.08]"
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
                      <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                        Preferred / Nice-to-Have Skills ({job.preferred_skills.length})
                      </h4>
                      <div className="flex flex-wrap gap-1.5">
                        {job.preferred_skills.map((s) => (
                          <span
                            key={s}
                            className="px-2.5 py-0.5 rounded-lg bg-obsidian-900/70 border border-white/[0.06] text-xs text-zinc-400 font-medium"
                          >
                            {s}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Match Rationale snippet */}
                  {match && (
                    <div className="p-4 rounded-xl bg-obsidian-900/60 border border-white/[0.08] space-y-2 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-zinc-200">6-Dimension Match Assessment</span>
                        <span className="font-tabular font-bold text-emerald-400">{match.overall_score}%</span>
                      </div>
                      <p className="text-zinc-400 leading-relaxed">{match.explanation}</p>
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
                    <h4 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
                      Original Job Posting Description
                    </h4>
                    <span className="text-[11px] text-zinc-500">Source: {job.source}</span>
                  </div>

                  <div className="p-4 rounded-xl bg-obsidian-900/50 border border-white/[0.06] text-xs text-zinc-300 leading-relaxed whitespace-pre-wrap font-sans">
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
