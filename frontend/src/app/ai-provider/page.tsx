"use client";

import { useEffect, useState } from "react";
import {
  Cpu,
  Zap,
  Key,
  Globe,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Sparkles,
} from "lucide-react";

interface AIProviderInfo {
  id: string;
  name: string;
  type: string;
  default_model: string;
  configured: boolean;
  description: string;
  requires_api_key?: boolean;
  base_url?: string | null;
  capabilities?: Record<string, boolean>;
}

export default function AIProviderPage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testingAi, setTestingAi] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const [aiProviders, setAiProviders] = useState<AIProviderInfo[]>([]);
  const [selectedProvider, setSelectedProvider] = useState<string>("ollama");
  const [savedAiProvider, setSavedAiProvider] = useState<string | null>(null);
  const [hasCustomApiKey, setHasCustomApiKey] = useState<boolean>(false);
  const [configuredProviders, setConfiguredProviders] = useState<string[]>([]);
  const [customModel, setCustomModel] = useState<string>("");
  const [customBaseUrl, setCustomBaseUrl] = useState<string>("");
  const [customApiKey, setCustomApiKey] = useState<string>("");

  const [aiTestResult, setAiTestResult] = useState<{
    reachable: boolean;
    latency_ms?: number;
    error?: string;
    sample_response?: string;
  } | null>(null);

  const fetchProvidersAndPrefs = async () => {
    try {
      const [aiRes, prefRes] = await Promise.all([
        fetch("http://localhost:8000/api/v1/ai/providers"),
        fetch("http://localhost:8000/api/v1/preferences"),
      ]);

      if (aiRes.ok) {
        const list = await aiRes.json();
        setAiProviders(list);
      }

      if (prefRes.ok) {
        const data = await prefRes.json();
        if (data.ai_provider) {
          setSelectedProvider(data.ai_provider);
          setSavedAiProvider(data.ai_provider);
        }
        if (data.ai_model) setCustomModel(data.ai_model);
        if (data.ai_base_url) setCustomBaseUrl(data.ai_base_url);
        if (data.has_custom_api_key) setHasCustomApiKey(true);
        if (data.configured_providers) setConfiguredProviders(data.configured_providers);
      }
    } catch {
      // Offline fallback
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProvidersAndPrefs();
  }, []);

  const handleTestAiConnection = async () => {
    setTestingAi(true);
    setAiTestResult(null);
    setMessage(null);
    try {
      const res = await fetch("http://localhost:8000/api/v1/ai/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: selectedProvider,
          model: customModel.trim() || undefined,
          base_url: customBaseUrl.trim() || undefined,
          api_key: customApiKey.trim() || undefined,
        }),
      });
      const data = await res.json();
      setAiTestResult(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Connection ping failed";
      setAiTestResult({ reachable: false, error: msg });
    } finally {
      setTestingAi(false);
    }
  };

  const handleSaveAiProvider = async () => {
    setSaving(true);
    setMessage(null);
    try {
      const payload: Record<string, unknown> = {
        ai_provider: selectedProvider,
        ai_model: customModel.trim() || null,
        ai_base_url: customBaseUrl.trim() || null,
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
        setSavedAiProvider(updated.ai_provider);
        setHasCustomApiKey(updated.has_custom_api_key);
        if (updated.configured_providers) {
          setConfiguredProviders(updated.configured_providers);
        }
        setCustomApiKey("");
        setMessage({
          type: "success",
          text: `AI Provider successfully set to ${selectedProvider.toUpperCase()}${
            customModel ? ` (${customModel})` : ""
          }.`,
        });
      } else {
        setMessage({ type: "error", text: "Failed to save AI provider configuration." });
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Save failed";
      setMessage({ type: "error", text: msg });
    } finally {
      setSaving(false);
    }
  };

  const isConfiguredForThisProvider =
    (selectedProvider === savedAiProvider && hasCustomApiKey) ||
    configuredProviders.includes(selectedProvider);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-sm text-zinc-500 font-mono">
        <RefreshCw className="w-4 h-4 animate-spin mr-2 text-purple-400" />
        Loading AI engine providers...
      </div>
    );
  }

  const selectedProviderInfo = aiProviders.find((p) => p.id === selectedProvider);
  const caps = selectedProviderInfo?.capabilities;

  return (
    <div className="space-y-8 pb-16 max-w-5xl">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-white/[0.08]">
        <div>
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md bg-purple-500/10 border border-purple-500/20 text-purple-400 text-xs font-mono uppercase tracking-wider mb-2">
            <Cpu className="w-3.5 h-3.5" />
            <span>Pluggable Multi-Provider LLM Gateway</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">AI Provider Configuration</h1>
          <p className="text-sm text-zinc-400 mt-1">
            Choose and configure the LLM backend for resume skill extraction, job enrichment, and explainable matching.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleTestAiConnection}
            disabled={testingAi}
            className="inline-flex items-center gap-1.5 px-3 py-2 bg-obsidian-900 hover:bg-obsidian-850 border border-white/[0.08] text-zinc-300 rounded-xl text-xs font-medium transition-colors"
          >
            <Zap className={`w-3.5 h-3.5 ${testingAi ? "animate-pulse text-amber-400" : "text-amber-400"}`} />
            <span>{testingAi ? "Testing Ping..." : "Test Connection"}</span>
          </button>
          <button
            onClick={handleSaveAiProvider}
            disabled={saving}
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white rounded-xl text-xs font-semibold shadow-sm transition-all"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>{saving ? "Saving..." : "Save AI Provider"}</span>
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

      {/* Live Test Diagnostic Output */}
      {aiTestResult && (
        <div
          className={`p-4 rounded-xl text-xs border backdrop-blur-md flex items-start gap-3 ${
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
            <div className="text-[11px] opacity-80 mt-1 space-y-0.5">
              {aiTestResult.latency_ms !== undefined && <div>Latency: {aiTestResult.latency_ms} ms</div>}
              {aiTestResult.sample_response && <div>Sample Response: &quot;{aiTestResult.sample_response}&quot;</div>}
              {aiTestResult.error && <div>Error: {aiTestResult.error}</div>}
            </div>
          </div>
        </div>
      )}

      {/* Provider Selector Card */}
      <div className="p-6 rounded-2xl bg-obsidian-900/60 border border-white/[0.08] shadow-surface-inset space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-white">Select AI Engine</h2>
            <p className="text-xs text-zinc-400 mt-0.5">
              Local Ollama runs completely private with zero cloud cost. Cloud models offer rapid latency and frontier reasoning.
            </p>
          </div>
          <span className="px-2.5 py-1 rounded-full text-[10px] font-mono bg-purple-500/10 text-purple-300 border border-purple-500/20">
            {savedAiProvider ? savedAiProvider.toUpperCase() : "OLLAMA"} ACTIVE
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {(aiProviders.length > 0
            ? aiProviders
            : [
                { id: "ollama", name: "Ollama (Local)", type: "local", default_model: "qwen3.5:9b", configured: true, description: "Zero cost, private" },
                { id: "openai", name: "OpenAI", type: "cloud", default_model: "gpt-4o-mini", configured: false, description: "GPT-4o, o1/o3-mini" },
                { id: "gemini", name: "Google Gemini", type: "cloud", default_model: "gemini-2.0-flash", configured: false, description: "gemini-2.0-flash" },
                { id: "anthropic", name: "Claude (Anthropic)", type: "cloud", default_model: "claude-3-5-haiku", configured: false, description: "Claude 3.5 Haiku" },
                { id: "groq", name: "Groq", type: "cloud", default_model: "llama-3.3-70b-versatile", configured: false, description: "Llama 3.3 70B fast LPU" },
                { id: "openrouter", name: "OpenRouter", type: "cloud", default_model: "meta-llama/llama-3.3-70b", configured: false, description: "200+ models gateway" },
                { id: "cerebras", name: "Cerebras", type: "cloud", default_model: "llama3.3-70b", configured: false, description: "Wafer-scale compute" },
                { id: "mistral", name: "Mistral", type: "cloud", default_model: "mistral-small-latest", configured: false, description: "Mistral & Codestral" },
                { id: "nvidia-nim", name: "NVIDIA NIM", type: "cloud", default_model: "meta/llama-3.3-70b-instruct", configured: false, description: "Hosted or on-prem" },
                { id: "opencode", name: "OpenCode", type: "local", default_model: "opencode-default", configured: false, description: "Coding agent runtime" },
                { id: "openai-compatible", name: "Custom / Proxy", type: "cloud", default_model: "auto/best-fast", configured: false, description: "vLLM, LM Studio, proxy" },
              ]
          ).map((item) => {
            const isSelected = selectedProvider.toLowerCase() === item.id.toLowerCase();
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
                  <div className="flex items-center gap-1">
                    {configuredProviders.includes(item.id) && item.id !== "ollama" && (
                      <span className="text-[8px] font-mono uppercase px-1 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                        Saved ✓
                      </span>
                    )}
                    <span
                      className={`text-[9px] font-mono uppercase px-1.5 py-0.5 rounded ${
                        item.type === "local"
                          ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                          : "bg-zinc-800 text-zinc-400"
                      }`}
                    >
                      {item.type}
                    </span>
                  </div>
                </div>
                <div className="text-[11px] text-zinc-400 mt-1 line-clamp-2">{item.description}</div>
              </button>
            );
          })}
        </div>

        {/* Capabilities Row */}
        {caps && (
          <div className="flex flex-wrap items-center gap-2 pt-1 pb-1">
            <span className="text-[10px] font-mono uppercase text-zinc-500 tracking-wider mr-1">Capabilities:</span>
            <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${caps.supports_streaming ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" : "bg-white/[0.02] text-zinc-600 border-white/[0.04]"}`}>
              {caps.supports_streaming ? "✓ Streaming" : "✕ Streaming"}
            </span>
            <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${caps.supports_tools ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" : "bg-white/[0.02] text-zinc-600 border-white/[0.04]"}`}>
              {caps.supports_tools ? "✓ Tool Calling" : "✕ Tool Calling"}
            </span>
            <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${caps.supports_structured_output ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" : "bg-white/[0.02] text-zinc-600 border-white/[0.04]"}`}>
              {caps.supports_structured_output ? "✓ Structured Output" : "✕ Structured Output"}
            </span>
            <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${caps.supports_vision ? "bg-purple-500/10 text-purple-400 border-purple-500/20" : "bg-white/[0.02] text-zinc-600 border-white/[0.04]"}`}>
              {caps.supports_vision ? "✓ Vision" : "✕ Vision"}
            </span>
            <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${caps.supports_reasoning ? "bg-amber-500/10 text-amber-400 border-amber-500/20" : "bg-white/[0.02] text-zinc-600 border-white/[0.04]"}`}>
              {caps.supports_reasoning ? "✓ Reasoning" : "✕ Reasoning"}
            </span>
          </div>
        )}

        {/* Dynamic Credentials & Model Inputs */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4 border-t border-white/[0.06]">
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
                    : "Leave empty for default"
              }
              value={customBaseUrl}
              onChange={(e) => setCustomBaseUrl(e.target.value)}
              className="w-full px-3 py-2 text-xs bg-obsidian-950/80 border border-white/[0.08] rounded-xl text-white placeholder:text-zinc-600 focus:outline-none focus:border-purple-500/50"
            />
          </div>

          <div>
            <label className="block text-[11px] font-mono text-zinc-400 uppercase tracking-wider mb-1.5 flex items-center gap-1">
              <Key className="w-3 h-3 text-zinc-500" />
              <span>API Key {isConfiguredForThisProvider ? "(Configured ✓)" : ""}</span>
            </label>
            <input
              type="password"
              placeholder={
                selectedProvider === "ollama"
                  ? "Not required for local Ollama"
                  : isConfiguredForThisProvider
                    ? "•••••••••••••••• (Leave blank to keep)"
                    : "Enter API key"
              }
              value={customApiKey}
              disabled={selectedProvider === "ollama"}
              onChange={(e) => setCustomApiKey(e.target.value)}
              className="w-full px-3 py-2 text-xs bg-obsidian-950/80 border border-white/[0.08] rounded-xl text-white placeholder:text-zinc-600 focus:outline-none focus:border-purple-500/50 disabled:opacity-40"
            />
            {isConfiguredForThisProvider && selectedProvider !== "ollama" && (
              <p className="text-[10px] text-zinc-500 mt-1">
                API key currently stored. Fill only to rotate/replace.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
