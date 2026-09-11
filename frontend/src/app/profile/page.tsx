"use client";

import { useEffect, useState } from "react";
import { User, ShieldAlert, Sparkles, Plus, X, RotateCcw } from "lucide-react";

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
  manual_overrides: Record<string, boolean>;
}

export default function ProfilePage() {
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [newExcludedRole, setNewExcludedRole] = useState("");
  const [newTargetRole, setNewTargetRole] = useState("");

  const fetchProfile = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/v1/profile");
      if (res.ok) {
        const data = await res.json();
        setProfile(data);
      }
    } catch {
      // Backend offline
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProfile();
  }, []);

  const handleAddTargetRole = async (customRole?: string) => {
    const roleToAdd = (customRole || newTargetRole).trim();
    if (!roleToAdd || !profile) return;
    if (profile.target_roles.includes(roleToAdd)) return;

    setSaving(true);
    const updatedTarget = [...profile.target_roles, roleToAdd];

    try {
      const res = await fetch("http://localhost:8000/api/v1/profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_roles: updatedTarget }),
      });
      if (res.ok) {
        const data = await res.json();
        setProfile(data);
        setNewTargetRole("");
      }
    } finally {
      setSaving(false);
    }
  };

  const handleRemoveTargetRole = async (roleToRemove: string) => {
    if (!profile) return;
    setSaving(true);
    const updatedTarget = profile.target_roles.filter((r) => r !== roleToRemove);

    try {
      const res = await fetch("http://localhost:8000/api/v1/profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_roles: updatedTarget }),
      });
      if (res.ok) {
        const data = await res.json();
        setProfile(data);
      }
    } finally {
      setSaving(false);
    }
  };

  const handleResetToResumeRoles = async () => {
    if (!profile) return;
    setSaving(true);
    try {
      const resResume = await fetch("http://localhost:8000/api/v1/resumes/active");
      let extractedRoles = ["Full Stack Developer", "Backend Developer", "AI Engineer"];
      if (resResume.ok) {
        const resumeData = await resResume.json();
        if (resumeData?.extracted_data?.target_roles?.length) {
          extractedRoles = resumeData.extracted_data.target_roles;
        }
      }
      const res = await fetch("http://localhost:8000/api/v1/profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_roles: extractedRoles }),
      });
      if (res.ok) {
        const data = await res.json();
        setProfile(data);
      }
    } finally {
      setSaving(false);
    }
  };

  const handleAddExcludedRole = async () => {
    if (!newExcludedRole.trim() || !profile) return;
    const roleToAdd = newExcludedRole.trim();
    if (profile.excluded_roles.includes(roleToAdd)) return;

    setSaving(true);
    const updatedExcluded = [...profile.excluded_roles, roleToAdd];

    try {
      const res = await fetch("http://localhost:8000/api/v1/profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ excluded_roles: updatedExcluded }),
      });
      if (res.ok) {
        const data = await res.json();
        setProfile(data);
        setNewExcludedRole("");
      }
    } finally {
      setSaving(false);
    }
  };

  const handleRemoveExcludedRole = async (roleToRemove: string) => {
    if (!profile) return;
    setSaving(true);
    const updatedExcluded = profile.excluded_roles.filter((r) => r !== roleToRemove);

    try {
      const res = await fetch("http://localhost:8000/api/v1/profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ excluded_roles: updatedExcluded }),
      });
      if (res.ok) {
        const data = await res.json();
        setProfile(data);
      }
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="p-12 text-center text-gray-500">Loading candidate profile...</div>;
  }

  if (!profile) {
    return (
      <div className="rounded-xl border border-dashed border-gray-800 p-12 text-center bg-gray-950/40">
        <User className="w-8 h-8 text-gray-500 mx-auto mb-2" />
        <p className="text-sm text-gray-400">No profile found. Please upload a resume first.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-16">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-white/[0.07]">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              CANDIDATE INTELLIGENCE
            </span>
            <span className="text-xs text-zinc-500">·</span>
            <span className="text-xs text-zinc-400 font-mono">
              {profile.experience_level} ({profile.experience_years}y Exp)
            </span>
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-zinc-100">Candidate Profile</h2>
          <p className="text-xs text-zinc-400">
            Structured candidate intelligence extracted from your resume with manual overrides.
          </p>
        </div>
      </div>

      {/* Target & Excluded Roles */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Target Roles Card */}
        <div className="p-6 rounded-2xl bg-obsidian-900/60 border border-white/[0.08] shadow-surface-inset space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-emerald-400 font-semibold text-sm">
              <Sparkles className="w-4 h-4" />
              <span>Target Roles (Active Search Scope)</span>
            </div>
            <button
              onClick={handleResetToResumeRoles}
              disabled={saving}
              className="text-xs text-zinc-400 hover:text-emerald-400 flex items-center gap-1 transition-colors"
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
                  className="flex items-center gap-1.5 px-3 py-1 bg-emerald-500/10 border border-emerald-500/25 text-emerald-300 text-xs rounded-lg font-medium"
                >
                  <span>{role}</span>
                  <button
                    onClick={() => handleRemoveTargetRole(role)}
                    disabled={saving}
                    className="hover:text-emerald-100 p-0.5 rounded"
                    title={`Remove ${role}`}
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))
            ) : (
              <p className="text-xs text-amber-400">No target roles active. Add at least one.</p>
            )}
          </div>

          <div className="flex items-center gap-2 pt-2">
            <input
              type="text"
              value={newTargetRole}
              onChange={(e) => setNewTargetRole(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAddTargetRole()}
              placeholder="e.g. Full Stack Developer, AI Engineer"
              className="flex-1 bg-obsidian-950 border border-white/[0.08] rounded-xl px-3 py-2 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-emerald-500/40"
            />
            <button
              onClick={() => handleAddTargetRole()}
              disabled={saving || !newTargetRole.trim()}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 active:scale-[0.98] disabled:opacity-50 text-white text-xs font-semibold rounded-xl flex items-center gap-1 transition-all shadow-sm"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Add</span>
            </button>
          </div>

          {/* Quick Suggestions */}
          <div className="flex flex-wrap items-center gap-1.5 pt-1">
            <span className="text-[10px] text-zinc-500 font-semibold uppercase tracking-wider">Quick add:</span>
            {["Full Stack Developer", "Backend Developer", "Frontend Developer", "AI Engineer", "Python Developer", "Node.js Developer"].map(
              (suggested) =>
                !profile.target_roles.includes(suggested) && (
                  <button
                    key={suggested}
                    onClick={() => handleAddTargetRole(suggested)}
                    disabled={saving}
                    className="px-2 py-0.5 rounded-md bg-obsidian-950 hover:bg-white/[0.06] text-[10px] text-zinc-400 hover:text-emerald-300 border border-white/[0.06] transition-colors"
                  >
                    + {suggested}
                  </button>
                )
            )}
          </div>

          <p className="text-[11px] text-zinc-500">
            Agent dynamically expands search queries around these target roles.
          </p>
        </div>

        {/* Excluded Roles Card */}
        <div className="p-6 rounded-2xl bg-obsidian-900/60 border border-white/[0.08] shadow-surface-inset space-y-4">
          <div className="flex items-center gap-2 text-rose-400 font-semibold text-sm">
            <ShieldAlert className="w-4 h-4" />
            <span>Explicit Excluded Roles (Never Recommend)</span>
          </div>

          <div className="flex flex-wrap gap-2">
            {profile.excluded_roles.length > 0 ? (
              profile.excluded_roles.map((role) => (
                <span
                  key={role}
                  className="flex items-center gap-1.5 px-3 py-1 bg-rose-500/10 border border-rose-500/25 text-rose-300 text-xs rounded-lg font-medium"
                >
                  <span>{role}</span>
                  <button
                    onClick={() => handleRemoveExcludedRole(role)}
                    disabled={saving}
                    className="hover:text-rose-100 p-0.5 rounded"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))
            ) : (
              <p className="text-xs text-zinc-500">No excluded roles configured.</p>
            )}
          </div>

          <div className="flex items-center gap-2 pt-2">
            <input
              type="text"
              value={newExcludedRole}
              onChange={(e) => setNewExcludedRole(e.target.value)}
              placeholder="e.g. Data Analyst, QA, Sales"
              className="flex-1 bg-obsidian-950 border border-white/[0.08] rounded-xl px-3 py-2 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-rose-500/40"
              onKeyDown={(e) => e.key === "Enter" && handleAddExcludedRole()}
            />
            <button
              onClick={handleAddExcludedRole}
              disabled={saving || !newExcludedRole.trim()}
              className="flex items-center gap-1 px-4 py-2 bg-rose-600 hover:bg-rose-500 active:scale-[0.98] text-white rounded-xl text-xs font-semibold transition-all disabled:opacity-50 shadow-sm"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Exclude</span>
            </button>
          </div>

          <p className="text-[11px] text-zinc-500">
            Jobs matching excluded titles or keywords are filtered automatically.
          </p>
        </div>
      </div>

      {/* Skills Taxonomy */}
      <div className="p-6 rounded-2xl bg-obsidian-900/60 border border-white/[0.08] shadow-surface-inset space-y-5">
        <h3 className="text-sm font-semibold text-zinc-200">Extracted & Canonicalized Skills</h3>

        <div className="space-y-4">
          <div>
            <p className="text-xs text-zinc-400 font-medium mb-2">Programming Languages</p>
            <div className="flex flex-wrap gap-1.5">
              {profile.programming_languages.map((item) => (
                <span
                  key={item}
                  className="px-2.5 py-1 bg-obsidian-950 border border-white/[0.06] text-zinc-300 text-xs rounded-lg"
                >
                  {item}
                </span>
              ))}
            </div>
          </div>

          <div>
            <p className="text-xs text-zinc-400 font-medium mb-2">Frameworks & Libraries</p>
            <div className="flex flex-wrap gap-1.5">
              {profile.frameworks.map((item) => (
                <span
                  key={item}
                  className="px-2.5 py-1 bg-obsidian-950 border border-white/[0.06] text-zinc-300 text-xs rounded-lg"
                >
                  {item}
                </span>
              ))}
            </div>
          </div>

          <div>
            <p className="text-xs text-zinc-400 font-medium mb-2">Databases</p>
            <div className="flex flex-wrap gap-1.5">
              {profile.databases.map((item) => (
                <span
                  key={item}
                  className="px-2.5 py-1 bg-obsidian-950 border border-white/[0.06] text-zinc-300 text-xs rounded-lg"
                >
                  {item}
                </span>
              ))}
            </div>
          </div>

          <div>
            <p className="text-xs text-zinc-400 font-medium mb-2">Cloud, Infrastructure & DevOps</p>
            <div className="flex flex-wrap gap-1.5">
              {profile.cloud.map((item) => (
                <span
                  key={item}
                  className="px-2.5 py-1 bg-obsidian-950 border border-white/[0.06] text-zinc-300 text-xs rounded-lg"
                >
                  {item}
                </span>
              ))}
            </div>
          </div>

          <div>
            <p className="text-xs text-zinc-400 font-medium mb-2">Tools & Platforms</p>
            <div className="flex flex-wrap gap-1.5">
              {profile.tools.map((item) => (
                <span
                  key={item}
                  className="px-2.5 py-1 bg-obsidian-950 border border-white/[0.06] text-zinc-300 text-xs rounded-lg"
                >
                  {item}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Projects */}
      {profile.projects && profile.projects.length > 0 && (
        <div className="p-6 rounded-2xl bg-obsidian-900/60 border border-white/[0.08] shadow-surface-inset space-y-4">
          <h3 className="text-sm font-semibold text-zinc-200">Highlighted Projects</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {profile.projects.map((proj, idx) => (
              <div key={idx} className="p-4 rounded-xl bg-obsidian-950 border border-white/[0.06] space-y-2">
                <p className="text-sm font-semibold text-emerald-400">{proj.title || "Project"}</p>
                <p className="text-xs text-zinc-300 leading-relaxed">{proj.description}</p>
                {proj.technologies && proj.technologies.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {proj.technologies.map((t) => (
                      <span key={t} className="px-2 py-0.5 bg-white/[0.04] text-zinc-400 text-[10px] rounded border border-white/[0.04]">
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
    </div>
  );
}
