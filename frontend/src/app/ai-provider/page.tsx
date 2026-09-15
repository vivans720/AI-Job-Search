"use client";

import { useEffect, useState } from "react";
import {
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
      <div className="flex items-center justify-center py-24 text-sm text-slate-500 font-mono">
        <RefreshCw className="w-4 h-4 animate-spin mr-2 text-emerald-600" />
        Loading AI engine providers...
      </div>
    );
  }

  const selectedProviderInfo = aiProviders.find((p) => p.id === selectedProvider);
  const caps = selectedProviderInfo?.capabilities;

  return (
    <div className="space-y-8 pb-16 max-w-5xl">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-200">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 font-mono tracking-wider uppercase">
              MULTI-PROVIDER LLM GATEWAY
            </span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">AI Provider Configuration</h1>
          <p className="text-xs text-slate-500 max-w-2xl leading-relaxed">
            Choose and configure the LLM backend for resume skill extraction, job enrichment, and explainable matching.
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={handleTestAiConnection}
            disabled={testingAi}
            className="inline-flex items-center gap-1.5 px-3 py-2 bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 rounded-xl text-xs font-semibold transition-colors shadow-xs"
          >
            <Zap className={`w-3.5 h-3.5 ${testingAi ? "animate-pulse text-amber-500" : "text-amber-500"}`} />
            <span>{testingAi ? "Testing Ping..." : "Test Connection"}</span>
          </button>
          <button
            onClick={handleSaveAiProvider}
            disabled={saving}
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-xl text-xs font-semibold shadow-xs transition-all"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>{saving ? "Saving..." : "Save AI Provider"}</span>
          </button>
        </div>
      </div>

      {message && (
        <div
          className={`p-4 rounded-xl flex items-center gap-3 text-xs border transition-all ${
            message.type === "success"
              ? "bg-emerald-50 border-emerald-200 text-emerald-800"
              : "bg-rose-50 border-rose-200 text-rose-800"
          }`}
        >
          {message.type === "success" ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          ) : (
            <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
          )}
          <span className="font-semibold">{message.text}</span>
        </div>
      )}

      {/* Live Test Diagnostic Output */}
      {aiTestResult && (
        <div
          className={`p-4 rounded-xl text-xs border flex items-start gap-3 ${
            aiTestResult.reachable
              ? "bg-emerald-50 border-emerald-200 text-emerald-800"
              : "bg-rose-50 border-rose-200 text-rose-800"
          }`}
        >
          {aiTestResult.reachable ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-600 mt-0.5 flex-shrink-0" />
          ) : (
            <AlertCircle className="w-4 h-4 text-rose-600 mt-0.5 flex-shrink-0" />
          )}
          <div className="flex-1 font-mono">
            <div className="font-bold">
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
      <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-card-subtle space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-slate-900">Select AI Engine</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Local Ollama runs completely private with zero cloud cost. Cloud models offer rapid latency and frontier reasoning.
            </p>
          </div>
          <span className="px-2.5 py-1 rounded-full text-[10px] font-mono bg-emerald-50 text-emerald-700 border border-emerald-200 font-semibold">
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
                    ? "bg-emerald-50/80 border-emerald-300 shadow-xs"
                    : "bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50/60"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-xs font-bold ${isSelected ? "text-emerald-900" : "text-slate-800"}`}>
                    {item.name}
                  </span>
                  <div className="flex items-center gap-1">
                    {configuredProviders.includes(item.id) && item.id !== "ollama" && (
                      <span className="text-[8px] font-mono uppercase px-1 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 font-semibold">
                        Saved ✓
                      </span>
                    )}
                    <span
                      className={`text-[9px] font-mono uppercase px-1.5 py-0.5 rounded font-semibold ${
                        item.type === "local"
                          ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                          : "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {item.type}
                    </span>
                  </div>
                </div>
                <div className="text-[11px] text-slate-500 mt-1 line-clamp-2">{item.description}</div>
              </button>
            );
          })}
        </div>

        {/* Capabilities Row */}
        {caps && (
          <div className="flex flex-wrap items-center gap-2 pt-1 pb-1">
            <span className="text-[10px] font-mono uppercase text-slate-400 tracking-wider mr-1">Capabilities:</span>
            <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${caps.supports_streaming ? "bg-emerald-50 text-emerald-700 border-emerald-200 font-semibold" : "bg-slate-50 text-slate-400 border-slate-200"}`}>
              {caps.supports_streaming ? "✓ Streaming" : "✕ Streaming"}
            </span>
            <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${caps.supports_tools ? "bg-emerald-50 text-emerald-700 border-emerald-200 font-semibold" : "bg-slate-50 text-slate-400 border-slate-200"}`}>
              {caps.supports_tools ? "✓ Tool Calling" : "✕ Tool Calling"}
            </span>
            <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${caps.supports_structured_output ? "bg-emerald-50 text-emerald-700 border-emerald-200 font-semibold" : "bg-slate-50 text-slate-400 border-slate-200"}`}>
              {caps.supports_structured_output ? "✓ Structured Output" : "✕ Structured Output"}
            </span>
            <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${caps.supports_vision ? "bg-indigo-50 text-indigo-700 border-indigo-200 font-semibold" : "bg-slate-50 text-slate-400 border-slate-200"}`}>
              {caps.supports_vision ? "✓ Vision" : "✕ Vision"}
            </span>
            <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${caps.supports_reasoning ? "bg-amber-50 text-amber-700 border-amber-200 font-semibold" : "bg-slate-50 text-slate-400 border-slate-200"}`}>
              {caps.supports_reasoning ? "✓ Reasoning" : "✕ Reasoning"}
            </span>
          </div>
        )}

        {/* Dynamic Credentials & Model Inputs */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4 border-t border-slate-100">
          <div>
            <label className="block text-[11px] font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
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
              className="w-full px-3.5 py-2 text-xs bg-white border border-slate-200 rounded-xl text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-400/20 shadow-xs"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-700 uppercase tracking-wider mb-1.5 flex items-center gap-1">
              <Globe className="w-3 h-3 text-slate-400" />
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
              className="w-full px-3.5 py-2 text-xs bg-white border border-slate-200 rounded-xl text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-400/20 shadow-xs"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-700 uppercase tracking-wider mb-1.5 flex items-center gap-1">
              <Key className="w-3 h-3 text-slate-400" />
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
              className="w-full px-3.5 py-2 text-xs bg-white border border-slate-200 rounded-xl text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-400/20 shadow-xs disabled:opacity-40"
            />
            {isConfiguredForThisProvider && selectedProvider !== "ollama" && (
              <p className="text-[10px] text-slate-500 mt-1">
                API key currently stored. Fill only to rotate/replace.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
