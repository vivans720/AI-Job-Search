"use client";

import { useEffect, useState } from "react";
import {
  Sliders,
  Plus,
  X,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Save,
  Clock,
  Briefcase,
  GraduationCap,
  MapPin,
  Building2,
  Sparkles,
  Globe,
  RotateCcw,
  Check,
} from "lucide-react";
import {
  UserPreferences,
  DEFAULT_PREFERENCES,
  FRESHNESS_OPTIONS,
  EXPERIENCE_OPTIONS,
  ROLE_TYPE_OPTIONS,
  SOURCE_BOARD_OPTIONS,
  SUGGESTED_LOCATIONS,
  FreshnessOption,
  ExperienceOption,
  RoleTypeOption,
  SourceBoardOption,
  getLocalPreferences,
  loadUserPreferences,
  saveUserPreferences,
} from "@/lib/preferences";

export default function PreferencesPage() {
  const [preferences, setPreferences] = useState<UserPreferences>(() => getLocalPreferences());
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const [locationInput, setLocationInput] = useState("");
  const [excludedInput, setExcludedInput] = useState("");
  const [priorityInput, setPriorityInput] = useState("");

  useEffect(() => {
    let isMounted = true;
    loadUserPreferences()
      .then((loaded) => {
        if (isMounted) {
          setPreferences(loaded);
        }
      })
      .catch(() => {
        // Fallback already populated from localStorage
      });
    return () => {
      isMounted = false;
    };
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setMessage(null);
    try {
      const saved = await saveUserPreferences(preferences);
      setPreferences(saved);
      setMessage({
        type: "success",
        text: "Search preferences saved to local cache and synchronized with server.",
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to save preferences";
      setMessage({ type: "error", text: msg });
    } finally {
      setSaving(false);
    }
  };

  const handleResetDefaults = () => {
    setPreferences({ ...DEFAULT_PREFERENCES });
    setMessage({
      type: "success",
      text: "Preferences reset to default values. Click 'Save Preferences' to persist.",
    });
  };

  // Location handlers
  const handleAddLocation = (locToAdd?: string) => {
    const loc = (locToAdd || locationInput).trim();
    if (!loc) return;
    if (!preferences.preferred_locations.some((l) => l.toLowerCase() === loc.toLowerCase())) {
      setPreferences((prev) => ({
        ...prev,
        preferred_locations: [...prev.preferred_locations, loc],
      }));
    }
    if (!locToAdd) setLocationInput("");
  };

  const handleRemoveLocation = (locToRemove: string) => {
    setPreferences((prev) => ({
      ...prev,
      preferred_locations: prev.preferred_locations.filter((l) => l !== locToRemove),
    }));
  };

  // Board toggle handler
  const handleToggleBoard = (board: SourceBoardOption) => {
    setPreferences((prev) => {
      const exists = prev.source_boards.includes(board);
      const updated = exists
        ? prev.source_boards.filter((b) => b !== board)
        : [...prev.source_boards, board];
      return { ...prev, source_boards: updated.length > 0 ? updated : [board] };
    });
  };

  // Excluded company handlers
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

  // Priority company handlers
  const handleAddPriorityCompany = () => {
    const c = priorityInput.trim();
    const existing = preferences.priority_companies || [];
    if (c && !existing.includes(c)) {
      setPreferences((prev) => ({
        ...prev,
        priority_companies: [...existing, c],
      }));
      setPriorityInput("");
    }
  };

  const handleRemovePriorityCompany = (c: string) => {
    const existing = preferences.priority_companies || [];
    setPreferences((prev) => ({
      ...prev,
      priority_companies: existing.filter((x) => x !== c),
    }));
  };

  return (
    <div className="space-y-8 pb-16 max-w-4xl">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-white/[0.08]">
        <div>
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-mono uppercase tracking-wider mb-2">
            <Sliders className="w-3.5 h-3.5" />
            <span>Search & Filter Strategy</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Job Search Preferences</h1>
          <p className="text-sm text-zinc-400 mt-1">
            Configure freshness window, experience criteria, match thresholds, target cities, role types, source boards, and company filters.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleResetDefaults}
            disabled={saving}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium text-zinc-400 hover:text-zinc-200 bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] transition-all"
            title="Reset to default preferences"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Defaults</span>
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-xl text-xs font-semibold shadow-sm transition-all"
          >
            {saving ? (
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Save className="w-3.5 h-3.5" />
            )}
            <span>{saving ? "Saving..." : "Save Preferences"}</span>
          </button>
        </div>
      </div>

      {message && (
        <div
          className={`p-4 rounded-xl flex items-center gap-3 text-xs border backdrop-blur-md transition-all ${
            message.type === "success"
              ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-300"
              : "bg-rose-500/10 border-rose-500/20 text-rose-300"
          }`}
        >
          {message.type === "success" ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
          ) : (
            <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
          )}
          <span className="font-medium">{message.text}</span>
        </div>
      )}

      {/* 1. Freshness & Match Threshold */}
      <div className="p-6 rounded-2xl bg-obsidian-900/60 border border-white/[0.08] shadow-surface-inset space-y-6">
        <div>
          <div className="flex items-center gap-2 text-white text-sm font-semibold mb-1">
            <Clock className="w-4 h-4 text-emerald-400" />
            <h2>Freshness Window & Match Threshold</h2>
          </div>
          <p className="text-xs text-zinc-400">
            Define publication recency limits to bypass ghost jobs and set minimum score filters.
          </p>
        </div>

        {/* Discrete Freshness Options */}
        <div>
          <div className="flex justify-between items-center mb-2">
            <label className="text-xs font-medium text-zinc-300">
              Freshness Cutoff (Hours)
            </label>
            <span className="text-xs font-mono text-emerald-400">
              Within {preferences.freshness_hours} {preferences.freshness_hours === 1 ? "Hour" : "Hours"}
            </span>
          </div>
          <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
            {FRESHNESS_OPTIONS.map((hours) => {
              const isSelected = preferences.freshness_hours === hours;
              return (
                <button
                  key={hours}
                  type="button"
                  onClick={() =>
                    setPreferences((prev) => ({
                      ...prev,
                      freshness_hours: hours as FreshnessOption,
                    }))
                  }
                  className={`py-2.5 px-3 rounded-xl text-xs font-medium transition-all text-center border ${
                    isSelected
                      ? "bg-emerald-500 text-white border-emerald-400 shadow-sm shadow-emerald-500/20 font-semibold"
                      : "bg-obsidian-950/70 hover:bg-white/[0.06] text-zinc-300 border-white/[0.08]"
                  }`}
                >
                  {hours}h
                </button>
              );
            })}
          </div>
          <p className="text-[11px] text-zinc-500 mt-1.5">
            Only jobs posted within the selected discrete window are surfaced.
          </p>
        </div>

        {/* Match Threshold Slider */}
        <div className="pt-4 border-t border-white/[0.06]">
          <div className="flex justify-between items-center mb-2">
            <div>
              <label className="text-xs font-medium text-zinc-300 block">
                Minimum Match Threshold
              </label>
              <span className="text-[11px] text-zinc-500">
                Jobs with composite score below this percentage are suppressed during search.
              </span>
            </div>
            <span className="text-sm font-semibold text-emerald-400 font-mono">
              {preferences.match_threshold}%
            </span>
          </div>
          <input
            type="range"
            min="0"
            max="100"
            step="5"
            value={preferences.match_threshold}
            onChange={(e) =>
              setPreferences((prev) => ({
                ...prev,
                match_threshold: Math.max(0, Math.min(100, parseInt(e.target.value) || 0)),
              }))
            }
            className="w-full accent-emerald-500 cursor-pointer"
          />
          <div className="flex justify-between text-[10px] text-zinc-500 font-mono mt-1">
            <span>0% (All Jobs)</span>
            <span>50% (Moderate)</span>
            <span>75% (High Match)</span>
            <span>100% (Exact)</span>
          </div>
        </div>
      </div>

      {/* 2. Role Type & Experience Level */}
      <div className="p-6 rounded-2xl bg-obsidian-900/60 border border-white/[0.08] shadow-surface-inset space-y-6">
        <div>
          <div className="flex items-center gap-2 text-white text-sm font-semibold mb-1">
            <Briefcase className="w-4 h-4 text-emerald-400" />
            <h2>Role Type & Experience Level</h2>
          </div>
          <p className="text-xs text-zinc-400">
            Specify employment category and experience bracket for automatic filter application.
          </p>
        </div>

        {/* Role Type Selection */}
        <div>
          <label className="text-xs font-medium text-zinc-300 block mb-2">
            Target Employment Type
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
            {ROLE_TYPE_OPTIONS.map((opt) => {
              const isSelected = preferences.role_type === opt.value;
              return (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() =>
                    setPreferences((prev) => ({
                      ...prev,
                      role_type: opt.value as RoleTypeOption,
                    }))
                  }
                  className={`p-3 rounded-xl text-left border transition-all ${
                    isSelected
                      ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-300 shadow-sm"
                      : "bg-obsidian-950/70 border-white/[0.08] text-zinc-300 hover:bg-white/[0.04]"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold">{opt.label}</span>
                    {isSelected && <Check className="w-3.5 h-3.5 text-emerald-400" />}
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Experience Level */}
        <div className="pt-4 border-t border-white/[0.06]">
          <div className="flex items-center gap-2 mb-2">
            <GraduationCap className="w-3.5 h-3.5 text-zinc-400" />
            <label className="text-xs font-medium text-zinc-300">
              Experience Level Tier
            </label>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
            {EXPERIENCE_OPTIONS.map((opt) => {
              const isSelected = preferences.experience_level === opt.value;
              return (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() =>
                    setPreferences((prev) => ({
                      ...prev,
                      experience_level: opt.value as ExperienceOption,
                    }))
                  }
                  className={`p-3 rounded-xl text-left border transition-all ${
                    isSelected
                      ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-300 shadow-sm"
                      : "bg-obsidian-950/70 border-white/[0.08] text-zinc-300 hover:bg-white/[0.04]"
                  }`}
                >
                  <div className="flex items-center justify-between mb-0.5">
                    <span className="text-xs font-semibold">{opt.label}</span>
                    {isSelected && <Check className="w-3.5 h-3.5 text-emerald-400" />}
                  </div>
                  <span className="text-[11px] text-zinc-500 block">{opt.desc}</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* 3. Preferred Locations */}
      <div className="p-6 rounded-2xl bg-obsidian-900/60 border border-white/[0.08] shadow-surface-inset space-y-4">
        <div>
          <div className="flex items-center gap-2 text-white text-sm font-semibold mb-1">
            <MapPin className="w-4 h-4 text-emerald-400" />
            <h2>Preferred Locations</h2>
          </div>
          <p className="text-xs text-zinc-400">
            Target cities and remote preferences to automatically populate your active search filter.
          </p>
        </div>

        {/* Input */}
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Add location (e.g. Bengaluru, Remote, Pune)"
            value={locationInput}
            onChange={(e) => setLocationInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), handleAddLocation())}
            className="flex-1 bg-obsidian-950 border border-white/[0.1] rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-emerald-500"
          />
          <button
            type="button"
            onClick={() => handleAddLocation()}
            className="px-3.5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-xs font-medium text-white transition-colors inline-flex items-center gap-1.5"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add</span>
          </button>
        </div>

        {/* Quick-add suggestions */}
        <div>
          <span className="text-[11px] text-zinc-500 font-medium block mb-1.5">
            Quick Add Suggestions:
          </span>
          <div className="flex flex-wrap gap-1.5">
            {SUGGESTED_LOCATIONS.map((loc) => {
              const isAdded = preferences.preferred_locations.some(
                (l) => l.toLowerCase() === loc.toLowerCase()
              );
              return (
                <button
                  key={loc}
                  type="button"
                  onClick={() => (isAdded ? handleRemoveLocation(loc) : handleAddLocation(loc))}
                  className={`text-xs px-2.5 py-1 rounded-md border transition-all inline-flex items-center gap-1 ${
                    isAdded
                      ? "bg-emerald-500/20 border-emerald-500/40 text-emerald-300 font-medium"
                      : "bg-white/[0.04] hover:bg-white/[0.08] border-white/[0.08] text-zinc-400"
                  }`}
                >
                  {isAdded && <Check className="w-3 h-3 text-emerald-400" />}
                  <span>{loc}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Active Locations list */}
        <div className="pt-2 border-t border-white/[0.06]">
          <span className="text-[11px] text-zinc-500 font-medium block mb-2">
            Selected Target Locations ({preferences.preferred_locations.length}):
          </span>
          <div className="flex flex-wrap gap-1.5 min-h-[32px]">
            {preferences.preferred_locations.length === 0 ? (
              <span className="text-xs text-zinc-600 italic">No locations configured yet. All locations will be accepted.</span>
            ) : (
              preferences.preferred_locations.map((loc) => (
                <span
                  key={loc}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium"
                >
                  <MapPin className="w-3 h-3 text-emerald-400" />
                  <span>{loc}</span>
                  <button
                    type="button"
                    onClick={() => handleRemoveLocation(loc)}
                    className="hover:text-emerald-200"
                    title={`Remove ${loc}`}
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))
            )}
          </div>
        </div>
      </div>

      {/* 4. Source Boards Selection */}
      <div className="p-6 rounded-2xl bg-obsidian-900/60 border border-white/[0.08] shadow-surface-inset space-y-4">
        <div>
          <div className="flex items-center gap-2 text-white text-sm font-semibold mb-1">
            <Globe className="w-4 h-4 text-emerald-400" />
            <h2>Source Job Boards</h2>
          </div>
          <p className="text-xs text-zinc-400">
            Choose which job boards to search across and prioritize.
          </p>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {SOURCE_BOARD_OPTIONS.map((opt) => {
            const isChecked = preferences.source_boards.includes(opt.value);
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => handleToggleBoard(opt.value)}
                className={`p-3 rounded-xl border text-left transition-all flex items-center justify-between ${
                  isChecked
                    ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-300 font-medium shadow-sm"
                    : "bg-obsidian-950/70 border-white/[0.08] text-zinc-400 hover:bg-white/[0.04]"
                }`}
              >
                <span className="text-xs font-medium">{opt.label}</span>
                <div
                  className={`w-4 h-4 rounded border flex items-center justify-center transition-all ${
                    isChecked
                      ? "bg-emerald-500 border-emerald-400 text-white"
                      : "border-white/[0.2] bg-white/[0.02]"
                  }`}
                >
                  {isChecked && <Check className="w-3 h-3" />}
                </div>
              </button>
            );
          })}
        </div>
        <p className="text-[11px] text-zinc-500">
          At least one board must remain selected.
        </p>
      </div>

      {/* 5. Excluded Companies & Agencies */}
      <div className="p-6 rounded-2xl bg-obsidian-900/60 border border-white/[0.08] shadow-surface-inset space-y-4">
        <div>
          <div className="flex items-center gap-2 text-white text-sm font-semibold mb-1">
            <Building2 className="w-4 h-4 text-rose-400" />
            <h2>Excluded Companies & Agencies</h2>
          </div>
          <p className="text-xs text-zinc-400">
            List staffing agencies, consultancies, or companies you wish to permanently filter out of job results.
          </p>
        </div>

        <div className="flex gap-2">
          <input
            type="text"
            placeholder="e.g. Staffing Agency, Revature, CyberCoders"
            value={excludedInput}
            onChange={(e) => setExcludedInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), handleAddExcludedCompany())}
            className="flex-1 bg-obsidian-950 border border-white/[0.1] rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-emerald-500"
          />
          <button
            type="button"
            onClick={handleAddExcludedCompany}
            className="px-3.5 py-2 rounded-lg bg-rose-600/80 hover:bg-rose-600 text-xs font-medium text-white transition-colors inline-flex items-center gap-1.5"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Exclude</span>
          </button>
        </div>

        <div className="flex flex-wrap gap-1.5 min-h-[32px]">
          {preferences.excluded_companies.length === 0 ? (
            <span className="text-xs text-zinc-600 italic">No companies excluded yet.</span>
          ) : (
            preferences.excluded_companies.map((c) => (
              <span
                key={c}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs bg-rose-500/10 text-rose-400 border border-rose-500/20 font-medium"
              >
                <span>{c}</span>
                <button
                  type="button"
                  onClick={() => handleRemoveExcludedCompany(c)}
                  className="hover:text-rose-200"
                  title={`Remove ${c}`}
                >
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))
          )}
        </div>
      </div>

      {/* 6. Priority Target Companies */}
      <div className="p-6 rounded-2xl bg-obsidian-900/60 border border-white/[0.08] shadow-surface-inset space-y-4">
        <div>
          <div className="flex items-center gap-2 text-white text-sm font-semibold mb-1">
            <Sparkles className="w-4 h-4 text-emerald-400" />
            <h2>Priority Target Companies</h2>
          </div>
          <p className="text-xs text-zinc-400">
            Boost match visibility and ranking for listings from these target organizations.
          </p>
        </div>

        <div className="flex gap-2">
          <input
            type="text"
            placeholder="e.g. Google, Zerodha, Swiggy, Microsoft"
            value={priorityInput}
            onChange={(e) => setPriorityInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), handleAddPriorityCompany())}
            className="flex-1 bg-obsidian-950 border border-white/[0.1] rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-emerald-500"
          />
          <button
            type="button"
            onClick={handleAddPriorityCompany}
            className="px-3.5 py-2 rounded-lg bg-white/[0.08] hover:bg-white/[0.12] text-xs font-medium text-zinc-200 transition-colors inline-flex items-center gap-1.5"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add</span>
          </button>
        </div>

        <div className="flex flex-wrap gap-1.5 min-h-[32px]">
          {(!preferences.priority_companies || preferences.priority_companies.length === 0) ? (
            <span className="text-xs text-zinc-600 italic">No priority companies added yet.</span>
          ) : (
            preferences.priority_companies.map((c) => (
              <span
                key={c}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium"
              >
                <span>{c}</span>
                <button
                  type="button"
                  onClick={() => handleRemovePriorityCompany(c)}
                  className="hover:text-emerald-200"
                  title={`Remove ${c}`}
                >
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
