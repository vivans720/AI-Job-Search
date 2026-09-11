"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  Sparkles,
  ArrowRight,
  ArrowLeft,
  CheckCircle2,
  AlertCircle,
  Briefcase,
  FileText,
  Sliders,
  Cpu,
  Layers,
  Rocket,
  Upload,
  RefreshCw,
  Plus,
  X,
  ShieldCheck,
  Check,
} from "lucide-react";
import { SyncProgressModal } from "@/components/SyncProgressModal";

interface ProfileState {
  experience_level: string;
  experience_years: number;
  target_roles: string[];
  skills: string[];
  preferred_locations: string[];
  remote_preference: boolean;
  internship_allowed: boolean;
  fulltime_allowed: boolean;
  minimum_salary_lpa: number | null;
}

interface PreferencesState {
  freshness_hours: number;
  experience_max_years: number;
  excluded_companies: string[];
  priority_companies: string[];
  match_threshold: number;
}

const STEPS = [
  { id: 1, name: "Welcome", icon: Sparkles },
  { id: 2, name: "Profile", icon: Briefcase },
  { id: 3, name: "Resume", icon: FileText },
  { id: 4, name: "Preferences", icon: Sliders },
  { id: 5, name: "AI Provider", icon: Cpu },
  { id: 6, name: "Job Sources", icon: Layers },
  { id: 7, name: "Ready & Sync", icon: Rocket },
];

export default function SetupWizardPage() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(1);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Step 2: Profile state
  const [profile, setProfile] = useState<ProfileState>({
    experience_level: "fresher",
    experience_years: 0,
    target_roles: ["Backend Engineer", "Software Engineer", "Python Developer"],
    skills: ["Python", "FastAPI", "PostgreSQL", "Docker", "Git"],
    preferred_locations: ["Bengaluru", "Remote", "Hyderabad"],
    remote_preference: true,
    internship_allowed: true,
    fulltime_allowed: true,
    minimum_salary_lpa: null,
  });
  const [roleInput, setRoleInput] = useState("");
  const [skillInput, setSkillInput] = useState("");
  const [locInput, setLocInput] = useState("");

  // Step 3: Resume state
  const [uploadingResume, setUploadingResume] = useState(false);
  const [uploadedResumeName, setUploadedResumeName] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Step 4: Preferences state
  const [preferences, setPreferences] = useState<PreferencesState>({
    freshness_hours: 24,
    experience_max_years: 2,
    excluded_companies: [],
    priority_companies: [],
    match_threshold: 60,
  });
  const [excludedInput, setExcludedInput] = useState("");

  // Step 5: AI Provider state
  const [selectedProvider, setSelectedProvider] = useState<string>("ollama");
  const [aiModel, setAiModel] = useState<string>("qwen2.5:7b");
  const [aiBaseUrl, setAiBaseUrl] = useState<string>("");
  const [aiApiKey, setAiApiKey] = useState<string>("");
  const [testingAi, setTestingAi] = useState(false);
  const [aiTestResult, setAiTestResult] = useState<{
    status: "success" | "error";
    message: string;
  } | null>(null);

  // Step 6: Sources state
  const [sources, setSources] = useState<{ [key: string]: boolean }>({
    linkedin: true,
    naukri: true,
    internshala: true,
  });

  // Step 7: Sync state
  const [isSyncModalOpen, setIsSyncModalOpen] = useState(false);

  useEffect(() => {
    async function loadInitialData() {
      try {
        const [prefRes, profRes] = await Promise.all([
          fetch("http://localhost:8000/api/v1/preferences"),
          fetch("http://localhost:8000/api/v1/profile"),
        ]);

        if (prefRes.ok) {
          const prefData = await prefRes.json();
          setPreferences({
            freshness_hours: prefData.freshness_hours || 24,
            experience_max_years: prefData.experience_max_years || 2,
            excluded_companies: prefData.excluded_companies || [],
            priority_companies: prefData.priority_companies || [],
            match_threshold: prefData.match_threshold || 60,
          });
          if (prefData.ai_provider) setSelectedProvider(prefData.ai_provider);
          if (prefData.ai_model) setAiModel(prefData.ai_model);
          if (prefData.ai_base_url) setAiBaseUrl(prefData.ai_base_url);
        }

        if (profRes.ok) {
          const profData = await profRes.json();
          setProfile((prev) => ({
            ...prev,
            experience_level: profData.experience_level || prev.experience_level,
            experience_years: profData.experience_years ?? prev.experience_years,
            target_roles: profData.target_roles?.length ? profData.target_roles : prev.target_roles,
            skills: profData.skills?.length ? profData.skills : prev.skills,
            preferred_locations: profData.preferred_locations?.length ? profData.preferred_locations : prev.preferred_locations,
            remote_preference: profData.remote_preference ?? prev.remote_preference,
            internship_allowed: profData.internship_allowed ?? prev.internship_allowed,
            fulltime_allowed: profData.fulltime_allowed ?? prev.fulltime_allowed,
            minimum_salary_lpa: profData.minimum_salary_lpa ?? prev.minimum_salary_lpa,
          }));
        }
      } catch (err) {
        console.error("Initial load failed:", err);
      } finally {
        setLoading(false);
      }
    }
    loadInitialData();
  }, []);

  const handleAddTargetRole = () => {
    const role = roleInput.trim();
    if (role && !profile.target_roles.includes(role)) {
      setProfile((prev) => ({ ...prev, target_roles: [...prev.target_roles, role] }));
      setRoleInput("");
    }
  };

  const handleRemoveTargetRole = (role: string) => {
    setProfile((prev) => ({
      ...prev,
      target_roles: prev.target_roles.filter((r) => r !== role),
    }));
  };

  const handleAddSkill = () => {
    const s = skillInput.trim();
    if (s && !profile.skills.includes(s)) {
      setProfile((prev) => ({ ...prev, skills: [...prev.skills, s] }));
      setSkillInput("");
    }
  };

  const handleRemoveSkill = (skill: string) => {
    setProfile((prev) => ({
      ...prev,
      skills: prev.skills.filter((s) => s !== skill),
    }));
  };

  const handleAddLocation = () => {
    const loc = locInput.trim();
    if (loc && !profile.preferred_locations.includes(loc)) {
      setProfile((prev) => ({
        ...prev,
        preferred_locations: [...prev.preferred_locations, loc],
      }));
      setLocInput("");
    }
  };

  const handleRemoveLocation = (loc: string) => {
    setProfile((prev) => ({
      ...prev,
      preferred_locations: prev.preferred_locations.filter((l) => l !== loc),
    }));
  };

  const handleAddExcludedCompany = () => {
    const c = excludedInput.trim();
    if (c && !preferences.excluded_companies.includes(c)) {
      setPreferences((prev) => ({
        ...prev,
        excluded_companies: [...prev.excluded_companies, c],
      }));
      setExcludedInput("");
    }
  };

  const handleRemoveExcludedCompany = (c: string) => {
    setPreferences((prev) => ({
      ...prev,
      excluded_companies: prev.excluded_companies.filter((x) => x !== c),
    }));
  };

  const handleResumeUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadingResume(true);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("http://localhost:8000/api/v1/resumes", {
        method: "POST",
        body: formData,
      });

      if (res.ok) {
        setUploadedResumeName(file.name);
        const profRes = await fetch("http://localhost:8000/api/v1/profile");
        if (profRes.ok) {
          const profData = await profRes.json();
          setProfile((prev) => ({
            ...prev,
            experience_level: profData.experience_level || prev.experience_level,
            experience_years: profData.experience_years ?? prev.experience_years,
            target_roles: profData.target_roles?.length ? profData.target_roles : prev.target_roles,
            skills: profData.skills?.length ? profData.skills : prev.skills,
            preferred_locations: profData.preferred_locations?.length ? profData.preferred_locations : prev.preferred_locations,
          }));
        }
      }
    } catch (err) {
      console.error("Resume upload error:", err);
    } finally {
      setUploadingResume(false);
    }
  };

  const handleTestAiConnection = async () => {
    setTestingAi(true);
    setAiTestResult(null);

    try {
      const res = await fetch("http://localhost:8000/api/v1/ai/test-connection", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: selectedProvider,
          model: aiModel || undefined,
          base_url: aiBaseUrl || undefined,
          api_key: aiApiKey || undefined,
        }),
      });

      const data = await res.json();
      if (res.ok && data.status === "ok") {
        setAiTestResult({
          status: "success",
          message: `Connected successfully! Provider: ${data.provider} (${data.model})`,
        });
      } else {
        setAiTestResult({
          status: "error",
          message: data.message || "Failed to reach AI provider model endpoint.",
        });
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Network connection failure.";
      setAiTestResult({
        status: "error",
        message: msg,
      });
    } finally {
      setTestingAi(false);
    }
  };

  const handleNext = async () => {
    if (currentStep === 2) {
      setSaving(true);
      try {
        await fetch("http://localhost:8000/api/v1/profile", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(profile),
        });
      } catch (err) {
        console.error("Profile save error:", err);
      } finally {
        setSaving(false);
      }
    } else if (currentStep === 4) {
      setSaving(true);
      try {
        await fetch("http://localhost:8000/api/v1/preferences", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(preferences),
        });
      } catch (err) {
        console.error("Preferences save error:", err);
      } finally {
        setSaving(false);
      }
    } else if (currentStep === 5) {
      setSaving(true);
      try {
        await fetch("http://localhost:8000/api/v1/preferences", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            ai_provider: selectedProvider,
            ai_model: aiModel,
            ai_base_url: aiBaseUrl,
            ai_api_key: aiApiKey || undefined,
          }),
        });
      } catch (err) {
        console.error("AI Preferences save error:", err);
      } finally {
        setSaving(false);
      }
    }

    if (currentStep < STEPS.length) {
      setCurrentStep((s) => s + 1);
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep((s) => s - 1);
    }
  };

  const handleFinishAndSync = async () => {
    setSaving(true);
    try {
      await fetch("http://localhost:8000/api/v1/preferences/complete-setup", {
        method: "POST",
      });
      setIsSyncModalOpen(true);
    } catch (err) {
      console.error("Complete setup error:", err);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-obsidian-950 flex flex-col items-center justify-center p-6 text-zinc-300">
        <RefreshCw className="w-6 h-6 animate-spin text-emerald-400" />
        <p className="text-xs text-zinc-500 mt-3 font-mono">Loading setup wizard...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-obsidian-950 text-zinc-100 flex flex-col items-center p-4 sm:p-8">
      {/* Top Header */}
      <header className="w-full max-w-4xl flex items-center justify-between py-4 border-b border-white/[0.08] mb-8">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shadow-sm shadow-emerald-950">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-zinc-100 tracking-tight">AI Job Agent Setup</h1>
            <p className="text-xs text-zinc-500">Candidate profile & intelligence configuration</p>
          </div>
        </div>
        <div className="text-xs font-mono text-zinc-400 px-3 py-1 rounded-full bg-white/[0.04] border border-white/[0.08]">
          Step {currentStep} of {STEPS.length}
        </div>
      </header>

      {/* Stepper Indicator */}
      <div className="w-full max-w-4xl mb-8 overflow-x-auto pb-2">
        <div className="flex items-center justify-between min-w-[620px] gap-2">
          {STEPS.map((step) => {
            const isCompleted = currentStep > step.id;
            const isCurrent = currentStep === step.id;

            return (
              <div
                key={step.id}
                onClick={() => isCompleted && setCurrentStep(step.id)}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                  isCurrent
                    ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                    : isCompleted
                    ? "bg-white/[0.04] text-zinc-300 border border-white/[0.06] cursor-pointer hover:bg-white/[0.08]"
                    : "text-zinc-600 opacity-60"
                }`}
              >
                <div
                  className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] ${
                    isCompleted
                      ? "bg-emerald-500/20 text-emerald-400"
                      : isCurrent
                      ? "bg-emerald-500 text-obsidian-950 font-bold"
                      : "bg-zinc-800 text-zinc-500"
                  }`}
                >
                  {isCompleted ? <Check className="w-3 h-3" /> : step.id}
                </div>
                <span>{step.name}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Wizard Content Card */}
      <main className="w-full max-w-4xl bg-obsidian-900/60 border border-white/[0.08] rounded-2xl p-6 sm:p-8 backdrop-blur-xl shadow-2xl flex-1 flex flex-col justify-between min-h-[460px]">
        {/* STEP 1: WELCOME */}
        {currentStep === 1 && (
          <div className="space-y-6 max-w-2xl py-4">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs font-medium">
              <ShieldCheck className="w-3.5 h-3.5" />
              Recall-First Job Intelligence Platform
            </div>

            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
              Welcome to your automated, deterministic job radar.
            </h2>

            <p className="text-sm text-zinc-400 leading-relaxed">
              This system crawls live Indian job boards (LinkedIn, Naukri, Internshala), applies
              anti-inflation filtering, and scores opportunities deterministically against your
              structured profile and skills.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
              <div className="p-4 rounded-xl bg-obsidian-950/60 border border-white/[0.06] space-y-2">
                <div className="text-emerald-400 font-semibold text-xs flex items-center gap-2">
                  <Cpu className="w-4 h-4" /> Pluggable AI Core
                </div>
                <p className="text-xs text-zinc-400">
                  Runs with Ollama locally for zero cloud dependency, or switches to Gemini/OpenAI models.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-obsidian-950/60 border border-white/[0.06] space-y-2">
                <div className="text-emerald-400 font-semibold text-xs flex items-center gap-2">
                  <Sliders className="w-4 h-4" /> Deterministic Matching
                </div>
                <p className="text-xs text-zinc-400">
                  Strict required/preferred skill gates, experience thresholds, and explainable scoring.
                </p>
              </div>
            </div>

            <p className="text-xs text-zinc-500 pt-2">
              We will guide you through setting up your profile, resume, AI model, and job board sources.
            </p>
          </div>
        )}

        {/* STEP 2: PROFILE */}
        {currentStep === 2 && (
          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-semibold text-white">Candidate Profile</h2>
              <p className="text-xs text-zinc-400 mt-1">
                Define your target roles, experience level, and key core skills.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              <div>
                <label className="text-xs font-medium text-zinc-300 block mb-1.5">
                  Experience Level
                </label>
                <select
                  value={profile.experience_level}
                  onChange={(e) =>
                    setProfile((p) => ({ ...p, experience_level: e.target.value }))
                  }
                  className="w-full bg-obsidian-950 border border-white/[0.1] rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-emerald-500"
                >
                  <option value="fresher">Fresher (0 years)</option>
                  <option value="junior">Junior (1-2 years)</option>
                  <option value="mid">Mid-Level (3-5 years)</option>
                  <option value="senior">Senior (5+ years)</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-medium text-zinc-300 block mb-1.5">
                  Years of Experience
                </label>
                <input
                  type="number"
                  min="0"
                  max="30"
                  value={profile.experience_years}
                  onChange={(e) =>
                    setProfile((p) => ({ ...p, experience_years: parseInt(e.target.value) || 0 }))
                  }
                  className="w-full bg-obsidian-950 border border-white/[0.1] rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-emerald-500"
                />
              </div>
            </div>

            {/* Target Roles */}
            <div>
              <label className="text-xs font-medium text-zinc-300 block mb-1.5">
                Target Roles (Used for query generation & matching)
              </label>
              <div className="flex gap-2 mb-2">
                <input
                  type="text"
                  placeholder="e.g. Backend Developer"
                  value={roleInput}
                  onChange={(e) => setRoleInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), handleAddTargetRole())}
                  className="flex-1 bg-obsidian-950 border border-white/[0.1] rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-emerald-500"
                />
                <button
                  type="button"
                  onClick={handleAddTargetRole}
                  className="px-3 py-2 rounded-lg bg-white/[0.08] hover:bg-white/[0.12] text-xs font-medium text-zinc-200"
                >
                  <Plus className="w-3.5 h-3.5" />
                </button>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {profile.target_roles.map((r) => (
                  <span
                    key={r}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs bg-emerald-500/10 text-emerald-300 border border-emerald-500/20"
                  >
                    {r}
                    <button
                      type="button"
                      onClick={() => handleRemoveTargetRole(r)}
                      className="hover:text-emerald-100"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
              </div>
            </div>

            {/* Core Skills */}
            <div>
              <label className="text-xs font-medium text-zinc-300 block mb-1.5">
                Key Technical Skills
              </label>
              <div className="flex gap-2 mb-2">
                <input
                  type="text"
                  placeholder="e.g. FastAPI, PostgreSQL, AWS"
                  value={skillInput}
                  onChange={(e) => setSkillInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), handleAddSkill())}
                  className="flex-1 bg-obsidian-950 border border-white/[0.1] rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-emerald-500"
                />
                <button
                  type="button"
                  onClick={handleAddSkill}
                  className="px-3 py-2 rounded-lg bg-white/[0.08] hover:bg-white/[0.12] text-xs font-medium text-zinc-200"
                >
                  <Plus className="w-3.5 h-3.5" />
                </button>
              </div>
              <div className="flex flex-wrap gap-1.5 max-h-28 overflow-y-auto pr-1">
                {profile.skills.map((s) => (
                  <span
                    key={s}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs bg-white/[0.06] text-zinc-300 border border-white/[0.08]"
                  >
                    {s}
                    <button
                      type="button"
                      onClick={() => handleRemoveSkill(s)}
                      className="hover:text-zinc-100"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
              </div>
            </div>

            {/* Location & Remote */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
              <div>
                <label className="text-xs font-medium text-zinc-300 block mb-1.5">
                  Preferred Locations
                </label>
                <div className="flex gap-2 mb-2">
                  <input
                    type="text"
                    placeholder="e.g. Bengaluru, Remote"
                    value={locInput}
                    onChange={(e) => setLocInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), handleAddLocation())}
                    className="flex-1 bg-obsidian-950 border border-white/[0.1] rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-emerald-500"
                  />
                  <button
                    type="button"
                    onClick={handleAddLocation}
                    className="px-3 py-2 rounded-lg bg-white/[0.08] hover:bg-white/[0.12] text-xs font-medium text-zinc-200"
                  >
                    <Plus className="w-3.5 h-3.5" />
                  </button>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {profile.preferred_locations.map((loc) => (
                    <span
                      key={loc}
                      className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] bg-white/[0.04] text-zinc-300 border border-white/[0.08]"
                    >
                      {loc}
                      <button
                        type="button"
                        onClick={() => handleRemoveLocation(loc)}
                        className="hover:text-zinc-100"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </span>
                  ))}
                </div>
              </div>

              <div className="flex flex-col justify-center space-y-3 bg-obsidian-950/60 p-3.5 rounded-xl border border-white/[0.06]">
                <label className="flex items-center gap-2 text-xs text-zinc-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={profile.remote_preference}
                    onChange={(e) =>
                      setProfile((p) => ({ ...p, remote_preference: e.target.checked }))
                    }
                    className="rounded border-zinc-700 text-emerald-500 focus:ring-emerald-500"
                  />
                  <span>Allow Remote Opportunities</span>
                </label>

                <label className="flex items-center gap-2 text-xs text-zinc-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={profile.internship_allowed}
                    onChange={(e) =>
                      setProfile((p) => ({ ...p, internship_allowed: e.target.checked }))
                    }
                    className="rounded border-zinc-700 text-emerald-500 focus:ring-emerald-500"
                  />
                  <span>Allow Internships / Apprenticeships</span>
                </label>
              </div>
            </div>
          </div>
        )}

        {/* STEP 3: RESUME */}
        {currentStep === 3 && (
          <div className="space-y-6 max-w-xl py-2">
            <div>
              <h2 className="text-lg font-semibold text-white">Upload Resume</h2>
              <p className="text-xs text-zinc-400 mt-1">
                Upload your resume (PDF/DOCX) to automatically enrich and verify your candidate profile.
              </p>
            </div>

            <div
              onClick={() => fileInputRef.current?.click()}
              className="border-2 border-dashed border-white/[0.12] hover:border-emerald-500/50 rounded-2xl p-8 flex flex-col items-center justify-center text-center cursor-pointer transition-all bg-obsidian-950/40 hover:bg-emerald-500/[0.02]"
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.doc"
                onChange={handleResumeUpload}
                className="hidden"
              />

              {uploadingResume ? (
                <div className="flex flex-col items-center gap-3">
                  <RefreshCw className="w-8 h-8 animate-spin text-emerald-400" />
                  <p className="text-xs text-zinc-300">Extracting profile with AI parser...</p>
                </div>
              ) : uploadedResumeName ? (
                <div className="flex flex-col items-center gap-3">
                  <CheckCircle2 className="w-8 h-8 text-emerald-400" />
                  <div>
                    <p className="text-xs font-semibold text-zinc-200">{uploadedResumeName}</p>
                    <p className="text-[11px] text-emerald-400 mt-1">
                      Resume successfully parsed and profile synced!
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      fileInputRef.current?.click();
                    }}
                    className="text-xs text-zinc-400 hover:text-zinc-200 underline mt-2"
                  >
                    Upload a different file
                  </button>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-3">
                  <div className="w-12 h-12 rounded-xl bg-white/[0.04] border border-white/[0.08] flex items-center justify-center text-zinc-400">
                    <Upload className="w-5 h-5" />
                  </div>
                  <div>
                    <p className="text-xs font-medium text-zinc-300">
                      Click to upload or drag & drop
                    </p>
                    <p className="text-[11px] text-zinc-500 mt-1">PDF or DOCX (up to 10MB)</p>
                  </div>
                </div>
              )}
            </div>

            <div className="p-3.5 rounded-xl bg-obsidian-950/80 border border-white/[0.06] text-xs text-zinc-400 space-y-1">
              <span className="text-zinc-200 font-medium">Privacy guarantee:</span>
              <p>
                Your resume is parsed locally or sent directly to your configured LLM. Data is saved
                only to your local database instance.
              </p>
            </div>
          </div>
        )}

        {/* STEP 4: PREFERENCES */}
        {currentStep === 4 && (
          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-semibold text-white">Search Preferences</h2>
              <p className="text-xs text-zinc-400 mt-1">
                Fine-tune anti-inflation freshness gates and company exclusions.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              <div>
                <label className="text-xs font-medium text-zinc-300 block mb-1.5">
                  Freshness Window (Hours)
                </label>
                <div className="flex items-center gap-3">
                  <input
                    type="number"
                    min="1"
                    max="168"
                    value={preferences.freshness_hours}
                    onChange={(e) =>
                      setPreferences((p) => ({
                        ...p,
                        freshness_hours: parseInt(e.target.value) || 24,
                      }))
                    }
                    className="w-28 bg-obsidian-950 border border-white/[0.1] rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-emerald-500"
                  />
                  <span className="text-xs text-zinc-500">
                    Default 24h for strict freshness
                  </span>
                </div>
              </div>

              <div>
                <label className="text-xs font-medium text-zinc-300 block mb-1.5">
                  Max Experience Cap (Years)
                </label>
                <div className="flex items-center gap-3">
                  <input
                    type="number"
                    min="0"
                    max="15"
                    value={preferences.experience_max_years}
                    onChange={(e) =>
                      setPreferences((p) => ({
                        ...p,
                        experience_max_years: parseInt(e.target.value) || 2,
                      }))
                    }
                    className="w-28 bg-obsidian-950 border border-white/[0.1] rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-emerald-500"
                  />
                  <span className="text-xs text-zinc-500">
                    Filters out bloated 3-5+ yr listings
                  </span>
                </div>
              </div>
            </div>

            {/* Match Threshold Slider */}
            <div>
              <div className="flex justify-between items-center mb-1.5">
                <label className="text-xs font-medium text-zinc-300">
                  Minimum Match Threshold
                </label>
                <span className="text-xs font-semibold text-emerald-400">
                  {preferences.match_threshold}%
                </span>
              </div>
              <input
                type="range"
                min="30"
                max="90"
                step="5"
                value={preferences.match_threshold}
                onChange={(e) =>
                  setPreferences((p) => ({
                    ...p,
                    match_threshold: parseInt(e.target.value),
                  }))
                }
                className="w-full accent-emerald-500"
              />
            </div>

            {/* Excluded Companies */}
            <div>
              <label className="text-xs font-medium text-zinc-300 block mb-1.5">
                Excluded Companies / Agencies
              </label>
              <div className="flex gap-2 mb-2">
                <input
                  type="text"
                  placeholder="e.g. Staffing Agency, Revature"
                  value={excludedInput}
                  onChange={(e) => setExcludedInput(e.target.value)}
                  onKeyDown={(e) =>
                    e.key === "Enter" && (e.preventDefault(), handleAddExcludedCompany())
                  }
                  className="flex-1 bg-obsidian-950 border border-white/[0.1] rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-emerald-500"
                />
                <button
                  type="button"
                  onClick={handleAddExcludedCompany}
                  className="px-3 py-2 rounded-lg bg-white/[0.08] hover:bg-white/[0.12] text-xs font-medium text-zinc-200"
                >
                  <Plus className="w-3.5 h-3.5" />
                </button>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {preferences.excluded_companies.map((c) => (
                  <span
                    key={c}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs bg-red-500/10 text-red-400 border border-red-500/20"
                  >
                    {c}
                    <button
                      type="button"
                      onClick={() => handleRemoveExcludedCompany(c)}
                      className="hover:text-red-200"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* STEP 5: AI PROVIDER */}
        {currentStep === 5 && (
          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-semibold text-white">AI Provider Configuration</h2>
              <p className="text-xs text-zinc-400 mt-1">
                Configure your LLM for skill normalization, extraction, and match reasoning.
              </p>
            </div>

            {/* Provider Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {[
                { id: "ollama", name: "Ollama", desc: "Local open-source (Recommended)", type: "local" },
                { id: "gemini", name: "Google Gemini", desc: "Fast cloud inference", type: "cloud" },
                { id: "openai", name: "OpenAI", desc: "GPT-4o mini cloud API", type: "cloud" },
              ].map((p) => {
                const isSelected = selectedProvider.toLowerCase() === p.id;
                return (
                  <div
                    key={p.id}
                    onClick={() => {
                      setSelectedProvider(p.id);
                      if (p.id === "ollama") setAiModel("qwen2.5:7b");
                      else if (p.id === "gemini") setAiModel("gemini-2.5-flash");
                      else if (p.id === "openai") setAiModel("gpt-4o-mini");
                    }}
                    className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                      isSelected
                        ? "bg-emerald-500/10 border-emerald-500/40 text-emerald-400"
                        : "bg-obsidian-950/60 border-white/[0.06] text-zinc-400 hover:border-white/[0.12]"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-semibold text-xs text-zinc-100">{p.name}</span>
                      <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-white/[0.06] text-zinc-400">
                        {p.type}
                      </span>
                    </div>
                    <p className="text-[11px] text-zinc-500">{p.desc}</p>
                  </div>
                );
              })}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-medium text-zinc-300 block mb-1.5">Model Name</label>
                <input
                  type="text"
                  value={aiModel}
                  onChange={(e) => setAiModel(e.target.value)}
                  placeholder="e.g. qwen2.5:7b or gpt-4o-mini"
                  className="w-full bg-obsidian-950 border border-white/[0.1] rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-emerald-500"
                />
              </div>

              {selectedProvider !== "ollama" ? (
                <div>
                  <label className="text-xs font-medium text-zinc-300 block mb-1.5">API Key</label>
                  <input
                    type="password"
                    value={aiApiKey}
                    onChange={(e) => setAiApiKey(e.target.value)}
                    placeholder="Enter API key"
                    className="w-full bg-obsidian-950 border border-white/[0.1] rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-emerald-500"
                  />
                </div>
              ) : (
                <div>
                  <label className="text-xs font-medium text-zinc-300 block mb-1.5">
                    Ollama Base URL
                  </label>
                  <input
                    type="text"
                    value={aiBaseUrl}
                    onChange={(e) => setAiBaseUrl(e.target.value)}
                    placeholder="http://localhost:11434 (default)"
                    className="w-full bg-obsidian-950 border border-white/[0.1] rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-emerald-500"
                  />
                </div>
              )}
            </div>

            {/* Test Connection Button & Status */}
            <div className="pt-2 flex flex-col sm:flex-row items-start sm:items-center gap-3">
              <button
                type="button"
                onClick={handleTestAiConnection}
                disabled={testingAi}
                className="px-4 py-2 rounded-lg bg-white/[0.08] hover:bg-white/[0.12] text-xs font-semibold text-zinc-200 flex items-center gap-2 border border-white/[0.08]"
              >
                {testingAi ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin text-emerald-400" />
                    <span>Verifying endpoint...</span>
                  </>
                ) : (
                  <>
                    <Cpu className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Test AI Connection</span>
                  </>
                )}
              </button>

              {aiTestResult && (
                <div
                  className={`text-xs px-3 py-1.5 rounded-lg flex items-center gap-2 ${
                    aiTestResult.status === "success"
                      ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                      : "bg-red-500/10 text-red-400 border border-red-500/20"
                  }`}
                >
                  {aiTestResult.status === "success" ? (
                    <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                  ) : (
                    <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                  )}
                  <span>{aiTestResult.message}</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* STEP 6: JOB SOURCES */}
        {currentStep === 6 && (
          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-semibold text-white">Job Sources</h2>
              <p className="text-xs text-zinc-400 mt-1">
                Select target discovery sources for automated synchronization.
              </p>
            </div>

            <div className="space-y-3">
              {[
                {
                  id: "linkedin",
                  name: "LinkedIn Jobs",
                  desc: "Public job postings API / crawl with strict freshness filters.",
                  tag: "High Volume",
                },
                {
                  id: "naukri",
                  name: "Naukri.com",
                  desc: "Leading Indian tech portal with rich role metadata and experience flags.",
                  tag: "India Tech",
                },
                {
                  id: "internshala",
                  name: "Internshala",
                  desc: "Early career tech internships, junior jobs, and entry-level positions.",
                  tag: "Early Career",
                },
              ].map((src) => {
                const isEnabled = sources[src.id] ?? true;
                return (
                  <div
                    key={src.id}
                    onClick={() => setSources((s) => ({ ...s, [src.id]: !isEnabled }))}
                    className={`p-4 rounded-xl border cursor-pointer transition-all flex items-center justify-between ${
                      isEnabled
                        ? "bg-emerald-500/[0.04] border-emerald-500/30 text-zinc-200"
                        : "bg-obsidian-950/60 border-white/[0.06] text-zinc-500"
                    }`}
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-xs text-zinc-100">{src.name}</span>
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/[0.06] text-zinc-400">
                          {src.tag}
                        </span>
                      </div>
                      <p className="text-xs text-zinc-400">{src.desc}</p>
                    </div>

                    <div
                      className={`w-5 h-5 rounded flex items-center justify-center border ${
                        isEnabled
                          ? "bg-emerald-500 border-emerald-500 text-obsidian-950"
                          : "border-zinc-700 bg-obsidian-950"
                      }`}
                    >
                      {isEnabled && <Check className="w-3.5 h-3.5 stroke-[3]" />}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* STEP 7: READY & SYNC */}
        {currentStep === 7 && (
          <div className="space-y-6 max-w-2xl py-2">
            <div>
              <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs font-semibold mb-3">
                <CheckCircle2 className="w-3.5 h-3.5" />
                Setup Complete
              </div>
              <h2 className="text-2xl font-bold text-white tracking-tight">
                You are ready to launch your Job Agent.
              </h2>
              <p className="text-xs text-zinc-400 mt-2 leading-relaxed">
                Review your configuration summary below. Clicking &quot;Finish & Start First Sync&quot; will
                lock in your profile, complete onboarding, and immediately trigger live ingestion.
              </p>
            </div>

            {/* Summary Box */}
            <div className="p-4 rounded-xl bg-obsidian-950/80 border border-white/[0.08] space-y-3 text-xs">
              <div className="flex justify-between py-1 border-b border-white/[0.06]">
                <span className="text-zinc-500">Target Roles:</span>
                <span className="text-zinc-200 font-medium">
                  {profile.target_roles.slice(0, 3).join(", ") || "None"}
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-white/[0.06]">
                <span className="text-zinc-500">Experience Cap:</span>
                <span className="text-zinc-200 font-medium">
                  {preferences.experience_max_years} years ({profile.experience_level})
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-white/[0.06]">
                <span className="text-zinc-500">AI Provider:</span>
                <span className="text-emerald-400 font-medium font-mono">
                  {selectedProvider} ({aiModel})
                </span>
              </div>
              <div className="flex justify-between py-1">
                <span className="text-zinc-500">Active Sources:</span>
                <span className="text-zinc-200 font-medium">
                  {Object.entries(sources)
                    .filter(([, v]) => v)
                    .map(([k]) => k.toUpperCase())
                    .join(", ")}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Wizard Footer Controls */}
        <div className="pt-8 border-t border-white/[0.06] flex items-center justify-between mt-8">
          <button
            type="button"
            onClick={handleBack}
            disabled={currentStep === 1 || saving}
            className={`px-4 py-2 rounded-lg text-xs font-medium flex items-center gap-2 transition-all ${
              currentStep === 1
                ? "opacity-0 pointer-events-none"
                : "text-zinc-400 hover:text-zinc-200 bg-white/[0.04] hover:bg-white/[0.08]"
            }`}
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Back
          </button>

          {currentStep < STEPS.length ? (
            <button
              type="button"
              onClick={handleNext}
              disabled={saving}
              className="px-5 py-2.5 rounded-lg text-xs font-semibold bg-emerald-500 hover:bg-emerald-400 text-obsidian-950 flex items-center gap-2 shadow-lg shadow-emerald-500/20 transition-all"
            >
              {saving ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  <span>Saving...</span>
                </>
              ) : (
                <>
                  <span>Next Step</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </>
              )}
            </button>
          ) : (
            <button
              type="button"
              onClick={handleFinishAndSync}
              disabled={saving}
              className="px-6 py-2.5 rounded-lg text-xs font-semibold bg-emerald-500 hover:bg-emerald-400 text-obsidian-950 flex items-center gap-2 shadow-lg shadow-emerald-500/20 transition-all"
            >
              <Rocket className="w-4 h-4" />
              <span>Finish & Start First Sync</span>
            </button>
          )}
        </div>
      </main>

      {/* Sync Progress Modal */}
      <SyncProgressModal
        isOpen={isSyncModalOpen}
        onClose={() => {
          setIsSyncModalOpen(false);
          router.push("/jobs");
        }}
        jobId={null}
        source="ALL"
        onSyncComplete={() => {
          setIsSyncModalOpen(false);
          router.push("/jobs");
        }}
      />
    </div>
  );
}
