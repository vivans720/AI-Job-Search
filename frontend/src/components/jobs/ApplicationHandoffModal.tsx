"use client";

import React, { useState, useEffect } from "react";
import {
  X,
  ExternalLink,
  Copy,
  Check,
  Sparkles,
  FileText,
  HelpCircle,
  AlertCircle,
  RefreshCw,
  Send,
  UserCheck,
} from "lucide-react";
import { Card, Button } from "@/components/ui";
import { getApiUrl } from "@/lib/api";

interface ApplicationAnswer {
  question: string;
  answer: string;
  source_facts?: string[];
  requires_user_input?: boolean;
}

interface TailoredResumeContent {
  tailored_summary?: string;
  highlighted_skills?: string[];
  tailored_bullet_points?: string[];
  match_rationale?: string;
}

interface PreparationData {
  id?: string;
  job_id: string;
  resume_mode: "EXISTING" | "TAILORED";
  resume_id?: string | null;
  tailored_resume_content?: TailoredResumeContent | null;
  cover_letter?: string | null;
  question_answers?: ApplicationAnswer[];
  status: string;
}

interface ApplicationHandoffModalProps {
  isOpen: boolean;
  onClose: () => void;
  jobId: string;
  jobTitle: string;
  companyName: string;
  applicationUrl: string;
  onMarkApplied?: () => void;
}

export function ApplicationHandoffModal({
  isOpen,
  onClose,
  jobId,
  jobTitle,
  companyName,
  applicationUrl,
  onMarkApplied,
}: ApplicationHandoffModalProps) {
  const [loading, setLoading] = useState(false);
  const [prepData, setPrepData] = useState<PreparationData | null>(null);
  const [resumeMode, setResumeMode] = useState<"EXISTING" | "TAILORED">("EXISTING");
  const [coverLetter, setCoverLetter] = useState<string>("");
  const [coverLetterTone, setCoverLetterTone] = useState("PROFESSIONAL");
  const [answers, setAnswers] = useState<ApplicationAnswer[]>([]);
  const [newQuestion, setNewQuestion] = useState("");
  const [generatingResume, setGeneratingResume] = useState(false);
  const [generatingCoverLetter, setGeneratingCoverLetter] = useState(false);
  const [generatingAnswers, setGeneratingAnswers] = useState(false);
  const [copiedSection, setCopiedSection] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [appliedConfirming, setAppliedConfirming] = useState(false);

  // Fetch initial preparation
  useEffect(() => {
    if (!isOpen || !jobId) return;

    const fetchPrep = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(getApiUrl(`/api/v1/applications/prep/${jobId}`));
        if (res.ok) {
          const data = await res.json();
          setPrepData(data);
          setResumeMode(data.resume_mode || "EXISTING");
          setCoverLetter(data.cover_letter || "");
          setAnswers(data.question_answers || []);
        } else if (res.status === 404) {
          // Trigger initial preparation if none exists
          await prepareFull("EXISTING");
        } else {
          throw new Error(`Failed to load preparation (${res.status})`);
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Failed to load application kit";
        setError(msg);
      } finally {
        setLoading(false);
      }
    };

    fetchPrep();
  }, [isOpen, jobId]);

  const prepareFull = async (mode: "EXISTING" | "TAILORED") => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(getApiUrl(`/api/v1/applications/prep/${jobId}`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          resume_mode: mode,
          include_cover_letter: true,
          questions: answers.length > 0 ? answers.map((a) => a.question) : undefined,
        }),
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Server error (${res.status})`);
      }
      const data = await res.json();
      setPrepData({
        job_id: jobId,
        resume_mode: mode,
        tailored_resume_content: data.resume?.tailored_content || null,
        cover_letter: data.cover_letter || "",
        question_answers: data.answers || [],
        status: data.prep_status || "READY_FOR_REVIEW",
      });
      setResumeMode(mode);
      setCoverLetter(data.cover_letter || "");
      setAnswers(data.answers || []);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error generating application";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleResumeModeChange = async (mode: "EXISTING" | "TAILORED") => {
    setResumeMode(mode);
    if (mode === "TAILORED" && !prepData?.tailored_resume_content) {
      setGeneratingResume(true);
      try {
        const res = await fetch(getApiUrl(`/api/v1/applications/prep/${jobId}/resume`), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mode: "TAILORED" }),
        });
        if (res.ok) {
          const data = await res.json();
          setPrepData((prev) =>
            prev ? { ...prev, resume_mode: "TAILORED", tailored_resume_content: data.tailored_content } : null
          );
        }
      } catch (err) {
        console.error(err);
      } finally {
        setGeneratingResume(false);
      }
    } else {
      try {
        await fetch(getApiUrl(`/api/v1/applications/prep/${jobId}/resume`), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mode: "EXISTING" }),
        });
      } catch (err) {
        console.error(err);
      }
    }
  };

  const handleRegenerateCoverLetter = async () => {
    setGeneratingCoverLetter(true);
    try {
      const res = await fetch(getApiUrl(`/api/v1/applications/prep/${jobId}/cover-letter`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tone: coverLetterTone }),
      });
      if (res.ok) {
        const data = await res.json();
        setCoverLetter(data.cover_letter);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setGeneratingCoverLetter(false);
    }
  };

  const handleAddQuestion = async () => {
    if (!newQuestion.trim()) return;
    setGeneratingAnswers(true);
    const updated = [...answers.map((a) => a.question), newQuestion.trim()];
    try {
      const res = await fetch(getApiUrl(`/api/v1/applications/prep/${jobId}/answers`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ questions: updated }),
      });
      if (res.ok) {
        const data = await res.json();
        setAnswers(data.answers || []);
        setNewQuestion("");
      }
    } catch (err) {
      console.error(err);
    } finally {
      setGeneratingAnswers(false);
    }
  };

  const copyToClipboard = (text: string, sectionKey: string) => {
    navigator.clipboard.writeText(text);
    setCopiedSection(sectionKey);
    setTimeout(() => setCopiedSection(null), 2000);
  };

  const handleConfirmApplied = async () => {
    setAppliedConfirming(true);
    try {
      // 1. Update prep status to APPROVED
      await fetch(getApiUrl(`/api/v1/applications/prep/${jobId}/status`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "APPROVED" }),
      });

      // 2. Update job pipeline status to APPLIED with user confirmation
      await fetch(getApiUrl(`/api/v1/saved-jobs/${jobId}/status`), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "APPLIED", notes: "Applied manually via Application Kit" }),
      });

      if (onMarkApplied) {
        onMarkApplied();
      }
      onClose();
    } catch (err) {
      console.error(err);
    } finally {
      setAppliedConfirming(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4 overflow-y-auto">
      <div
        className="bg-white border border-slate-200 rounded-2xl shadow-2xl max-w-3xl w-full max-h-[90vh] flex flex-col overflow-hidden animate-fade-in"
        role="dialog"
        aria-modal="true"
      >
        {/* Header */}
        <div className="p-5 border-b border-slate-200 bg-slate-50/80 flex items-start justify-between gap-4">
          <div className="space-y-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-purple-50 text-purple-800 border border-purple-200">
                Phase 9: Application Kit
              </span>
              <span className="text-xs font-semibold text-slate-500 font-mono">
                Status: {prepData?.status || "PREPARING"}
              </span>
            </div>
            <h2 className="text-lg sm:text-xl font-bold text-slate-900 tracking-tight truncate">
              {jobTitle}
            </h2>
            <p className="text-xs text-slate-600 font-medium">{companyName}</p>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-5 sm:p-6 space-y-6">
          {loading ? (
            <div className="py-20 text-center text-xs text-slate-400 space-y-3">
              <RefreshCw className="w-6 h-6 animate-spin text-purple-600 mx-auto" />
              <p className="font-medium text-slate-600">Preparing application materials...</p>
              <p className="text-slate-400 text-[11px]">
                Grounding answers in your profile and deep job research
              </p>
            </div>
          ) : error ? (
            <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          ) : (
            <>
              {/* Section 1: Resume Mode Choice */}
              <Card className="p-4 space-y-3 border-slate-200/90">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <FileText className="w-4 h-4 text-purple-600" />
                    <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                      Resume Selection
                    </h3>
                  </div>
                  <div className="flex items-center gap-1.5 bg-slate-100 p-1 rounded-xl text-xs font-semibold">
                    <button
                      onClick={() => handleResumeModeChange("EXISTING")}
                      className={`px-3 py-1 rounded-lg transition-all ${
                        resumeMode === "EXISTING"
                          ? "bg-white text-slate-900 shadow-xs"
                          : "text-slate-500 hover:text-slate-800"
                      }`}
                    >
                      Existing Primary
                    </button>
                    <button
                      onClick={() => handleResumeModeChange("TAILORED")}
                      className={`px-3 py-1 rounded-lg flex items-center gap-1 transition-all ${
                        resumeMode === "TAILORED"
                          ? "bg-white text-purple-700 shadow-xs"
                          : "text-slate-500 hover:text-slate-800"
                      }`}
                    >
                      <Sparkles className="w-3 h-3 text-purple-600" />
                      AI-Tailored
                    </button>
                  </div>
                </div>

                {resumeMode === "EXISTING" ? (
                  <p className="text-xs text-slate-600 leading-relaxed">
                    Using your default verified primary resume without any synthetic modifications.
                  </p>
                ) : (
                  <div className="space-y-2.5 pt-1 text-xs">
                    {generatingResume ? (
                      <div className="flex items-center gap-2 text-slate-500 py-3">
                        <RefreshCw className="w-3.5 h-3.5 animate-spin text-purple-600" />
                        <span>Tailoring bullet points to match job requirements...</span>
                      </div>
                    ) : prepData?.tailored_resume_content ? (
                      <div className="space-y-2 p-3 bg-purple-50/60 border border-purple-200/70 rounded-xl">
                        {prepData.tailored_resume_content.tailored_summary && (
                          <div>
                            <span className="font-bold text-purple-950 block text-[11px] uppercase tracking-wide">
                              Tailored Summary:
                            </span>
                            <p className="text-slate-700 leading-relaxed mt-0.5">
                              {prepData.tailored_resume_content.tailored_summary}
                            </p>
                          </div>
                        )}
                        {prepData.tailored_resume_content.highlighted_skills && (
                          <div>
                            <span className="font-bold text-purple-950 block text-[11px] uppercase tracking-wide">
                              Highlighted Skills:
                            </span>
                            <div className="flex flex-wrap gap-1.5 mt-1">
                              {prepData.tailored_resume_content.highlighted_skills.map((s) => (
                                <span
                                  key={s}
                                  className="px-2 py-0.5 bg-white border border-purple-200 rounded text-[11px] font-medium text-purple-800"
                                >
                                  {s}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    ) : (
                      <p className="text-slate-500 italic">No tailored content generated yet.</p>
                    )}
                  </div>
                )}
              </Card>

              {/* Section 2: Cover Letter */}
              <Card className="p-4 space-y-3 border-slate-200/90">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-purple-600" />
                    <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                      Targeted Cover Letter
                    </h3>
                  </div>

                  <div className="flex items-center gap-2">
                    <select
                      value={coverLetterTone}
                      onChange={(e) => setCoverLetterTone(e.target.value)}
                      className="text-xs bg-slate-50 border border-slate-200 rounded-lg px-2 py-1 font-medium text-slate-700"
                    >
                      <option value="PROFESSIONAL">Professional</option>
                      <option value="ENTHUSIASTIC">Enthusiastic</option>
                      <option value="CONCISE">Concise</option>
                    </select>

                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={generatingCoverLetter}
                      onClick={handleRegenerateCoverLetter}
                      leftIcon={<RefreshCw className={`w-3 h-3 ${generatingCoverLetter ? "animate-spin" : ""}`} />}
                    >
                      Regenerate
                    </Button>

                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => copyToClipboard(coverLetter, "cover_letter")}
                      leftIcon={
                        copiedSection === "cover_letter" ? (
                          <Check className="w-3 h-3 text-emerald-600" />
                        ) : (
                          <Copy className="w-3 h-3" />
                        )
                      }
                    >
                      {copiedSection === "cover_letter" ? "Copied" : "Copy"}
                    </Button>
                  </div>
                </div>

                <textarea
                  value={coverLetter}
                  onChange={(e) => setCoverLetter(e.target.value)}
                  rows={6}
                  placeholder="Generated cover letter will appear here..."
                  className="w-full text-xs font-sans text-slate-800 bg-slate-50/60 border border-slate-200 rounded-xl p-3 focus:outline-none focus:ring-2 focus:ring-purple-500/20 leading-relaxed resize-y"
                />
              </Card>

              {/* Section 3: Screening Q&A */}
              <Card className="p-4 space-y-3 border-slate-200/90">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <HelpCircle className="w-4 h-4 text-purple-600" />
                    <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                      Application Screening Q&A ({answers.length})
                    </h3>
                  </div>
                </div>

                <div className="space-y-3 pt-1">
                  {answers.map((item, idx) => (
                    <div
                      key={idx}
                      className={`p-3 rounded-xl border text-xs space-y-1.5 ${
                        item.requires_user_input
                          ? "bg-amber-50/70 border-amber-200"
                          : "bg-slate-50 border-slate-200/80"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <span className="font-bold text-slate-900">Q: {item.question}</span>
                        {item.requires_user_input && (
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-200/80 text-amber-900 shrink-0">
                            Candidate Input Recommended
                          </span>
                        )}
                      </div>
                      <p className="text-slate-700 leading-relaxed">
                        <strong>A:</strong> {item.answer}
                      </p>
                      {item.source_facts && item.source_facts.length > 0 && (
                        <p className="text-[11px] text-slate-400">
                          Grounding: {item.source_facts.join(", ")}
                        </p>
                      )}
                    </div>
                  ))}

                  {/* Add Screening Question input */}
                  <div className="flex items-center gap-2 pt-2">
                    <input
                      type="text"
                      value={newQuestion}
                      onChange={(e) => setNewQuestion(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          handleAddQuestion();
                        }
                      }}
                      placeholder="Paste screening question (e.g. 'How many years of Python experience?')..."
                      className="flex-1 text-xs px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-purple-500/20"
                    />
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={!newQuestion.trim() || generatingAnswers}
                      onClick={handleAddQuestion}
                      leftIcon={<Send className="w-3 h-3" />}
                    >
                      Answer
                    </Button>
                  </div>
                </div>
              </Card>
            </>
          )}
        </div>

        {/* Section 4: Handoff Action Footer */}
        <div className="p-4 sm:p-5 border-t border-slate-200 bg-slate-50/90 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <a
              href={applicationUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 sm:flex-none inline-flex items-center justify-center gap-1.5 px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-xl text-xs font-semibold shadow-xs transition active:scale-[0.98]"
            >
              <span>Open Application Link</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>

            <button
              onClick={() => copyToClipboard(applicationUrl, "app_url")}
              className="px-3 py-2 rounded-xl border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 text-xs font-medium transition shadow-xs"
              title="Copy Application URL"
            >
              {copiedSection === "app_url" ? "URL Copied ✓" : "Copy Link"}
            </button>
          </div>

          <Button
            variant="primary"
            size="md"
            disabled={appliedConfirming}
            onClick={handleConfirmApplied}
            leftIcon={<UserCheck className="w-4 h-4 text-emerald-400" />}
            className="w-full sm:w-auto bg-emerald-600 hover:bg-emerald-700 border-emerald-500"
          >
            {appliedConfirming ? "Confirming..." : "I've Applied ✓"}
          </Button>
        </div>
      </div>
    </div>
  );
}
