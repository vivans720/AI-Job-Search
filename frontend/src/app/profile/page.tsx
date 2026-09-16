"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import {
  ShieldAlert,
  Sparkles,
  Plus,
  X,
  RotateCcw,
  FileText,
  Upload,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  AlertTriangle,
  Check,
  Bookmark,
  Layers,
} from "lucide-react";
import { getApiUrl } from "@/lib/api";

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

interface CandidateProfile {
  id: string;
  experience_level: string;
  experience_years: number;
  target_roles: string[];
  excluded_roles: string[];
  programming_languages: string[];
  frameworks: string[];
  databases: string[];
  cloud: string[];
  tools: string[];
  skills: string[];
  education: Array<{
    degree?: string;
    institution?: string;
    graduation_year?: number;
    grade?: string;
  }>;
  projects: Array<{
    title?: string;
    description?: string;
    technologies?: string[];
  }>;
  preferred_locations: string[];
  remote_preference: boolean;
  internship_allowed?: boolean;
  fulltime_allowed?: boolean;
  minimum_salary_lpa?: number | null;
  work_experience?: Array<Record<string, unknown>>;
  certifications?: string[];
  manual_overrides: Record<string, unknown>;
}

type SkillCategoryKey =
  | "programming_languages"
  | "frameworks"
  | "databases"
  | "cloud"
  | "tools";

function formatExperienceLevel(level?: string): string {
  if (!level) return "Entry Level";
  if (level.toLowerCase() === "fresher") return "Entry Level (0-1y)";
  return level;
}

export default function ProfilePage() {
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [resumes, setResumes] = useState<ResumeItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploadingResume, setUploadingResume] = useState(false);
  const [saving, setSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [resumeMessage, setResumeMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  // Form Inputs
  const [newTargetRole, setNewTargetRole] = useState("");
  const [newExcludedRole, setNewExcludedRole] = useState("");
  const [newSkill, setNewSkill] = useState("");

  // Destructive Confirmation Modal & Undo Buffer
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [previousRolesForUndo, setPreviousRolesForUndo] = useState<string[] | null>(null);

  // Target Ingestion Skills State (persisted in preferences.preferred_technologies)
  const [syncSkills, setSyncSkills] = useState<string[]>([]);
  const [newSyncSkillInput, setNewSyncSkillInput] = useState("");
  const [savingSyncSkills, setSavingSyncSkills] = useState(false);
  const [syncSkillsSavedToast, setSyncSkillsSavedToast] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchPreferences = async () => {
    try {
      const res = await fetch(getApiUrl("/api/v1/preferences"));
      if (res.ok) {
        const prefData = await res.json();
        if (prefData && Array.isArray(prefData.preferred_technologies)) {
          setSyncSkills(prefData.preferred_technologies);
        }
      }
    } catch {
      // ignore
    }
  };

  const handleSaveSyncSkills = async (customSkills?: string[]) => {
    const toSave = customSkills !== undefined ? customSkills : syncSkills;
    setSavingSyncSkills(true);
    try {
      const res = await fetch(getApiUrl("/api/v1/preferences"), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ preferred_technologies: toSave }),
      });
      if (res.ok) {
        setSyncSkills(toSave);
        setSyncSkillsSavedToast(true);
        setTimeout(() => setSyncSkillsSavedToast(false), 3000);
        setResumeMessage({
          type: "success",
          text: "Scraper target skills saved. Feeds will crawl these skills when synced from Jobs page.",
        });
      } else {
        setResumeMessage({
          type: "error",
          text: "Failed to save scraper target skills.",
        });
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Network error.";
      setResumeMessage({ type: "error", text: msg });
    } finally {
      setSavingSyncSkills(false);
    }
  };

  const toggleSyncSkill = (skill: string) => {
    const normalized = skill.trim().toLowerCase();
    if (syncSkills.some((s) => s.toLowerCase() === normalized)) {
      setSyncSkills(syncSkills.filter((s) => s.toLowerCase() !== normalized));
    } else {
      setSyncSkills([...syncSkills, skill.trim()]);
    }
  };

  const handleAddCustomSyncSkill = () => {
    const trimmed = newSyncSkillInput.trim().toLowerCase();
    if (!trimmed) return;
    if (!syncSkills.some((s) => s.toLowerCase() === trimmed)) {
      setSyncSkills([...syncSkills, trimmed]);
    }
    setNewSyncSkillInput("");
  };

  const handleRemoveSyncSkill = (skillToRemove: string) => {
    setSyncSkills(syncSkills.filter((s) => s.toLowerCase() !== skillToRemove.toLowerCase()));
  };

  const handleResetSyncSkillsToTop5 = () => {
    if (profile?.skills && profile.skills.length > 0) {
      setSyncSkills(profile.skills.slice(0, 5));
    } else {
      setSyncSkills(["javascript", "typescript", "react", "node.js", "python"]);
    }
  };

  const fetchProfile = async () => {
    try {
      const res = await fetch(getApiUrl("/api/v1/profile"));
      if (res.ok) {
        const data = await res.json();
        setProfile(data);
        setErrorMessage(null);
      } else if (res.status === 404) {
        setProfile(null);
      } else {
        const err = await res.json().catch(() => ({}));
        setErrorMessage(err.detail || "Unable to load candidate profile from server.");
      }
    } catch {
      setErrorMessage("Cannot connect to backend server. Please verify the API is running.");
    }
  };

  const fetchResumes = async () => {
    try {
      const res = await fetch(getApiUrl("/api/v1/resumes"));
      if (res.ok) {
        const data = await res.json();
        setResumes(data);
      }
    } catch {
      // Handled by fetchProfile banner
    }
  };

  const loadData = useCallback(async () => {
    setLoading(true);
    await Promise.all([fetchProfile(), fetchResumes(), fetchPreferences()]);
    setLoading(false);
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const updateProfileFields = async (
    updates: Partial<CandidateProfile>,
    successNotice?: string
  ) => {
    if (!profile) return;
    setSaving(true);
    setErrorMessage(null);
    try {
      const res = await fetch(getApiUrl("/api/v1/profile"), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates),
      });

      if (res.ok) {
        const updated = await res.json();
        setProfile(updated);
        if (successNotice) {
          setResumeMessage({ type: "success", text: successNotice });
          setTimeout(() => setResumeMessage(null), 4000);
        }
      } else {
        const err = await res.json().catch(() => ({}));
        setErrorMessage(err.detail || "Failed to update profile settings.");
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Network error";
      setErrorMessage(`Failed to save changes: ${msg}`);
    } finally {
      setSaving(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadingResume(true);
    setResumeMessage(null);
    setErrorMessage(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(getApiUrl("/api/v1/resumes"), {
        method: "POST",
        body: formData,
      });

      if (res.ok) {
        setResumeMessage({
          type: "success",
          text: `"${file.name}" uploaded, parsed, and candidate profile synchronized!`,
        });
        await Promise.all([fetchResumes(), fetchProfile()]);
      } else {
        const err = await res.json().catch(() => ({}));
        setResumeMessage({
          type: "error",
          text: err.detail || "Failed to upload and parse resume.",
        });
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Network error during upload.";
      setResumeMessage({ type: "error", text: msg });
    } finally {
      setUploadingResume(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  // Target Roles
  const handleAddTargetRole = async (customRole?: string) => {
    const roleToAdd = (customRole || newTargetRole).trim();
    if (!roleToAdd || !profile) return;
    if (profile.target_roles.some((r) => r.toLowerCase() === roleToAdd.toLowerCase())) return;

    const updatedTarget = [...profile.target_roles, roleToAdd];
    await updateProfileFields({ target_roles: updatedTarget });
    setNewTargetRole("");
  };

  const handleRemoveTargetRole = async (roleToRemove: string) => {
    if (!profile) return;
    const updatedTarget = profile.target_roles.filter((r) => r !== roleToRemove);
    await updateProfileFields({ target_roles: updatedTarget });
  };

  const handleConfirmResetRoles = async () => {
    setShowResetConfirm(false);
    if (!profile) return;
    setSaving(true);
    const backupRoles = [...profile.target_roles];
    try {
      const resResume = await fetch(getApiUrl("/api/v1/resumes/active"));
      let extractedRoles = ["Full Stack Developer", "Backend Developer", "AI Engineer"];
      if (resResume.ok) {
        const resumeData = await resResume.json();
        if (resumeData?.extracted_data?.target_roles?.length) {
          extractedRoles = resumeData.extracted_data.target_roles;
        }
      }
      setPreviousRolesForUndo(backupRoles);
      await updateProfileFields(
        { target_roles: extractedRoles },
        "Target roles reset to resume defaults."
      );
    } catch {
      setErrorMessage("Could not retrieve active resume data for reset.");
    } finally {
      setSaving(false);
    }
  };

  const handleUndoResetRoles = async () => {
    if (!previousRolesForUndo || !profile) return;
    const restored = [...previousRolesForUndo];
    setPreviousRolesForUndo(null);
    await updateProfileFields(
      { target_roles: restored },
      "Previous custom target roles restored."
    );
  };

  // Excluded Roles
  const handleAddExcludedRole = async (customRole?: string) => {
    const roleToAdd = (customRole || newExcludedRole).trim();
    if (!roleToAdd || !profile) return;
    if (profile.excluded_roles.some((r) => r.toLowerCase() === roleToAdd.toLowerCase())) return;

    const updatedExcluded = [...profile.excluded_roles, roleToAdd];
    await updateProfileFields({ excluded_roles: updatedExcluded });
    setNewExcludedRole("");
  };

  const handleRemoveExcludedRole = async (roleToRemove: string) => {
    if (!profile) return;
    const updatedExcluded = profile.excluded_roles.filter((r) => r !== roleToRemove);
    await updateProfileFields({ excluded_roles: updatedExcluded });
  };

  // Skills Management (Flat list add/remove)
  const handleRemoveSkill = async (skillToRemove: string) => {
    if (!profile) return;
    const updatedSkills = (profile.skills || []).filter((s) => s !== skillToRemove);

    // Also clean up from category arrays if present
    const categoryUpdates: Partial<CandidateProfile> = {};
    const catKeys: SkillCategoryKey[] = [
      "programming_languages",
      "frameworks",
      "databases",
      "cloud",
      "tools",
    ];
    for (const key of catKeys) {
      if (profile[key] && profile[key].includes(skillToRemove)) {
        categoryUpdates[key] = profile[key].filter((s) => s !== skillToRemove);
      }
    }

    const currentCore = Array.isArray(profile.manual_overrides?.core_skills)
      ? (profile.manual_overrides.core_skills as string[])
      : [];
    const updatedCore = currentCore.filter((s) => s !== skillToRemove);

    await updateProfileFields({
      skills: updatedSkills,
      ...categoryUpdates,
      manual_overrides: {
        ...(profile.manual_overrides || {}),
        core_skills: updatedCore,
      },
    });
  };

  const handleAddSkill = async (customSkill?: string) => {
    const skillToAdd = (customSkill || newSkill).trim();
    if (!skillToAdd || !profile) return;

    const currentSkills = profile.skills || [];
    if (currentSkills.some((s) => s.toLowerCase() === skillToAdd.toLowerCase())) return;

    const updatedSkills = [...currentSkills, skillToAdd];

    await updateProfileFields({
      skills: updatedSkills,
    });

    setNewSkill("");
  };

  const activeResume = resumes.find((r) => r.is_active) || resumes[0];

  const fileUploadInput = (
    <input
      type="file"
      ref={fileInputRef}
      onChange={handleFileUpload}
      accept=".pdf,.docx"
      className="hidden"
      aria-label="Upload resume PDF or DOCX"
    />
  );

  if (loading) {
    return (
      <div className="p-16 text-center text-xs text-slate-500 font-mono rounded-2xl bg-white border border-slate-200 shadow-card-subtle">
        Loading candidate profile...
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-16">
      {fileUploadInput}

      {/* Network / Server Error Banner */}
      {errorMessage && (
        <div className="p-4 rounded-xl flex items-start justify-between gap-3 text-xs font-medium border bg-rose-50 border-rose-200 text-rose-800">
          <div className="flex items-center gap-2.5">
            <AlertCircle className="w-4 h-4 shrink-0 text-rose-600" />
            <span>{errorMessage}</span>
          </div>
          <button
            onClick={loadData}
            className="px-2.5 py-1 bg-rose-100 hover:bg-rose-200 text-rose-900 rounded-lg text-[11px] font-semibold transition-colors flex items-center gap-1"
          >
            <RefreshCw className="w-3 h-3" />
            <span>Retry</span>
          </button>
        </div>
      )}

      {/* Header */}
      <div className="pb-6 border-b border-slate-200">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 font-mono tracking-wider uppercase">
              CANDIDATE INTELLIGENCE
            </span>
            {profile && (
              <>
                <span className="text-xs text-slate-400">·</span>
                <span className="text-xs text-slate-600 font-mono">
                  {formatExperienceLevel(profile.experience_level)} ({profile.experience_years}y Exp)
                </span>
              </>
            )}
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Candidate Profile</h1>
          <p className="text-xs text-slate-500 max-w-2xl leading-relaxed">
            Configure matching intelligence, fine-tune skill weights, and control negative search boundaries.
          </p>
        </div>
      </div>

      {/* Resume Message Toast with Undo Support */}
      {resumeMessage && (
        <div
          role="status"
          aria-live="polite"
          className={`p-3.5 rounded-xl flex items-center justify-between gap-3 text-xs font-medium border ${
            resumeMessage.type === "success"
              ? "bg-emerald-50 border-emerald-200 text-emerald-800"
              : "bg-rose-50 border-rose-200 text-rose-800"
          }`}
        >
          <div className="flex items-center gap-3">
            {resumeMessage.type === "success" ? (
              <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600" />
            ) : (
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-600" />
            )}
            <span>{resumeMessage.text}</span>
          </div>

          {previousRolesForUndo && (
            <button
              onClick={handleUndoResetRoles}
              disabled={saving}
              className="px-2.5 py-1 bg-emerald-700 hover:bg-emerald-800 text-white rounded-lg text-[11px] font-semibold transition-colors flex items-center gap-1 shadow-xs"
            >
              <RotateCcw className="w-3 h-3" />
              <span>Undo Reset</span>
            </button>
          )}
        </div>
      )}

      {/* Empty State */}
      {!profile && !activeResume && (
        <div className="rounded-2xl border border-dashed border-slate-300 p-16 text-center bg-white space-y-4 shadow-card-subtle">
          <FileText className="w-8 h-8 text-slate-400 mx-auto" />
          <div className="space-y-1">
            <p className="text-sm font-semibold text-slate-800">No candidate profile or resume yet</p>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              Upload your latest resume (PDF or DOCX) to automatically extract your skills, target roles, and experience.
            </p>
          </div>
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploadingResume}
            className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-semibold transition-all shadow-xs"
          >
            <Upload className="w-4 h-4" />
            <span>Select Resume File</span>
          </button>
        </div>
      )}

      {/* Active Resume Card */}
      {activeResume && (
        <div className="bg-white border border-slate-200 shadow-card-subtle rounded-2xl p-5 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-3.5">
              <div className="w-10 h-10 rounded-xl bg-slate-100 border border-slate-200 text-emerald-600 flex items-center justify-center shadow-xs">
                <FileText className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-bold text-slate-900">{activeResume.filename}</h3>
                  <span className="px-2 py-0.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 text-[10px] font-semibold">
                    Active Resume
                  </span>
                </div>
                <p className="text-[11px] text-slate-500 font-mono mt-0.5 flex items-center gap-1.5 flex-wrap">
                  <span title={`Full SHA256: ${activeResume.resume_hash}`} className="cursor-help underline decoration-dotted underline-offset-2">
                    SHA256: {activeResume.resume_hash.slice(0, 8)}...
                  </span>
                  <span>·</span>
                  <span>Uploaded {new Date(activeResume.created_at).toLocaleDateString()}</span>
                </p>
              </div>
            </div>

            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploadingResume || saving}
              className="flex items-center gap-2 px-3.5 py-2 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 text-emerald-800 active:scale-[0.98] disabled:opacity-50 rounded-xl text-xs font-semibold transition-all shadow-xs self-start sm:self-auto"
            >
              {uploadingResume ? (
                <RefreshCw className="w-3.5 h-3.5 animate-spin text-emerald-700" />
              ) : (
                <Upload className="w-3.5 h-3.5 text-emerald-700" />
              )}
              <span>{uploadingResume ? "Parsing with AI..." : "Replace Resume"}</span>
            </button>
          </div>

          <div className="pt-3 border-t border-slate-100 grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/80 space-y-0.5">
              <p className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider">Experience Level</p>
              <p className="text-xs font-bold text-slate-900">
                {formatExperienceLevel(activeResume.extracted_data?.experience_level || profile?.experience_level)}
              </p>
            </div>

            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/80 space-y-0.5">
              <p className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider">Target Roles Extracted</p>
              <p className="text-xs font-bold text-emerald-700 truncate" title={activeResume.extracted_data?.target_roles?.join(", ")}>
                {activeResume.extracted_data?.target_roles?.join(", ") || profile?.target_roles?.join(", ") || "General SWE"}
              </p>
            </div>

            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/80 space-y-0.5">
              <p className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider">Skills Detected</p>
              <p className="text-xs font-bold text-slate-900 font-tabular">
                {profile?.skills?.length || activeResume.extracted_data?.skills?.length || 0} active skills
              </p>
            </div>
          </div>
        </div>
      )}

      {profile && (
        <>
          {/* Target & Excluded Roles */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Target Roles Card */}
            <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-card-subtle space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-emerald-600 shrink-0" />
                  <h2 className="text-sm font-bold text-slate-900 tracking-tight">
                    Target Roles <span className="text-xs font-normal text-slate-500">(Active Scope)</span>
                  </h2>
                </div>
                <button
                  onClick={() => setShowResetConfirm(true)}
                  disabled={saving}
                  className="text-xs text-slate-500 hover:text-emerald-700 font-medium flex items-center gap-1 transition-colors"
                  title="Reset target roles to active resume extraction"
                >
                  <RotateCcw className="w-3 h-3" />
                  <span>Reset to Resume</span>
                </button>
              </div>

              <div className="flex flex-wrap gap-2">
                {profile.target_roles.length > 0 ? (
                  profile.target_roles.map((role) => (
                    <span
                      key={role}
                      className="flex items-center gap-1.5 pl-3 pr-1.5 py-1 bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs rounded-lg font-medium shadow-xs"
                    >
                      <span>{role}</span>
                      <button
                        onClick={() => handleRemoveTargetRole(role)}
                        disabled={saving}
                        aria-label={`Remove target role ${role}`}
                        className="p-1 -mr-0.5 rounded hover:bg-emerald-100 hover:text-emerald-950 transition-colors inline-flex items-center justify-center"
                        title={`Remove ${role}`}
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </span>
                  ))
                ) : (
                  <p className="text-xs text-amber-600">No target roles active. Add at least one.</p>
                )}
              </div>

              <div className="flex items-center gap-2 pt-2">
                <label htmlFor="target-role-input" className="sr-only">
                  Add target role
                </label>
                <input
                  id="target-role-input"
                  type="text"
                  value={newTargetRole}
                  onChange={(e) => setNewTargetRole(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleAddTargetRole()}
                  placeholder="e.g. Full Stack Developer, AI Engineer"
                  className="flex-1 bg-white border border-slate-200 rounded-xl px-3.5 py-2 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-400/20 shadow-xs"
                />
                <button
                  onClick={() => handleAddTargetRole()}
                  disabled={saving || !newTargetRole.trim()}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 active:scale-[0.98] disabled:opacity-50 text-white text-xs font-semibold rounded-xl flex items-center gap-1 transition-all shadow-xs"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Add</span>
                </button>
              </div>

              {/* Quick Suggestions for Target Roles */}
              <div className="flex flex-wrap items-center gap-1.5 pt-1">
                <span className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider">Quick add:</span>
                {[
                  "Full Stack Developer",
                  "Backend Developer",
                  "Frontend Developer",
                  "AI Engineer",
                  "Python Developer",
                  "Node.js Developer",
                ].map(
                  (suggested) =>
                    !profile.target_roles.includes(suggested) && (
                      <button
                        key={suggested}
                        onClick={() => handleAddTargetRole(suggested)}
                        disabled={saving}
                        className="px-2 py-0.5 rounded-md bg-slate-50 hover:bg-slate-100 text-[10px] text-slate-600 hover:text-emerald-700 border border-slate-200 transition-colors"
                      >
                        + {suggested}
                      </button>
                    )
                )}
              </div>

              <p className="text-[11px] text-slate-500">
                Agent dynamically expands search queries around these target roles.
              </p>
            </div>

            {/* Excluded Roles Card */}
            <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-card-subtle space-y-4">
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-rose-500 shrink-0" />
                <h2 className="text-sm font-bold text-slate-900 tracking-tight">
                  Excluded Roles <span className="text-xs font-normal text-slate-500">(Negative Filter)</span>
                </h2>
              </div>

              <div className="flex flex-wrap gap-2">
                {profile.excluded_roles.length > 0 ? (
                  profile.excluded_roles.map((role) => (
                    <span
                      key={role}
                      className="flex items-center gap-1.5 pl-3 pr-1.5 py-1 bg-rose-50 border border-rose-200 text-rose-800 text-xs rounded-lg font-medium shadow-xs"
                    >
                      <span>{role}</span>
                      <button
                        onClick={() => handleRemoveExcludedRole(role)}
                        disabled={saving}
                        aria-label={`Remove excluded role ${role}`}
                        className="p-1 -mr-0.5 rounded hover:bg-rose-100 hover:text-rose-950 transition-colors inline-flex items-center justify-center"
                        title={`Remove ${role}`}
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </span>
                  ))
                ) : (
                  <p className="text-xs text-slate-500">No excluded roles configured.</p>
                )}
              </div>

              <div className="flex items-center gap-2 pt-2">
                <label htmlFor="excluded-role-input" className="sr-only">
                  Add excluded role
                </label>
                <input
                  id="excluded-role-input"
                  type="text"
                  value={newExcludedRole}
                  onChange={(e) => setNewExcludedRole(e.target.value)}
                  placeholder="e.g. Data Analyst, QA, Sales"
                  className="flex-1 bg-white border border-slate-200 rounded-xl px-3.5 py-2 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-400/20 shadow-xs"
                  onKeyDown={(e) => e.key === "Enter" && handleAddExcludedRole()}
                />
                <button
                  onClick={() => handleAddExcludedRole()}
                  disabled={saving || !newExcludedRole.trim()}
                  className="flex items-center gap-1 px-4 py-2 bg-rose-600 hover:bg-rose-500 active:scale-[0.98] text-white rounded-xl text-xs font-semibold transition-all disabled:opacity-50 shadow-xs"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Exclude</span>
                </button>
              </div>

              {/* Quick Suggestions for Excluded Roles */}
              <div className="flex flex-wrap items-center gap-1.5 pt-1">
                <span className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider">Quick exclude:</span>
                {["Data Analyst", "QA Engineer", "Sales Engineer", "Technical Writer", "Intern"].map(
                  (suggested) =>
                    !profile.excluded_roles.includes(suggested) && (
                      <button
                        key={suggested}
                        onClick={() => handleAddExcludedRole(suggested)}
                        disabled={saving}
                        className="px-2 py-0.5 rounded-md bg-white hover:bg-rose-50 text-[10px] text-rose-900 border border-slate-200 hover:border-rose-200 transition-colors"
                      >
                        + {suggested}
                      </button>
                    )
                )}
              </div>

              <p className="text-[11px] text-slate-500">
                Jobs matching excluded titles or keywords are filtered automatically.
              </p>
            </div>
          </div>

          {/* Skills */}
          <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-card-subtle space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-slate-900">Skills</h3>
                <span className="text-xs text-slate-400 font-mono font-normal">
                  ({profile.skills?.length || 0})
                </span>
              </div>
            </div>

            {/* Skills List */}
            <div className="flex flex-wrap gap-2">
              {profile.skills && profile.skills.length > 0 ? (
                profile.skills.map((skill) => (
                  <span
                    key={skill}
                    className="inline-flex items-center gap-1.5 pl-3 pr-1.5 py-1 text-xs rounded-lg font-medium border border-slate-200 bg-slate-50 text-slate-800 shadow-xs hover:border-slate-300 transition-all"
                  >
                    <span>{skill}</span>
                    <button
                      onClick={() => handleRemoveSkill(skill)}
                      disabled={saving}
                      aria-label={`Remove skill ${skill}`}
                      className="p-1 -mr-0.5 rounded hover:bg-slate-200 text-slate-400 hover:text-slate-700 transition-colors inline-flex items-center justify-center"
                      title={`Remove ${skill}`}
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </span>
                ))
              ) : (
                <p className="text-xs text-slate-400">No skills configured. Add skills below.</p>
              )}
            </div>

            {/* Add Skill Input */}
            <div className="flex items-center gap-2 pt-2 max-w-md">
              <label htmlFor="skill-input" className="sr-only">
                Add skill
              </label>
              <input
                id="skill-input"
                type="text"
                value={newSkill}
                onChange={(e) => setNewSkill(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleAddSkill()}
                placeholder="e.g. Python, Docker, Next.js"
                className="flex-1 bg-white border border-slate-200 rounded-xl px-3.5 py-2 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-400/20 shadow-xs"
              />
              <button
                onClick={() => handleAddSkill()}
                disabled={saving || !newSkill.trim()}
                className="px-4 py-2 bg-slate-900 hover:bg-slate-800 active:scale-[0.98] disabled:opacity-50 text-white text-xs font-semibold rounded-xl flex items-center gap-1 transition-all shadow-xs"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add</span>
              </button>
            </div>
          </div>

          {/* Dedicated Target Ingestion Skills Card (Permanent In-Page Layout) */}
          <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-card-subtle space-y-5">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className="p-1.5 rounded-lg bg-blue-50 text-blue-600">
                    <Layers className="w-4 h-4" />
                  </span>
                  <h3 className="text-sm font-bold text-slate-900">Target Ingestion Skills</h3>
                </div>
                <p className="text-xs text-slate-500 mt-1">
                  External crawlers (LinkedIn, Naukri, Internshala) search for these exact keywords when you trigger &quot;Sync Feeds&quot; on the Jobs page.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => handleSaveSyncSkills()}
                  disabled={savingSyncSkills}
                  className="flex items-center gap-1.5 px-3.5 py-1.5 bg-slate-900 hover:bg-slate-800 active:scale-95 disabled:opacity-50 text-white text-xs font-semibold rounded-xl shadow-xs transition-all cursor-pointer"
                >
                  {savingSyncSkills ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Saving...</span>
                    </>
                  ) : syncSkillsSavedToast ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-emerald-400" />
                      <span>Saved!</span>
                    </>
                  ) : (
                    <>
                      <Bookmark className="w-3.5 h-3.5" />
                      <span>Save Sync Skills</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Profile Suggestions Chips */}
            {profile?.skills && profile.skills.length > 0 && (
              <div className="pt-1">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-amber-500" />
                    Suggested from your profile (click to toggle)
                  </span>
                  <button
                    type="button"
                    onClick={handleResetSyncSkillsToTop5}
                    className="text-[11px] text-blue-600 hover:text-blue-700 font-medium cursor-pointer"
                  >
                    Reset to top 5
                  </button>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {profile.skills.slice(0, 10).map((skill) => {
                    const isSelected = syncSkills.some(
                      (s) => s.toLowerCase() === skill.toLowerCase()
                    );
                    return (
                      <button
                        key={skill}
                        type="button"
                        onClick={() => toggleSyncSkill(skill)}
                        className={`px-3 py-1 rounded-full text-xs font-medium transition-all active:scale-95 cursor-pointer border ${
                          isSelected
                            ? "bg-blue-500/10 text-blue-700 border-blue-200 ring-1 ring-blue-400/20"
                            : "bg-slate-50 text-slate-600 border-slate-200 hover:bg-slate-100 hover:border-slate-300"
                        }`}
                      >
                        {isSelected ? "✓ " : "+ "}
                        {skill}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Active Target Skills Box */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                  Active crawl targets ({syncSkills.length})
                </span>
                {syncSkills.length > 0 && (
                  <button
                    type="button"
                    onClick={() => setSyncSkills([])}
                    className="text-[11px] text-slate-400 hover:text-slate-600 cursor-pointer"
                  >
                    Clear all
                  </button>
                )}
              </div>

              <div className="min-h-[56px] p-2.5 rounded-xl border border-slate-200 bg-slate-50/50 flex flex-wrap gap-1.5 items-center">
                {syncSkills.length === 0 ? (
                  <span className="text-xs text-slate-400 italic px-1">
                    No custom target skills configured. Ingestion crawler will fall back to your top 5 profile skills.
                  </span>
                ) : (
                  syncSkills.map((skill) => (
                    <span
                      key={skill}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-white border border-slate-200 text-slate-800 text-xs font-medium rounded-lg shadow-2xs"
                    >
                      {skill}
                      <button
                        type="button"
                        onClick={() => handleRemoveSyncSkill(skill)}
                        className="text-slate-400 hover:text-rose-600 transition-colors cursor-pointer"
                        title={`Remove ${skill}`}
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </span>
                  ))
                )}
              </div>
            </div>

            {/* Add custom skill input */}
            <div className="flex items-center gap-2 max-w-md">
              <label htmlFor="sync-skill-input" className="sr-only">
                Add target ingestion skill
              </label>
              <input
                id="sync-skill-input"
                type="text"
                value={newSyncSkillInput}
                onChange={(e) => setNewSyncSkillInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === ",") {
                    e.preventDefault();
                    handleAddCustomSyncSkill();
                  }
                }}
                placeholder="Add another skill (e.g. Next.js, Go, Docker)..."
                className="flex-1 bg-white border border-slate-200 rounded-xl px-3.5 py-2 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 shadow-xs"
              />
              <button
                type="button"
                onClick={handleAddCustomSyncSkill}
                disabled={!newSyncSkillInput.trim()}
                className="px-3.5 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 disabled:opacity-40 rounded-xl text-xs font-medium transition-all active:scale-95 cursor-pointer flex items-center gap-1 shadow-2xs"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add</span>
              </button>
            </div>
          </div>

          {/* Highlighted Projects */}
          {profile.projects && profile.projects.length > 0 && (
            <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-card-subtle space-y-4">
              <h3 className="text-sm font-bold text-slate-900">Highlighted Projects</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {profile.projects.map((proj, idx) => (
                  <div key={idx} className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
                    <p className="text-sm font-semibold text-emerald-700">{proj.title || "Project"}</p>
                    <p className="text-xs text-slate-600 leading-relaxed">{proj.description}</p>
                    {proj.technologies && proj.technologies.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 pt-1">
                        {proj.technologies.map((t) => (
                          <span
                            key={t}
                            className="px-2 py-0.5 bg-white text-slate-600 text-[10px] rounded border border-slate-200 font-medium shadow-xs"
                          >
                            {t}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* Confirmation Modal for Reset to Resume */}
      {showResetConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center gap-3 text-amber-600">
              <div className="p-2 rounded-xl bg-amber-50 border border-amber-200">
                <AlertTriangle className="w-5 h-5 text-amber-600" />
              </div>
              <div>
                <h4 className="text-sm font-bold text-slate-900">Reset Target Roles?</h4>
                <p className="text-xs text-slate-500">This will overwrite your custom target roles.</p>
              </div>
            </div>

            <p className="text-xs text-slate-600 leading-relaxed">
              Your active search scope will be restored to the roles originally extracted from your resume. Any manual role additions will be removed.
            </p>

            <div className="flex items-center justify-end gap-2.5 pt-2">
              <button
                onClick={() => setShowResetConfirm(false)}
                disabled={saving}
                className="px-3.5 py-2 text-xs font-semibold text-slate-600 hover:text-slate-900 rounded-xl hover:bg-slate-100 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmResetRoles}
                disabled={saving}
                className="px-4 py-2 text-xs font-semibold text-white bg-amber-600 hover:bg-amber-500 active:scale-[0.98] rounded-xl shadow-xs transition-all flex items-center gap-1.5"
              >
                {saving && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                <span>Confirm Reset</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

