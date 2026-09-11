"use client";

import { useEffect, useState, useRef } from "react";
import { Upload, FileText, CheckCircle2, AlertCircle, RefreshCw } from "lucide-react";

interface ResumeItem {
  id: string;
  filename: string;
  resume_hash: string;
  is_active: boolean;
  created_at: string;
  extracted_data: {
    candidate_name?: string;
    target_roles?: string[];
    experience_level?: string;
    skills?: string[];
  };
}

export default function ResumePage() {
  const [resumes, setResumes] = useState<ResumeItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchResumes = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/v1/resumes");
      if (res.ok) {
        const data = await res.json();
        setResumes(data);
      }
    } catch {
      // Backend offline or error
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchResumes();
  }, []);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setMessage(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("http://localhost:8000/api/v1/resumes", {
        method: "POST",
        body: formData,
      });

      if (res.ok) {
        setMessage({ type: "success", text: "Resume uploaded, parsed, and embedded successfully!" });
        await fetchResumes();
      } else {
        const err = await res.json();
        setMessage({ type: "error", text: err.detail || "Failed to upload resume" });
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Network error";
      setMessage({ type: "error", text: msg });
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const activeResume = resumes.find((r) => r.is_active) || resumes[0];

  return (
    <div className="space-y-6 pb-16">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-white/[0.07]">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              DOCUMENT INTELLIGENCE
            </span>
            <span className="text-xs text-zinc-500">·</span>
            <span className="text-xs text-zinc-400">PDF & DOCX Support</span>
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-zinc-100">Resume Management</h2>
          <p className="text-xs text-zinc-400">
            Uploaded resumes are parsed with OmniRoute and embedded using local neural embeddings.
          </p>
        </div>

        <div>
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileUpload}
            accept=".pdf,.docx"
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="flex items-center gap-2 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-500 active:scale-[0.98] disabled:opacity-50 text-white rounded-xl text-xs font-semibold transition-all shadow-surface-glow"
          >
            {uploading ? (
              <RefreshCw className="w-4 h-4 animate-spin text-white" />
            ) : (
              <Upload className="w-4 h-4" />
            )}
            <span>{uploading ? "Analyzing with AI..." : "Upload New Resume"}</span>
          </button>
        </div>
      </div>

      {message && (
        <div
          className={`p-4 rounded-xl flex items-center gap-3 text-xs font-medium border shadow-lg ${
            message.type === "success"
              ? "bg-emerald-950/40 border-emerald-500/30 text-emerald-300"
              : "bg-rose-950/40 border-rose-500/30 text-rose-300"
          }`}
        >
          {message.type === "success" ? (
            <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
          ) : (
            <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
          )}
          <span>{message.text}</span>
        </div>
      )}

      {loading ? (
        <div className="py-20 text-center text-xs text-zinc-500 rounded-2xl bg-obsidian-900/40 border border-white/[0.06]">
          Loading active resume...
        </div>
      ) : activeResume ? (
        <div className="space-y-6">
          <div className="bg-obsidian-900/60 border border-white/[0.08] shadow-surface-inset rounded-2xl p-6 space-y-6">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-center gap-3.5">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-emerald-500/20 to-emerald-950/40 border border-emerald-500/30 text-emerald-400 flex items-center justify-center shadow-sm">
                  <FileText className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="text-base font-semibold text-zinc-100">{activeResume.filename}</h3>
                  <p className="text-[11px] text-zinc-500 font-mono mt-0.5">
                    SHA256: {activeResume.resume_hash.slice(0, 16)}... · Uploaded{" "}
                    {new Date(activeResume.created_at).toLocaleDateString()}
                  </p>
                </div>
              </div>

              <span className="px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs font-semibold">
                Active Resume
              </span>
            </div>

            <div className="pt-6 border-t border-white/[0.06] grid grid-cols-1 md:grid-cols-3 gap-5">
              <div className="p-4 rounded-xl bg-obsidian-950 border border-white/[0.06] space-y-1">
                <p className="text-[10px] text-zinc-500 font-semibold uppercase tracking-wider">Experience Level</p>
                <p className="text-base font-semibold text-zinc-100">
                  {activeResume.extracted_data?.experience_level || "Fresher"}
                </p>
              </div>

              <div className="p-4 rounded-xl bg-obsidian-950 border border-white/[0.06] space-y-1">
                <p className="text-[10px] text-zinc-500 font-semibold uppercase tracking-wider">Target Roles Extracted</p>
                <p className="text-base font-semibold text-emerald-400 truncate" title={activeResume.extracted_data?.target_roles?.join(", ")}>
                  {activeResume.extracted_data?.target_roles?.join(", ") || "General SWE"}
                </p>
              </div>

              <div className="p-4 rounded-xl bg-obsidian-950 border border-white/[0.06] space-y-1">
                <p className="text-[10px] text-zinc-500 font-semibold uppercase tracking-wider">Skills Detected</p>
                <p className="text-base font-semibold text-zinc-100">
                  {activeResume.extracted_data?.skills?.length || 0} canonical skills
                </p>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="rounded-2xl border border-dashed border-white/[0.08] p-16 text-center bg-obsidian-900/30 space-y-3">
          <FileText className="w-8 h-8 text-zinc-600 mx-auto" />
          <p className="text-sm font-medium text-zinc-300">No resumes indexed yet</p>
          <p className="text-xs text-zinc-500 max-w-sm mx-auto">
            Upload your latest resume (PDF or DOCX) to automatically calibrate your candidate profile.
          </p>
        </div>
      )}
    </div>
  );
}
