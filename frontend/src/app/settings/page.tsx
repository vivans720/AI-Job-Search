"use client";

import { useEffect, useState } from "react";
import {
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  History,
  Clock,
  CalendarClock,
  Play,
  Cpu,
  Zap,
  Key,
  Globe,
  Sparkles,
  Wand2,
  BarChart3,
  Target,
} from "lucide-react";

interface Preferences {
  freshness_hours: number;
  experience_max_years: number;
  preferred_technologies: string[];
  preferred_industries?: string[];
  sync_interval_hours?: number;
  auto_sync_enabled?: boolean;
  last_auto_sync_at?: string | null;
  ai_provider?: string | null;
  ai_model?: string | null;
  ai_base_url?: string | null;
  has_custom_api_key?: boolean;
}

interface AIProviderInfo {
  id: string;
  name: string;
  type: string;
  default_model: string;
  configured: boolean;
  description: string;
}

interface ScheduleInfo {
  auto_sync_enabled: boolean;
  sync_interval_hours: number;
  last_auto_sync_at: string | null;
  next_run_at: string | null;
  seconds_until_next_run: number | null;
}

interface SyncLogEntry {
  timestamp: string;
  source: string;
  status: string;
  total_discovered?: number;
  fresh_jobs?: number;
  canonical_saved?: number;
  duration_ms?: number;
  error?: string;
}

interface EvaluationCase {
  fixture_id: string;
  category: string;
  schema_valid: boolean;
  latency_ms: number;
  error?: string | null;
  metrics?: Record<string, number>;
}

interface EvaluationReport {
  timestamp: string;
  total_fixtures: number;
  schema_valid_rate: number;
  avg_latency_ms: number;
  total_duration_ms: number;
  summary?: {
    avg_resume_skill_f1?: number;
    avg_job_required_skill_f1?: number;
  };
  cases?: EvaluationCase[];
}

export default function AuditLogsPage() {
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Scheduler states
  const [schedule, setSchedule] = useState<ScheduleInfo | null>(null);
  const [updatingSchedule, setUpdatingSchedule] = useState(false);
  const [triggeringSchedule, setTriggeringSchedule] = useState(false);

  // Sync history states
  const [syncHistory, setSyncHistory] = useState<SyncLogEntry[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  // AI Provider states (Phase 39)
  const [aiProviders, setAiProviders] = useState<AIProviderInfo[]>([]);
  const [selectedProvider, setSelectedProvider] = useState<string>("ollama");
  const [customModel, setCustomModel] = useState<string>("");
  const [customBaseUrl, setCustomBaseUrl] = useState<string>("");
  const [customApiKey, setCustomApiKey] = useState<string>("");
  const [testingAi, setTestingAi] = useState<boolean>(false);
  const [savingAi, setSavingAi] = useState<boolean>(false);
  const [aiTestResult, setAiTestResult] = useState<{
    reachable: boolean;
    latency_ms?: number;
    error?: string;
    sample_response?: string;
  } | null>(null);

  // AI Pipeline states (Phase 40)
  const [pipelineSkillsInput, setPipelineSkillsInput] = useState<string>("React.js, ReactJS, py, fast api, k8s, postgres");
  const [pipelineSkillsResult, setPipelineSkillsResult] = useState<{
    mappings?: { raw_token: string; canonical_skill: string }[];
  } | null>(null);
  const [testingNormalize, setTestingNormalize] = useState<boolean>(false);
  const [pipelineJobTitle, setPipelineJobTitle] = useState<string>("Full Stack Python Developer");
  const [pipelineJobDesc, setPipelineJobDesc] = useState<string>("We need a developer with Python, FastAPI, Docker, and React experience. Nice to have: PostgreSQL and Kubernetes.");
  const [pipelineJobResult, setPipelineJobResult] = useState<{
    required_skills?: string[];
    preferred_skills?: string[];
    tools_and_technologies?: string[];
    soft_skills?: string[];
  } | null>(null);
  const [testingExtractJob, setTestingExtractJob] = useState<boolean>(false);

  // AI Evaluation Framework states (Phase 41)
  const [evalReport, setEvalReport] = useState<EvaluationReport | null>(null);
  const [runningEval, setRunningEval] = useState<boolean>(false);
  const [loadingEvalReport, setLoadingEvalReport] = useState<boolean>(false);

  const fetchPrefs = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/v1/preferences");
      if (res.ok) {
        const data = await res.json();
        setPrefs(data);
        if (data.ai_provider) setSelectedProvider(data.ai_provider);
        if (data.ai_model) setCustomModel(data.ai_model);
        if (data.ai_base_url) setCustomBaseUrl(data.ai_base_url);
      }
    } catch {
      // Backend offline
    } finally {
      setLoading(false);
    }
  };

  const fetchAiProviders = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/v1/ai/providers");
      if (res.ok) {
        const list = await res.json();
        setAiProviders(list);
      }
    } catch {
      // AI provider listing offline
    }
  };

  const fetchSchedule = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/v1/sources/schedule");
      if (res.ok) {
        const data = await res.json();
        setSchedule(data);
      }
    } catch {
      // Backend offline
    }
  };

  const fetchSyncHistory = async () => {
    setLoadingHistory(true);
    try {
      const res = await fetch("http://localhost:8000/api/v1/sources/history?limit=8");
      if (res.ok) {
        const data = await res.json();
        setSyncHistory(data.history || []);
      }
    } catch {
      // Sync history unreachable
    } finally {
      setLoadingHistory(false);
    }
  };

  const handleTestAiConnection = async () => {
    setTestingAi(true);
    setAiTestResult(null);
    try {
      const res = await fetch("http://localhost:8000/api/v1/ai/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: selectedProvider,
          model: customModel || undefined,
          base_url: customBaseUrl || undefined,
          api_key: customApiKey || undefined,
        }),
      });
      const data = await res.json();
      setAiTestResult(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Connection failed";
      setAiTestResult({ reachable: false, error: msg });
    } finally {
      setTestingAi(false);
    }
  };

  const handleTestNormalizeSkills = async () => {
    setTestingNormalize(true);
    setPipelineSkillsResult(null);
    try {
      const skills = pipelineSkillsInput.split(",").map((s) => s.trim()).filter(Boolean);
      const res = await fetch("http://localhost:8000/api/v1/ai/pipeline/normalize-skills", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ skills }),
      });
      if (res.ok) {
        const data = await res.json();
        setPipelineSkillsResult(data);
      }
    } catch {
      // Error
    } finally {
      setTestingNormalize(false);
    }
  };

  const fetchEvalReport = async () => {
    setLoadingEvalReport(true);
    try {
      const res = await fetch("http://localhost:8000/api/v1/ai/evaluation/report");
      if (res.ok) {
        const data = await res.json();
        if (data.status !== "not_run") {
          setEvalReport(data);
        }
      }
    } catch {
      // Offline
    } finally {
      setLoadingEvalReport(false);
    }
  };

  const handleRunEvaluation = async (category: string = "all") => {
    setRunningEval(true);
    try {
      const res = await fetch("http://localhost:8000/api/v1/ai/evaluation/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category }),
      });
      if (res.ok) {
        const data = await res.json();
        setEvalReport(data);
      }
    } catch {
      // Error running eval
    } finally {
      setRunningEval(false);
    }
  };

  const handleTestExtractJob = async () => {
    setTestingExtractJob(true);
    setPipelineJobResult(null);
    try {
      const res = await fetch("http://localhost:8000/api/v1/ai/pipeline/extract-job-skills", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: pipelineJobTitle,
          description: pipelineJobDesc,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setPipelineJobResult(data);
      }
    } catch {
      // Error
    } finally {
      setTestingExtractJob(false);
    }
  };

  const handleSaveAiProvider = async () => {
    setSavingAi(true);
    setMessage(null);
    try {
      const payload: Record<string, unknown> = {
        ai_provider: selectedProvider,
        ai_model: customModel || null,
        ai_base_url: customBaseUrl || null,
      };
      if (customApiKey.trim()) {
        payload.ai_api_key = customApiKey.trim();
      }
      const res = await fetch("http://localhost:8000/api/v1/preferences", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        const updated = await res.json();
        setPrefs(updated);
        setCustomApiKey("");
        setMessage({
          type: "success",
          text: `AI Provider updated to ${selectedProvider.toUpperCase()}${customModel ? ` (${customModel})` : ""}.`,
        });
      } else {
        setMessage({ type: "error", text: "Failed to save AI provider configuration." });
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Save failed";
      setMessage({ type: "error", text: msg });
    } finally {
      setSavingAi(false);
    }
  };

  const handleUpdateInterval = async (hours: number, enabled: boolean) => {
    setUpdatingSchedule(true);
    setMessage(null);
    try {
      const res = await fetch("http://localhost:8000/api/v1/preferences", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sync_interval_hours: hours,
          auto_sync_enabled: enabled,
        }),
      });
      if (res.ok) {
        const updated = await res.json();
        setPrefs(updated);
        await fetchSchedule();
        setMessage({
          type: "success",
          text: enabled
            ? `Automated sync interval set to every ${hours} hours.`
            : "Automated scheduled ingestion disabled.",
        });
      } else {
        setMessage({ type: "error", text: "Failed to update scheduler settings." });
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to update schedule.";
      setMessage({ type: "error", text: msg });
    } finally {
      setUpdatingSchedule(false);
    }
  };

  const handleTriggerScheduleNow = async () => {
    setTriggeringSchedule(true);
    setMessage(null);
    try {
      const res = await fetch("http://localhost:8000/api/v1/sources/schedule/trigger", {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        await fetchSchedule();
        setMessage({
          type: "success",
          text: data.message || "Scheduled sync triggered successfully.",
        });
        setTimeout(fetchSyncHistory, 2000);
      } else {
        setMessage({ type: "error", text: "Failed to trigger scheduled sync." });
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Trigger error.";
      setMessage({ type: "error", text: msg });
    } finally {
      setTriggeringSchedule(false);
    }
  };

  useEffect(() => {
    fetchPrefs();
    fetchAiProviders();
    fetchSchedule();
    fetchSyncHistory();
    fetchEvalReport();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-sm text-zinc-500 font-mono">
        <RefreshCw className="w-4 h-4 animate-spin mr-2 text-emerald-400" />
        Loading settings and audit telemetry...
      </div>
    );
  }

  if (!prefs) {
    return (
      <div className="p-8 rounded-2xl bg-obsidian-900/60 border border-white/[0.08] text-center text-sm text-zinc-400">
        Preferences service unreachable. Ensure FastAPI backend is running on port 8000.
      </div>
    );
  }

  const currentInterval = prefs.sync_interval_hours ?? 24;
  const isAutoEnabled = prefs.auto_sync_enabled ?? true;

  return (
    <div className="space-y-8 pb-16">
      {/* Action Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-white/[0.08]">
        <div>
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md bg-purple-500/10 border border-purple-500/20 text-purple-400 text-xs font-mono uppercase tracking-wider mb-2">
            <span>Phase 39 — AI Provider & Ingestion Control</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">AI Provider & Scheduler Settings</h1>
          <p className="text-sm text-zinc-400 mt-1">
            Configure pluggable AI intelligence engines (Ollama, OpenAI, Gemini, Claude) and automated ingestion schedules.
          </p>
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

      {/* Phase 39: AI Provider Configuration Card */}
      <div className="p-6 rounded-2xl bg-obsidian-900/60 border border-white/[0.08] shadow-surface-inset space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-400">
              <Cpu className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold text-white">AI Provider Abstraction</h3>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-purple-500/10 text-purple-300 border border-purple-500/20">
                  {selectedProvider.toUpperCase()} ACTIVE
                </span>
              </div>
              <p className="text-[11px] text-zinc-400 mt-0.5">
                Pluggable LLM interface powering skill extraction, resume profiling, and match explanations.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleTestAiConnection}
              disabled={testingAi}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-obsidian-800 hover:bg-obsidian-700 border border-white/[0.08] text-zinc-300 rounded-xl text-xs font-medium transition-colors"
            >
              <Zap className={`w-3.5 h-3.5 ${testingAi ? "animate-pulse text-amber-400" : "text-amber-400"}`} />
              <span>{testingAi ? "Testing Ping..." : "Test Connection"}</span>
            </button>
            <button
              onClick={handleSaveAiProvider}
              disabled={savingAi}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-purple-600 hover:bg-purple-500 text-white rounded-xl text-xs font-medium shadow-sm transition-colors"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>{savingAi ? "Saving..." : "Save AI Provider"}</span>
            </button>
          </div>
        </div>

        {/* Live Test Diagnostic Output */}
        {aiTestResult && (
          <div
            className={`p-3.5 rounded-xl text-xs border backdrop-blur-md flex items-start gap-2.5 ${
              aiTestResult.reachable
                ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-300"
                : "bg-rose-500/10 border-rose-500/20 text-rose-300"
            }`}
          >
            {aiTestResult.reachable ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400 mt-0.5 flex-shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 text-rose-400 mt-0.5 flex-shrink-0" />
            )}
            <div className="flex-1 font-mono">
              <div className="font-semibold">
                {aiTestResult.reachable ? "Provider Connected Successfully" : "Connection Failed"}
              </div>
              <div className="text-[11px] opacity-80 mt-0.5">
                {aiTestResult.latency_ms && `Latency: ${aiTestResult.latency_ms} ms`}
                {aiTestResult.sample_response && ` • Response: "${aiTestResult.sample_response}"`}
                {aiTestResult.error && ` • Error: ${aiTestResult.error}`}
              </div>
            </div>
          </div>
        )}

        {/* Provider Cards Selection */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
          {(aiProviders.length > 0
            ? aiProviders.map((p) => ({
                id: p.id,
                name: p.name,
                type: p.type,
                hint: p.description,
                configured: p.configured,
              }))
            : [
                { id: "ollama", name: "Ollama (Local)", type: "local", hint: "Zero cost, private", configured: true },
                { id: "openai", name: "OpenAI", type: "cloud", hint: "GPT-4o, GPT-4o-mini", configured: false },
                { id: "gemini", name: "Google Gemini", type: "cloud", hint: "gemini-2.0-flash", configured: false },
                { id: "anthropic", name: "Claude (Anthropic)", type: "cloud", hint: "Claude 3.5 Haiku", configured: false },
                { id: "deepseek", name: "DeepSeek", type: "cloud", hint: "DeepSeek V3 / R1", configured: false },
                { id: "openai_compatible", name: "Custom / Proxy", type: "cloud", hint: "OmniRoute, vLLM, LM Studio", configured: false },
              ]
          ).map((item) => {
            const isSelected = selectedProvider.toLowerCase() === item.id;
            return (
              <button
                key={item.id}
                onClick={() => {
                  setSelectedProvider(item.id);
                  setAiTestResult(null);
                }}
                className={`p-3.5 rounded-xl border text-left transition-all ${
                  isSelected
                    ? "bg-purple-500/15 border-purple-500/40 shadow-sm"
                    : "bg-obsidian-950/40 border-white/[0.05] hover:border-white/[0.1] hover:bg-white/[0.02]"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-xs font-semibold ${isSelected ? "text-purple-300" : "text-zinc-200"}`}>
                    {item.name}
                  </span>
                  <span
                    className={`text-[10px] font-mono uppercase px-1.5 py-0.5 rounded ${
                      item.type === "local"
                        ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                        : "bg-zinc-800 text-zinc-400"
                    }`}
                  >
                    {item.type}
                  </span>
                </div>
                <div className="text-[11px] text-zinc-400 mt-1">{item.hint}</div>
              </button>
            );
          })}
        </div>

        {/* Dynamic Credentials Form */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2 border-t border-white/[0.06]">
          <div>
            <label className="block text-[11px] font-mono text-zinc-400 uppercase tracking-wider mb-1.5">
              Model Override
            </label>
            <input
              type="text"
              placeholder={
                selectedProvider === "ollama"
                  ? "qwen3.5:9b"
                  : selectedProvider === "openai"
                    ? "gpt-4o-mini"
                    : selectedProvider === "gemini"
                      ? "gemini-2.0-flash"
                      : selectedProvider === "anthropic"
                        ? "claude-3-5-haiku-20241022"
                        : "auto/best-fast"
              }
              value={customModel}
              onChange={(e) => setCustomModel(e.target.value)}
              className="w-full px-3 py-2 text-xs bg-obsidian-950/80 border border-white/[0.08] rounded-xl text-white placeholder:text-zinc-600 focus:outline-none focus:border-purple-500/50"
            />
          </div>

          <div>
            <label className="block text-[11px] font-mono text-zinc-400 uppercase tracking-wider mb-1.5 flex items-center gap-1">
              <Globe className="w-3 h-3 text-zinc-500" />
              <span>Base URL (Optional)</span>
            </label>
            <input
              type="text"
              placeholder={
                selectedProvider === "ollama"
                  ? "http://localhost:11434/v1"
                  : selectedProvider === "gemini"
                    ? "https://generativelanguage.googleapis.com/v1beta/openai/"
                    : "Leave empty for provider default"
              }
              value={customBaseUrl}
              onChange={(e) => setCustomBaseUrl(e.target.value)}
              className="w-full px-3 py-2 text-xs bg-obsidian-950/80 border border-white/[0.08] rounded-xl text-white placeholder:text-zinc-600 focus:outline-none focus:border-purple-500/50"
            />
          </div>

          <div>
            <label className="block text-[11px] font-mono text-zinc-400 uppercase tracking-wider mb-1.5 flex items-center gap-1">
              <Key className="w-3 h-3 text-zinc-500" />
              <span>API Key {prefs.has_custom_api_key && selectedProvider === prefs.ai_provider ? "(Configured ✓)" : ""}</span>
            </label>
            <input
              type="password"
              placeholder={
                selectedProvider === "ollama"
                  ? "Not required for local Ollama"
                  : prefs.has_custom_api_key
                    ? "•••••••••••••••• (Leave blank to keep)"
                    : "Enter API key"
              }
              value={customApiKey}
              disabled={selectedProvider === "ollama"}
              onChange={(e) => setCustomApiKey(e.target.value)}
              className="w-full px-3 py-2 text-xs bg-obsidian-950/80 border border-white/[0.08] rounded-xl text-white placeholder:text-zinc-600 focus:outline-none focus:border-purple-500/50 disabled:opacity-40"
            />
          </div>
        </div>
      </div>

      {/* Phase 40: AI Pipeline Intelligence Playground Card */}
      <div className="p-6 rounded-2xl bg-obsidian-900/60 border border-white/[0.08] shadow-surface-inset space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-400">
              <Wand2 className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">Phase 40 — AI Pipeline Playground</h3>
              <p className="text-[11px] text-zinc-400">
                Test LLM-driven structured skill normalization and job description extraction in real time.
              </p>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
          {/* Skill Normalization Test */}
          <div className="p-4 rounded-xl bg-obsidian-950/40 border border-white/[0.06] space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-zinc-200">Skill Canonicalization</span>
              <button
                onClick={handleTestNormalizeSkills}
                disabled={testingNormalize}
                className="px-2.5 py-1 text-[11px] bg-purple-600/20 hover:bg-purple-600/30 text-purple-300 border border-purple-500/30 rounded-lg transition-colors flex items-center gap-1"
              >
                {testingNormalize ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                <span>Normalize</span>
              </button>
            </div>
            <input
              type="text"
              value={pipelineSkillsInput}
              onChange={(e) => setPipelineSkillsInput(e.target.value)}
              placeholder="e.g. React.js, py, k8s, postgres"
              className="w-full px-3 py-1.5 text-xs bg-obsidian-900 border border-white/[0.08] rounded-lg text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-purple-500/50 font-mono"
            />
            {pipelineSkillsResult && (
              <div className="p-2.5 bg-obsidian-900/80 rounded-lg border border-white/[0.04] text-[11px] font-mono space-y-1">
                <div className="text-zinc-500 uppercase text-[9px]">Resolved Mappings:</div>
                {pipelineSkillsResult.mappings?.map((m, idx: number) => (
                  <div key={idx} className="flex items-center justify-between text-zinc-300">
                    <span className="text-zinc-400 font-medium">{m.raw_token}</span>
                    <span className="text-emerald-400 font-semibold">{m.canonical_skill}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Job Description Extraction Test */}
          <div className="p-4 rounded-xl bg-obsidian-950/40 border border-white/[0.06] space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-zinc-200">Job Skills Extraction</span>
              <button
                onClick={handleTestExtractJob}
                disabled={testingExtractJob}
                className="px-2.5 py-1 text-[11px] bg-purple-600/20 hover:bg-purple-600/30 text-purple-300 border border-purple-500/30 rounded-lg transition-colors flex items-center gap-1"
              >
                {testingExtractJob ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                <span>Extract</span>
              </button>
            </div>
            <input
              type="text"
              value={pipelineJobTitle}
              onChange={(e) => setPipelineJobTitle(e.target.value)}
              placeholder="Job Title"
              className="w-full px-3 py-1.5 text-xs bg-obsidian-900 border border-white/[0.08] rounded-lg text-zinc-200 focus:outline-none focus:border-purple-500/50"
            />
            <textarea
              rows={2}
              value={pipelineJobDesc}
              onChange={(e) => setPipelineJobDesc(e.target.value)}
              placeholder="Job Description snippet..."
              className="w-full px-3 py-1.5 text-xs bg-obsidian-900 border border-white/[0.08] rounded-lg text-zinc-200 focus:outline-none focus:border-purple-500/50 resize-none"
            />
            {pipelineJobResult && (
              <div className="p-2.5 bg-obsidian-900/80 rounded-lg border border-white/[0.04] text-[11px] font-mono space-y-1">
                <div>
                  <span className="text-purple-400 font-medium">Required: </span>
                  <span className="text-zinc-300">{pipelineJobResult.required_skills?.join(", ") || "None"}</span>
                </div>
                <div>
                  <span className="text-cyan-400 font-medium">Preferred: </span>
                  <span className="text-zinc-300">{pipelineJobResult.preferred_skills?.join(", ") || "None"}</span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Phase 41: AI Evaluation Framework Benchmark Card */}
      <div className="p-6 rounded-2xl bg-obsidian-900/60 border border-white/[0.08] shadow-surface-inset space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400">
              <BarChart3 className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">Phase 41 — AI Evaluation Framework</h3>
              <p className="text-[11px] text-zinc-400">
                Benchmark precision, recall, F1, and schema validity against gold-standard ground truth fixtures.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => handleRunEvaluation("all")}
              disabled={runningEval}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-amber-600/20 hover:bg-amber-600/30 border border-amber-500/30 text-amber-300 rounded-xl text-xs font-medium transition-colors"
            >
              <Play className={`w-3.5 h-3.5 ${runningEval ? "animate-spin" : ""}`} />
              <span>{runningEval ? "Evaluating..." : "Run Benchmark"}</span>
            </button>
            <button
              onClick={fetchEvalReport}
              disabled={loadingEvalReport}
              className="p-1.5 bg-obsidian-800 hover:bg-obsidian-700 border border-white/[0.08] text-zinc-300 rounded-xl transition-colors"
              title="Refresh Benchmark Report"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loadingEvalReport ? "animate-spin text-amber-400" : ""}`} />
            </button>
          </div>
        </div>

        {evalReport ? (
          <div className="space-y-4 pt-1">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="p-3 bg-obsidian-950/60 border border-white/[0.06] rounded-xl">
                <div className="text-[10px] uppercase font-mono text-zinc-400">Schema Validity</div>
                <div className="text-lg font-bold text-emerald-400 mt-1 font-mono">
                  {Math.round((evalReport.schema_valid_rate || 0) * 100)}%
                </div>
              </div>
              <div className="p-3 bg-obsidian-950/60 border border-white/[0.06] rounded-xl">
                <div className="text-[10px] uppercase font-mono text-zinc-400">Avg Latency</div>
                <div className="text-lg font-bold text-amber-400 mt-1 font-mono">
                  {evalReport.avg_latency_ms} ms
                </div>
              </div>
              <div className="p-3 bg-obsidian-950/60 border border-white/[0.06] rounded-xl">
                <div className="text-[10px] uppercase font-mono text-zinc-400">Resume Skill F1</div>
                <div className="text-lg font-bold text-cyan-400 mt-1 font-mono">
                  {evalReport.summary?.avg_resume_skill_f1 ?? "N/A"}
                </div>
              </div>
              <div className="p-3 bg-obsidian-950/60 border border-white/[0.06] rounded-xl">
                <div className="text-[10px] uppercase font-mono text-zinc-400">Job Req Skill F1</div>
                <div className="text-lg font-bold text-purple-400 mt-1 font-mono">
                  {evalReport.summary?.avg_job_required_skill_f1 ?? "N/A"}
                </div>
              </div>
            </div>

            <div className="p-3 bg-obsidian-950/40 rounded-xl border border-white/[0.04]">
              <div className="text-[11px] font-semibold text-zinc-300 mb-2 flex items-center gap-1.5">
                <Target className="w-3.5 h-3.5 text-amber-400" />
                <span>Test Cases Evaluated ({evalReport.cases?.length || 0})</span>
              </div>
              <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                {evalReport.cases?.map((c: EvaluationCase, i: number) => (
                  <div key={i} className="flex items-center justify-between text-xs py-1 px-2 rounded bg-obsidian-900/60 border border-white/[0.03]">
                    <span className="font-mono text-zinc-300 truncate max-w-[200px]">{c.fixture_id}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/[0.05] text-zinc-400 capitalize">{c.category}</span>
                      <span className="font-mono text-[11px] text-zinc-400">{c.latency_ms}ms</span>
                      <span className={`text-[11px] font-semibold ${c.schema_valid ? "text-emerald-400" : "text-rose-400"}`}>
                        {c.schema_valid ? "VALID" : "INVALID"}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="text-xs text-zinc-500 py-4 text-center font-mono bg-obsidian-950/30 rounded-xl border border-white/[0.04]">
            No evaluation benchmarks run yet. Click &quot;Run Benchmark&quot; above to test against gold-standard fixtures.
          </div>
        )}
      </div>

      {/* Scheduler Configuration Card */}
      <div className="p-6 rounded-2xl bg-obsidian-900/60 border border-white/[0.08] shadow-surface-inset space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
              <CalendarClock className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">Automated Ingestion Schedule</h3>
              <p className="text-[11px] text-zinc-400">
                Periodic background worker runs crawl, freshness gate, and dedup pipeline automatically.
              </p>
            </div>
          </div>

          <button
            onClick={handleTriggerScheduleNow}
            disabled={triggeringSchedule}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600/20 hover:bg-emerald-600/30 border border-emerald-500/30 text-emerald-300 rounded-xl text-xs font-medium transition-colors"
          >
            <Play className={`w-3.5 h-3.5 ${triggeringSchedule ? "animate-spin" : ""}`} />
            <span>{triggeringSchedule ? "Triggering..." : "Run Schedule Now"}</span>
          </button>
        </div>

        {/* Schedule Interval Selection */}
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
          {[
            { label: "Every 6 hours", hours: 6, enabled: true },
            { label: "Every 12 hours", hours: 12, enabled: true },
            { label: "Every 24 hours", hours: 24, enabled: true },
            { label: "Manual Only", hours: 0, enabled: false },
          ].map((opt) => {
            const isSelected =
              (!opt.enabled && !isAutoEnabled) ||
              (opt.enabled && isAutoEnabled && currentInterval === opt.hours);

            return (
              <button
                key={opt.label}
                disabled={updatingSchedule}
                onClick={() => handleUpdateInterval(opt.hours, opt.enabled)}
                className={`p-4 rounded-xl border text-left transition-all ${
                  isSelected
                    ? "bg-emerald-950/40 border-emerald-500/40 text-white shadow-surface-glow"
                    : "bg-obsidian-950/40 border-white/[0.06] text-zinc-400 hover:text-zinc-200 hover:border-white/[0.12]"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-semibold">{opt.label}</span>
                  {isSelected && <span className="w-2 h-2 rounded-full bg-emerald-400"></span>}
                </div>
                <span className="text-[11px] text-zinc-500 block font-mono">
                  {opt.enabled ? `Runs 4x/day (${opt.hours}h window)` : "Triggered on demand only"}
                </span>
              </button>
            );
          })}
        </div>

        {/* Schedule Timing Status */}
        {schedule && (
          <div className="p-4 rounded-xl bg-obsidian-950/60 border border-white/[0.06] flex flex-wrap items-center justify-between gap-4 text-xs font-mono">
            <div className="flex items-center gap-2 text-zinc-400">
              <Clock className="w-4 h-4 text-zinc-500" />
              <span>
                Status:{" "}
                <strong className={schedule.auto_sync_enabled ? "text-emerald-400" : "text-amber-400"}>
                  {schedule.auto_sync_enabled ? `Active (${schedule.sync_interval_hours}h)` : "Disabled"}
                </strong>
              </span>
            </div>

            {schedule.next_run_at && (
              <div className="text-zinc-400">
                Next scheduled sync:{" "}
                <span className="text-zinc-200">
                  {new Date(schedule.next_run_at).toLocaleString("en-IN", {
                    hour: "2-digit",
                    minute: "2-digit",
                    day: "numeric",
                    month: "short",
                  })}
                </span>
              </div>
            )}

            {schedule.last_auto_sync_at && (
              <div className="text-zinc-400">
                Last run:{" "}
                <span className="text-zinc-300">
                  {new Date(schedule.last_auto_sync_at).toLocaleString("en-IN", {
                    hour: "2-digit",
                    minute: "2-digit",
                    day: "numeric",
                    month: "short",
                  })}
                </span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Sync Ingestion Audit History */}
      <div className="p-6 rounded-2xl bg-obsidian-900/60 border border-white/[0.08] shadow-surface-inset space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-lg bg-zinc-500/10 border border-white/[0.08] text-zinc-400">
              <History className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">Ingestion Audit Log</h3>
              <p className="text-[11px] text-zinc-400">Recent cron and manual trigger discovery runs</p>
            </div>
          </div>
          <button
            onClick={fetchSyncHistory}
            disabled={loadingHistory}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-obsidian-800 hover:bg-obsidian-700 border border-white/[0.08] text-zinc-300 rounded-xl text-xs font-medium transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loadingHistory ? "animate-spin text-emerald-400" : ""}`} />
            <span>Refresh Logs</span>
          </button>
        </div>

        {syncHistory.length > 0 ? (
          <div className="overflow-x-auto rounded-xl border border-white/[0.06]">
            <table className="w-full text-left text-xs text-zinc-300">
              <thead className="text-[11px] uppercase font-mono bg-obsidian-950/80 text-zinc-400 border-b border-white/[0.06]">
                <tr>
                  <th className="py-3 px-4">Timestamp (IST)</th>
                  <th className="py-3 px-4">Source Board</th>
                  <th className="py-3 px-4">Discovered</th>
                  <th className="py-3 px-4">Fresh</th>
                  <th className="py-3 px-4">Canonical Saved</th>
                  <th className="py-3 px-4">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04] bg-obsidian-950/40">
                {syncHistory.map((item, idx) => (
                  <tr key={idx} className="hover:bg-white/[0.02] transition-colors">
                    <td className="py-2.5 px-4 font-mono text-zinc-400">
                      {new Date(item.timestamp).toLocaleString("en-IN", {
                        hour: "2-digit",
                        minute: "2-digit",
                        second: "2-digit",
                        day: "numeric",
                        month: "short",
                      })}
                    </td>
                    <td className="py-2.5 px-4 font-medium text-white capitalize">{item.source}</td>
                    <td className="py-2.5 px-4 font-tabular">{item.total_discovered ?? "-"}</td>
                    <td className="py-2.5 px-4 text-cyan-400 font-tabular font-medium">{item.fresh_jobs ?? "-"}</td>
                    <td className="py-2.5 px-4 text-emerald-400 font-tabular font-semibold">{item.canonical_saved ?? "-"}</td>
                    <td className="py-2.5 px-4">
                      <span
                        className={`px-2 py-0.5 rounded-md text-[10px] font-mono ${
                          item.status === "success"
                            ? "bg-emerald-500/10 text-emerald-400"
                            : item.status === "error"
                              ? "bg-rose-500/10 text-rose-400"
                              : "bg-zinc-500/10 text-zinc-400"
                        }`}
                      >
                        {item.status}
                      </span>
                      {item.error && (
                        <span className="block text-[10px] text-rose-400/70 mt-0.5 max-w-[200px] truncate">
                          {item.error}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-xs text-zinc-500 py-6 text-center font-mono bg-obsidian-950/30 rounded-xl border border-white/[0.04]">
            No sync telemetry records logged yet.
          </div>
        )}
      </div>
    </div>
  );
}
