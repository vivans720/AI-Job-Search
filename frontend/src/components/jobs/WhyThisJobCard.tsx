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
      <div className="p-6 bg-white border border-slate-200 rounded-2xl text-slate-900 animate-pulse space-y-4 shadow-card-subtle">
        <div className="h-6 w-48 bg-slate-100 rounded-lg"></div>
        <div className="h-4 w-full bg-slate-100 rounded"></div>
        <div className="h-4 w-3/4 bg-slate-100 rounded"></div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-xs font-medium">
        {error || "Could not generate explanation"}
      </div>
    );
  }

  const isApply = data.verdict === "APPLY";
  const isConsider = data.verdict === "CONSIDER";

  const badgeBg = isApply
    ? "bg-emerald-50 text-emerald-700 border-emerald-200"
    : isConsider
    ? "bg-amber-50 text-amber-700 border-amber-200"
    : "bg-rose-50 text-rose-700 border-rose-200";

  return (
    <div className="p-6 bg-white border border-slate-200 rounded-2xl text-slate-800 shadow-card-subtle space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2.5 flex-wrap">
            <span className="text-2xl font-bold tracking-tight text-slate-900 font-tabular">
              {Math.round(data.overall_score)}% Match
            </span>
            <span className={`px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wider border rounded-full ${badgeBg}`}>
              {data.verdict}
            </span>
            {data.is_llm_generated && (
              <span className="px-2 py-0.5 text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-md">
                AI Synthesized
              </span>
            )}
          </div>
          <h3 className="text-xs text-slate-600 font-medium">{data.headline}</h3>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-700 transition-colors text-xs p-1"
          >
            ✕
          </button>
        )}
      </div>

      {/* Strong Matches */}
      {data.strong_matches.length > 0 && (
        <div className="space-y-2">
          <div className="text-xs font-bold text-slate-700 uppercase tracking-wider">
            Verified Skill Matches
          </div>
          <div className="flex flex-wrap gap-1.5">
            {data.strong_matches.map((skill) => (
              <span
                key={skill}
                className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-300 rounded-lg shadow-xs"
              >
                <span className="text-emerald-700 font-bold">✓</span> {skill}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Transferable Skills */}
      {data.transferable_matches.length > 0 && (
        <div className="space-y-2">
          <div className="text-xs font-bold text-slate-700 uppercase tracking-wider">
            Transferable Skills Bridge
          </div>
          <div className="space-y-1.5">
            {data.transferable_matches.map((item, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between text-xs p-3 bg-slate-50 border border-slate-200 rounded-xl text-slate-800"
              >
                <div className="flex items-center gap-2">
                  <span className="text-emerald-700 font-bold">↗</span>
                  <span className="font-bold text-slate-900">{item.job_skill}</span>
                  <span className="text-slate-500 font-normal">(via {item.candidate_skill})</span>
                </div>
                <span className="text-xs text-emerald-800 font-mono font-bold">
                  {Math.round(item.credit * 100)}% credit
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Missing Skills */}
      {data.missing_critical.length > 0 && (
        <div className="space-y-2">
          <div className="text-xs font-bold text-slate-700 uppercase tracking-wider">
            Missing Requirements
          </div>
          <div className="flex flex-wrap gap-1.5">
            {data.missing_critical.map((skill) => (
              <span
                key={skill}
                className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-semibold bg-rose-50 text-rose-800 border border-rose-300 rounded-lg shadow-xs"
              >
                <span className="text-rose-700 font-bold">✗</span> {skill}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Eligibility Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs sm:text-[13px]">
        <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl space-y-1">
          <div className="font-bold text-slate-700 text-xs uppercase tracking-wider">Experience Eligibility</div>
          <div className="flex items-center gap-2 text-slate-800 font-medium">
            <span className={data.experience_status.eligible ? "text-emerald-700 font-bold" : "text-rose-700 font-bold"}>
              {data.experience_status.eligible ? "✓" : "✗"}
            </span>
            <span>{data.experience_status.summary}</span>
          </div>
        </div>
        <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl space-y-1">
          <div className="font-bold text-slate-700 text-xs uppercase tracking-wider">Location Fit</div>
          <div className="flex items-center gap-2 text-slate-800 font-medium">
            <span className={data.location_status.eligible ? "text-emerald-700 font-bold" : "text-rose-700 font-bold"}>
              {data.location_status.eligible ? "✓" : "✗"}
            </span>
            <span>{data.location_status.summary}</span>
          </div>
        </div>
      </div>

      {/* Recommendation Card */}
      <div
        className={`p-4 rounded-xl border text-sm leading-relaxed font-normal ${
          isApply
            ? "bg-emerald-50/80 border-emerald-300 text-emerald-950"
            : isConsider
            ? "bg-amber-50/80 border-amber-300 text-amber-950"
            : "bg-rose-50/80 border-rose-300 text-rose-950"
        }`}
      >
        <div className="font-bold text-xs uppercase tracking-wider mb-1.5 opacity-90">
          Executive Recommendation
        </div>
        <div>{data.recommendation_text}</div>
      </div>

      {/* Interview Talking Points */}
      {data.interview_talking_points.length > 0 && (
        <div className="space-y-2">
          <div className="text-xs font-bold text-slate-700 uppercase tracking-wider">
            Target Interview Talking Points
          </div>
          <ul className="list-disc list-inside space-y-1.5 text-xs sm:text-[13px] text-slate-800 leading-relaxed">
            {data.interview_talking_points.map((pt, i) => (
              <li key={i}>{pt}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
