"use client";

import React, { useState, useEffect } from "react";

export interface TransferableMatchItem {
  job_skill: string;
  candidate_skill: string;
  rationale: string;
  credit: number;
}

export interface ExperienceStatus {
  eligible: boolean;
  candidate_years: number;
  required_min?: number;
  required_max?: number;
  summary: string;
}

export interface LocationStatus {
  eligible: boolean;
  job_location: string;
  remote_type?: string;
  candidate_locations: string[];
  remote_allowed: boolean;
  summary: string;
}

export interface WhyThisJobData {
  job_id: string;
  job_title: string;
  company_name: string;
  overall_score: number;
  verdict: "APPLY" | "CONSIDER" | "SKIP";
  recommendation: string;
  headline: string;
  strong_matches: string[];
  transferable_matches: TransferableMatchItem[];
  missing_critical: string[];
  missing_nice_to_have: string[];
  experience_status: ExperienceStatus;
  location_status: LocationStatus;
  recommendation_text: string;
  rejection_reasons: string[];
  interview_talking_points: string[];
  confidence: number;
  confidence_label: string;
  is_llm_generated: boolean;
}

interface WhyThisJobCardProps {
  jobId: string;
  initialData?: WhyThisJobData | null;
  onClose?: () => void;
}

export default function WhyThisJobCard({ jobId, initialData, onClose }: WhyThisJobCardProps) {
  const [data, setData] = useState<WhyThisJobData | null>(initialData || null);
  const [loading, setLoading] = useState<boolean>(!initialData);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initialData) return;

    let isMounted = true;
    async function fetchWhyData() {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`http://localhost:8000/api/v1/jobs/${jobId}/why?use_llm=true`);
        if (!res.ok) {
          throw new Error(`Failed to load explanation (${res.status})`);
        }
        const json = await res.json();
        if (isMounted) {
          setData(json);
        }
      } catch (err: unknown) {
        if (isMounted) {
          const msg = err instanceof Error ? err.message : "Failed to load explanation";
          setError(msg);
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    fetchWhyData();
    return () => {
      isMounted = false;
    };
  }, [jobId, initialData]);

  if (loading) {
    return (
      <div className="p-6 bg-slate-900 border border-slate-800 rounded-xl text-slate-200 animate-pulse">
        <div className="h-6 w-48 bg-slate-800 rounded mb-4"></div>
        <div className="h-4 w-full bg-slate-800 rounded mb-2"></div>
        <div className="h-4 w-3/4 bg-slate-800 rounded"></div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-5 bg-rose-950/40 border border-rose-800/60 rounded-xl text-rose-300 text-sm">
        {error || "Could not generate explanation"}
      </div>
    );
  }

  const isApply = data.verdict === "APPLY";
  const isConsider = data.verdict === "CONSIDER";

  const badgeBg = isApply
    ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/40"
    : isConsider
    ? "bg-amber-500/20 text-amber-400 border-amber-500/40"
    : "bg-rose-500/20 text-rose-400 border-rose-500/40";

  return (
    <div className="p-6 bg-slate-900 border border-slate-800 rounded-xl text-slate-100 shadow-xl space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <span className="text-2xl font-bold tracking-tight text-white">
              {Math.round(data.overall_score)}% Match
            </span>
            <span className={`px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wider border rounded-full ${badgeBg}`}>
              {data.verdict}
            </span>
            {data.is_llm_generated && (
              <span className="px-2 py-0.5 text-[10px] bg-cyan-950 text-cyan-400 border border-cyan-800 rounded">
                AI Synthesized
              </span>
            )}
          </div>
          <h3 className="text-sm font-medium text-slate-300 mt-1">{data.headline}</h3>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white transition-colors text-sm"
          >
            ✕
          </button>
        )}
      </div>

      {/* Strong Matches */}
      {data.strong_matches.length > 0 && (
        <div className="space-y-1.5">
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
            Strong Matches
          </div>
          <div className="flex flex-wrap gap-2">
            {data.strong_matches.map((skill) => (
              <span
                key={skill}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium bg-emerald-950/60 text-emerald-300 border border-emerald-800/80 rounded-md"
              >
                <span className="text-emerald-400 font-bold">✓</span> {skill}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Transferable Skills */}
      {data.transferable_matches.length > 0 && (
        <div className="space-y-1.5">
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
            Transferable Skills
          </div>
          <div className="space-y-1.5">
            {data.transferable_matches.map((item, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between text-xs p-2 bg-slate-800/50 border border-slate-700/60 rounded-lg text-slate-200"
              >
                <div className="flex items-center gap-2">
                  <span className="text-cyan-400 font-bold">↗</span>
                  <span className="font-semibold text-cyan-300">{item.job_skill}</span>
                  <span className="text-slate-400">(via {item.candidate_skill})</span>
                </div>
                <span className="text-[11px] text-slate-400 font-mono">
                  {Math.round(item.credit * 100)}% credit
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Missing Skills */}
      {data.missing_critical.length > 0 && (
        <div className="space-y-1.5">
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
            Missing Required
          </div>
          <div className="flex flex-wrap gap-2">
            {data.missing_critical.map((skill) => (
              <span
                key={skill}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium bg-rose-950/60 text-rose-300 border border-rose-800/80 rounded-md"
              >
                <span className="text-rose-400 font-bold">✗</span> {skill}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Eligibility Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
        <div className="p-3 bg-slate-800/40 border border-slate-700/60 rounded-lg">
          <div className="font-semibold text-slate-400 mb-1">Experience</div>
          <div className="flex items-center gap-2 text-slate-200">
            <span>{data.experience_status.eligible ? "✓" : "✗"}</span>
            <span>{data.experience_status.summary}</span>
          </div>
        </div>
        <div className="p-3 bg-slate-800/40 border border-slate-700/60 rounded-lg">
          <div className="font-semibold text-slate-400 mb-1">Location</div>
          <div className="flex items-center gap-2 text-slate-200">
            <span>{data.location_status.eligible ? "✓" : "✗"}</span>
            <span>{data.location_status.summary}</span>
          </div>
        </div>
      </div>

      {/* Recommendation Card */}
      <div
        className={`p-4 rounded-xl border text-sm leading-relaxed ${
          isApply
            ? "bg-emerald-950/20 border-emerald-900/50 text-emerald-200"
            : isConsider
            ? "bg-amber-950/20 border-amber-900/50 text-amber-200"
            : "bg-rose-950/20 border-rose-900/50 text-rose-200"
        }`}
      >
        <div className="font-semibold text-xs uppercase tracking-wider mb-1 opacity-80">
          Recommendation
        </div>
        <div>{data.recommendation_text}</div>
      </div>

      {/* Interview Talking Points */}
      {data.interview_talking_points.length > 0 && (
        <div className="space-y-1.5">
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
            Interview Talking Points
          </div>
          <ul className="list-disc list-inside space-y-1 text-xs text-slate-300">
            {data.interview_talking_points.map((pt, i) => (
              <li key={i}>{pt}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
