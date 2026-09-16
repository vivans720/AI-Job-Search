"use client";

import { useEffect, useState, useId } from "react";
import {
  Zap,
  Key,
  Globe,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Sparkles,
  ExternalLink,
  RotateCcw,
  Eye,
  EyeOff,
  Cpu,
  Cloud,
  Layers,
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

interface ProviderFormState {
  model: string;
  baseUrl: string;
  apiKey: string;
  isCustomModel: boolean;
}

const PROVIDER_PRESET_MODELS: Record<string, { id: string; label: string; tag?: string }[]> = {
  ollama: [
    { id: "qwen3.5:9b", label: "Qwen 2.5 9B (Recommended)", tag: "Balanced" },
    { id: "llama3.3:8b", label: "Llama 3.3 8B", tag: "Fast" },
    { id: "mistral:7b", label: "Mistral 7B", tag: "Light" },
    { id: "deepseek-r1:8b", label: "DeepSeek R1 8B", tag: "Reasoning" },
  ],
  openai: [
    { id: "gpt-4o-mini", label: "GPT-4o Mini (Default, Fast)", tag: "Affordable" },
    { id: "gpt-4o", label: "GPT-4o (Frontier Vision)", tag: "High Quality" },
    { id: "o3-mini", label: "o3-mini (Reasoning)", tag: "Reasoning" },
  ],
  gemini: [
    { id: "gemini-2.0-flash", label: "Gemini 2.0 Flash (Fast & Capable)", tag: "Recommended" },
    { id: "gemini-1.5-pro", label: "Gemini 1.5 Pro (Deep Analysis)", tag: "High Quality" },
    { id: "gemini-2.5-flash-lite", label: "Gemini 2.5 Flash Lite", tag: "Ultra Fast" },
  ],
  anthropic: [
    { id: "claude-3-5-haiku-20241022", label: "Claude 3.5 Haiku (Rapid Extraction)", tag: "Speed" },
    { id: "claude-3-7-sonnet-20250219", label: "Claude 3.7 Sonnet (Top Intelligence)", tag: "Frontier" },
  ],
  groq: [
    { id: "llama-3.3-70b-versatile", label: "Llama 3.3 70B Versatile", tag: "Ultra LPU" },
    { id: "mixtral-8x7b-32768", label: "Mixtral 8x7B", tag: "Speed" },
  ],
  openrouter: [
    { id: "meta-llama/llama-3.3-70b-instruct", label: "Meta Llama 3.3 70B", tag: "Auto Route" },
    { id: "deepseek/deepseek-chat", label: "DeepSeek V3", tag: "Budget" },
    { id: "anthropic/claude-3.5-haiku", label: "Claude 3.5 Haiku via Gateway", tag: "Cloud" },
  ],
  cerebras: [
    { id: "llama3.3-70b", label: "Llama 3.3 70B (Wafer-Scale Speed)", tag: "Realtime" },
  ],
  mistral: [
    { id: "mistral-small-latest", label: "Mistral Small", tag: "Fast" },
    { id: "codestral-latest", label: "Codestral", tag: "Code" },
    { id: "mistral-large-latest", label: "Mistral Large", tag: "Frontier" },
  ],
  "nvidia-nim": [
    { id: "meta/llama-3.3-70b-instruct", label: "Meta Llama 3.3 70B Instruct", tag: "Microservice" },
  ],
  opencode: [
    { id: "opencode-default", label: "OpenCode Runtime Default", tag: "Local Gateway" },
  ],
  "openai-compatible": [
    { id: "auto/best-fast", label: "Auto Best Fast", tag: "Custom Proxy" },
  ],
};

const PROVIDER_KEY_DOCS: Record<string, { label: string; url: string }> = {
  openai: { label: "OpenAI API Keys", url: "https://platform.openai.com/api-keys" },
  gemini: { label: "Google AI Studio", url: "https://aistudio.google.com/app/apikey" },
  anthropic: { label: "Anthropic Console", url: "https://console.anthropic.com/settings/keys" },
  groq: { label: "Groq Console", url: "https://console.groq.com/keys" },
  openrouter: { label: "OpenRouter Keys", url: "https://openrouter.ai/keys" },
  cerebras: { label: "Cerebras Cloud", url: "https://cloud.cerebras.ai/" },
  mistral: { label: "Mistral La Plateforme", url: "https://console.mistral.ai/api-keys/" },
  "nvidia-nim": { label: "NVIDIA API Catalog", url: "https://build.nvidia.com/" },
};

const DEFAULT_FALLBACK_PROVIDERS: AIProviderInfo[] = [
  { id: "ollama", name: "Ollama (Local LLM)", type: "local", default_model: "qwen3.5:9b", configured: true, description: "Local-first private inference. Zero cloud cost, high privacy." },
  { id: "openai", name: "OpenAI", type: "cloud", default_model: "gpt-4o-mini", configured: false, description: "Official OpenAI API (GPT-4o, GPT-4o-mini, o1/o3-mini)." },
  { id: "gemini", name: "Google AI / Gemini", type: "cloud", default_model: "gemini-2.0-flash", configured: false, description: "Google Gemini via official OpenAI-compatible endpoint." },
  { id: "anthropic", name: "Anthropic Claude", type: "cloud", default_model: "claude-3-5-haiku", configured: false, description: "Anthropic Claude 3.5 Haiku / Sonnet via native Messages API." },
  { id: "groq", name: "Groq", type: "cloud", default_model: "llama-3.3-70b-versatile", configured: false, description: "Ultra-fast LPU inference for Llama 3.3, Mixtral, and Gemma models." },
  { id: "openrouter", name: "OpenRouter", type: "cloud", default_model: "meta-llama/llama-3.3-70b", configured: false, description: "Unified gateway with full model routing across 200+ models." },
  { id: "cerebras", name: "Cerebras", type: "cloud", default_model: "llama3.3-70b", configured: false, description: "Wafer-scale high-throughput inference for Llama 3 models." },
  { id: "mistral", name: "Mistral AI", type: "cloud", default_model: "mistral-small-latest", configured: false, description: "Mistral Small, Large, and Codestral inference models." },
  { id: "nvidia-nim", name: "NVIDIA NIM", type: "cloud", default_model: "meta/llama-3.3-70b-instruct", configured: false, description: "NVIDIA NIM microservices hosted on API catalog or self-hosted." },
  { id: "opencode", name: "OpenCode", type: "local", default_model: "opencode-default", configured: false, description: "OpenCode AI coding agent gateway and local runtime integration." },
  { id: "openai-compatible", name: "Custom / Proxy", type: "cloud", default_model: "auto/best-fast", configured: false, description: "Any custom OpenAI-compatible endpoint (vLLM, LM Studio, LiteLLM)." },
];

export default function AIProviderPage() {
  const modelSelectId = useId();
  const customModelInputId = useId();
  const baseUrlInputId = useId();
  const apiKeyInputId = useId();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testingAi, setTestingAi] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const [aiProviders, setAiProviders] = useState<AIProviderInfo[]>(DEFAULT_FALLBACK_PROVIDERS);
  const [selectedProvider, setSelectedProvider] = useState<string>("ollama");
  const [savedAiProvider, setSavedAiProvider] = useState<string | null>(null);
  const [hasCustomApiKey, setHasCustomApiKey] = useState<boolean>(false);
  const [configuredProviders, setConfiguredProviders] = useState<string[]>([]);
  const [activeTab, setActiveTab] = useState<"all" | "local" | "cloud" | "gateway">("all");
  const [showApiKey, setShowApiKey] = useState<boolean>(false);

  // Per-provider isolated state map to prevent state leakage
  const [providerStates, setProviderStates] = useState<Record<string, ProviderFormState>>({});

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

      let loadedProviders = DEFAULT_FALLBACK_PROVIDERS;
      if (aiRes.ok) {
        const list = await aiRes.json();
        if (Array.isArray(list) && list.length > 0) {
          loadedProviders = list;
          setAiProviders(list);
        }
      }

      if (prefRes.ok) {
        const data = await prefRes.json();
        const activeProv = data.ai_provider || "ollama";
        setSelectedProvider(activeProv);
        setSavedAiProvider(activeProv);

        if (data.has_custom_api_key) setHasCustomApiKey(true);
        if (data.configured_providers) setConfiguredProviders(data.configured_providers);

        // Pre-populate state for the currently active provider from saved preferences
        const initialStates: Record<string, ProviderFormState> = {};
        loadedProviders.forEach((p) => {
          const isSaved = p.id === activeProv;
          const currentModel = isSaved && data.ai_model ? data.ai_model : p.default_model;
          const presets = PROVIDER_PRESET_MODELS[p.id] || [];
          const isPreset = presets.some((m) => m.id === currentModel);

          initialStates[p.id] = {
            model: currentModel,
            baseUrl: isSaved && data.ai_base_url ? data.ai_base_url : p.base_url || "",
            apiKey: "",
            isCustomModel: !isPreset && Boolean(currentModel),
          };
        });
        setProviderStates(initialStates);
      }
    } catch {
      // Offline fallback initialized via defaults
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProvidersAndPrefs();
  }, []);

  // Current active form state helper
  const currentState: ProviderFormState = providerStates[selectedProvider] || {
    model: aiProviders.find((p) => p.id === selectedProvider)?.default_model || "",
    baseUrl: "",
    apiKey: "",
    isCustomModel: false,
  };

  const updateCurrentState = (partial: Partial<ProviderFormState>) => {
    setProviderStates((prev) => ({
      ...prev,
      [selectedProvider]: {
        ...(prev[selectedProvider] || {
          model: aiProviders.find((p) => p.id === selectedProvider)?.default_model || "",
          baseUrl: "",
          apiKey: "",
          isCustomModel: false,
        }),
        ...partial,
      },
    }));
  };

  const handleResetCurrentProvider = () => {
    const defaultInfo = aiProviders.find((p) => p.id === selectedProvider);
    if (!defaultInfo) return;
    updateCurrentState({
      model: defaultInfo.default_model,
      baseUrl: defaultInfo.base_url || "",
      apiKey: "",
      isCustomModel: false,
    });
    setAiTestResult(null);
    setMessage({ type: "success", text: `Reset configuration for ${defaultInfo.name} to defaults.` });
  };

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
          model: currentState.model.trim() || undefined,
          base_url: currentState.baseUrl.trim() || undefined,
          api_key: currentState.apiKey.trim() || undefined,
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
        ai_model: currentState.model.trim() || null,
        ai_base_url: currentState.baseUrl.trim() || null,
      };

      if (currentState.apiKey.trim()) {
        payload.ai_api_key = currentState.apiKey.trim();
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
        updateCurrentState({ apiKey: "" });
        setMessage({
          type: "success",
          text: `Active AI Provider set to ${selectedProvider.toUpperCase()}${
            currentState.model ? ` (${currentState.model})` : ""
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
    configuredProviders.includes(selectedProvider) ||
    selectedProvider === "ollama";

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
  const presets = PROVIDER_PRESET_MODELS[selectedProvider] || [];
  const docLink = PROVIDER_KEY_DOCS[selectedProvider];

  const filteredProviders = aiProviders.filter((p) => {
    if (activeTab === "local") return p.type === "local";
    if (activeTab === "cloud") return p.type === "cloud" && p.id !== "openai-compatible" && p.id !== "openrouter";
    if (activeTab === "gateway") return p.id === "openrouter" || p.id === "openai-compatible" || p.id === "nvidia-nim";
    return true;
  });

  return (
    <div className="space-y-8 pb-16 max-w-5xl">
      {/* Header */}
      <div className="pb-6 border-b border-slate-200 space-y-1">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-semibold text-emerald-700 tracking-wider uppercase font-mono">
            Intelligence Gateway
          </span>
          <span className="text-slate-300">•</span>
          <span className="text-[10px] text-slate-500">
            Current Active Engine: <strong className="text-slate-800 uppercase">{savedAiProvider || "Ollama"}</strong>
          </span>
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">AI Provider Configuration</h1>
        <p className="text-xs text-slate-500 max-w-2xl leading-relaxed">
          Select and calibrate the LLM inference engine powering resume skill extraction, company tech radar, and job match explanations.
        </p>
      </div>

      {/* Global Status Banner */}
      {message && (
        <div
          role="status"
          className={`p-4 rounded-xl flex items-center gap-3 text-xs border transition-all ${
            message.type === "success"
              ? "bg-emerald-50 border-emerald-200 text-emerald-800"
              : "bg-rose-50 border-rose-200 text-rose-800"
          }`}
        >
          {message.type === "success" ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          ) : (
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
          )}
          <span className="font-semibold">{message.text}</span>
        </div>
      )}

      {/* Connection Ping Diagnostic Output */}
      {aiTestResult && (
        <div
          role="status"
          className={`p-4 rounded-xl text-xs border flex items-start gap-3 transition-all ${
            aiTestResult.reachable
              ? "bg-emerald-50 border-emerald-200 text-emerald-800"
              : "bg-rose-50 border-rose-200 text-rose-800"
          }`}
        >
          {aiTestResult.reachable ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-600 mt-0.5 shrink-0" />
          ) : (
            <AlertCircle className="w-4 h-4 text-rose-600 mt-0.5 shrink-0" />
          )}
          <div className="flex-1 font-mono">
            <div className="font-bold flex items-center justify-between">
              <span>{aiTestResult.reachable ? "Connection Test Passed" : "Connection Test Failed"}</span>
              {aiTestResult.latency_ms !== undefined && (
                <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-100/70 text-emerald-800">
                  {aiTestResult.latency_ms} ms
                </span>
              )}
            </div>
            <div className="text-[11px] opacity-80 mt-1 space-y-0.5">
              {aiTestResult.sample_response && (
                <div>Response Sample: &quot;{aiTestResult.sample_response}&quot;</div>
              )}
              {aiTestResult.error && (
                <div className="text-rose-700 font-sans mt-1">
                  <strong>Cause:</strong> {aiTestResult.error}
                  <span className="block text-[10px] text-rose-600 mt-0.5 font-mono">
                    Verify that your API key or local base URL server is online and allows inbound queries.
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Step 1: Provider Selection */}
      <section aria-labelledby="provider-heading" className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 id="provider-heading" className="text-sm font-bold text-slate-900">
              1. Choose Engine
            </h2>
            <p className="text-xs text-slate-500">
              Select an engine to inspect or update its settings below.
            </p>
          </div>

          {/* Group Filter Tabs */}
          <div className="flex items-center gap-1 p-1 bg-slate-100 rounded-xl text-[11px] font-medium text-slate-600">
            <button
              onClick={() => setActiveTab("all")}
              className={`px-3 py-1 rounded-lg transition-all ${
                activeTab === "all" ? "bg-white text-slate-900 shadow-xs font-semibold" : "hover:text-slate-900"
              }`}
            >
              All (11)
            </button>
            <button
              onClick={() => setActiveTab("local")}
              className={`px-3 py-1 rounded-lg flex items-center gap-1 transition-all ${
                activeTab === "local" ? "bg-white text-slate-900 shadow-xs font-semibold" : "hover:text-slate-900"
              }`}
            >
              <Cpu className="w-3 h-3 text-emerald-600" />
              <span>Local / Free</span>
            </button>
            <button
              onClick={() => setActiveTab("cloud")}
              className={`px-3 py-1 rounded-lg flex items-center gap-1 transition-all ${
                activeTab === "cloud" ? "bg-white text-slate-900 shadow-xs font-semibold" : "hover:text-slate-900"
              }`}
            >
              <Cloud className="w-3 h-3 text-sky-600" />
              <span>Cloud Frontier</span>
            </button>
            <button
              onClick={() => setActiveTab("gateway")}
              className={`px-3 py-1 rounded-lg flex items-center gap-1 transition-all ${
                activeTab === "gateway" ? "bg-white text-slate-900 shadow-xs font-semibold" : "hover:text-slate-900"
              }`}
            >
              <Layers className="w-3 h-3 text-indigo-600" />
              <span>Gateways</span>
            </button>
          </div>
        </div>

        {/* Provider Cards */}
        <div
          role="radiogroup"
          aria-labelledby="provider-heading"
          className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3"
        >
          {filteredProviders.map((item) => {
            const isSelected = selectedProvider.toLowerCase() === item.id.toLowerCase();
            const isSaved = savedAiProvider?.toLowerCase() === item.id.toLowerCase();
            const hasKey = configuredProviders.includes(item.id);

            return (
              <button
                key={item.id}
                role="radio"
                aria-checked={isSelected}
                onClick={() => {
                  setSelectedProvider(item.id);
                  setAiTestResult(null);
                  setMessage(null);
                }}
                className={`p-3.5 rounded-xl border text-left transition-all relative flex flex-col justify-between ${
                  isSelected
                    ? "bg-emerald-50/70 border-emerald-400 ring-2 ring-emerald-400/20 shadow-xs"
                    : "bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50/70"
                }`}
              >
                <div>
                  <div className="flex items-start justify-between gap-2">
                    <span className={`text-xs font-bold leading-tight ${isSelected ? "text-emerald-950" : "text-slate-900"}`}>
                      {item.name}
                    </span>
                    <span
                      className={`text-[9px] font-mono uppercase px-1.5 py-0.5 rounded font-medium shrink-0 ${
                        item.type === "local"
                          ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                          : "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {item.type}
                    </span>
                  </div>

                  <p className="text-[11px] text-slate-500 mt-1.5 line-clamp-2 leading-relaxed">
                    {item.description}
                  </p>
                </div>

                <div className="mt-3 pt-2 border-t border-slate-100 flex items-center justify-between text-[10px]">
                  {isSaved ? (
                    <span className="font-mono uppercase font-semibold text-emerald-700 flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                      Active
                    </span>
                  ) : hasKey ? (
                    <span className="font-mono text-slate-500 flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                      Configured
                    </span>
                  ) : item.requires_api_key ? (
                    <span className="text-slate-400 font-mono">Key required</span>
                  ) : (
                    <span className="text-emerald-600 font-mono">Ready (Local)</span>
                  )}

                  {isSelected && (
                    <span className="text-emerald-700 font-semibold text-[10px]">Selected</span>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      </section>

      {/* Step 2: Configuration Details for Selected Provider */}
      <section
        aria-labelledby="config-heading"
        className="p-6 rounded-2xl bg-white border border-slate-200 shadow-card-subtle space-y-6"
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-100">
          <div>
            <div className="flex items-center gap-2">
              <h2 id="config-heading" className="text-sm font-bold text-slate-900">
                2. Calibrate {selectedProviderInfo?.name || selectedProvider}
              </h2>
              {isConfiguredForThisProvider && (
                <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-50 text-emerald-700 border border-emerald-200 font-semibold">
                  Credentials Ready
                </span>
              )}
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Tune model identifiers, custom proxy endpoints, and access tokens for this engine.
            </p>
          </div>

          <button
            onClick={handleResetCurrentProvider}
            type="button"
            className="inline-flex items-center gap-1 text-[11px] text-slate-500 hover:text-slate-800 transition-colors self-start sm:self-auto"
          >
            <RotateCcw className="w-3 h-3" />
            <span>Reset to defaults</span>
          </button>
        </div>

        {/* Capabilities row for selected provider */}
        {caps && (
          <div className="bg-slate-50 p-3 rounded-xl border border-slate-100 flex flex-wrap items-center gap-2">
            <span className="text-[10px] font-mono uppercase text-slate-500 tracking-wider mr-1">
              Capabilities:
            </span>
            <span
              className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                caps.supports_streaming
                  ? "bg-white text-emerald-700 border-emerald-200 font-medium"
                  : "bg-white/60 text-slate-400 border-slate-200"
              }`}
            >
              {caps.supports_streaming ? "✓ Streaming" : "✕ Streaming"}
            </span>
            <span
              className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                caps.supports_tools
                  ? "bg-white text-emerald-700 border-emerald-200 font-medium"
                  : "bg-white/60 text-slate-400 border-slate-200"
              }`}
            >
              {caps.supports_tools ? "✓ Tool Calling" : "✕ Tool Calling"}
            </span>
            <span
              className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                caps.supports_structured_output
                  ? "bg-white text-emerald-700 border-emerald-200 font-medium"
                  : "bg-white/60 text-slate-400 border-slate-200"
              }`}
            >
              {caps.supports_structured_output ? "✓ Structured JSON" : "✕ Structured JSON"}
            </span>
            <span
              className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                caps.supports_vision
                  ? "bg-white text-indigo-700 border-indigo-200 font-medium"
                  : "bg-white/60 text-slate-400 border-slate-200"
              }`}
            >
              {caps.supports_vision ? "✓ Vision" : "✕ Vision"}
            </span>
            <span
              className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                caps.supports_reasoning
                  ? "bg-white text-amber-700 border-amber-200 font-medium"
                  : "bg-white/60 text-slate-400 border-slate-200"
              }`}
            >
              {caps.supports_reasoning ? "✓ Reasoning" : "✕ Reasoning"}
            </span>
          </div>
        )}

        {/* Calibration Inputs */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {/* Model Selection */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label htmlFor={modelSelectId} className="block text-[11px] font-semibold text-slate-700 uppercase tracking-wider">
                Model Selection
              </label>
              <button
                type="button"
                onClick={() => updateCurrentState({ isCustomModel: !currentState.isCustomModel })}
                className="text-[10px] text-emerald-600 hover:text-emerald-700 underline font-mono"
              >
                {currentState.isCustomModel ? "Choose preset" : "Custom override"}
              </button>
            </div>

            {currentState.isCustomModel ? (
              <input
                id={customModelInputId}
                type="text"
                placeholder={selectedProviderInfo?.default_model || "Enter exact model ID"}
                value={currentState.model}
                onChange={(e) => updateCurrentState({ model: e.target.value })}
                className="w-full px-3.5 py-2 text-xs bg-white border border-slate-200 rounded-xl text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 shadow-xs font-mono"
              />
            ) : (
              <select
                id={modelSelectId}
                value={currentState.model}
                onChange={(e) => updateCurrentState({ model: e.target.value })}
                className="w-full px-3.5 py-2 text-xs bg-white border border-slate-200 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 shadow-xs cursor-pointer"
              >
                {presets.map((preset) => (
                  <option key={preset.id} value={preset.id}>
                    {preset.label} ({preset.id})
                  </option>
                ))}
                {!presets.some((p) => p.id === currentState.model) && currentState.model && (
                  <option value={currentState.model}>{currentState.model} (Saved)</option>
                )}
              </select>
            )}
            <p className="text-[10px] text-slate-500">
              Default: <code className="font-mono text-slate-700">{selectedProviderInfo?.default_model}</code>
            </p>
          </div>

          {/* Base URL Input */}
          <div className="space-y-1.5">
            <label htmlFor={baseUrlInputId} className="block text-[11px] font-semibold text-slate-700 uppercase tracking-wider flex items-center gap-1">
              <Globe className="w-3 h-3 text-slate-400" />
              <span>Base URL (Optional)</span>
            </label>
            <input
              id={baseUrlInputId}
              type="text"
              placeholder={
                selectedProvider === "ollama"
                  ? "http://localhost:11434/v1"
                  : selectedProvider === "gemini"
                  ? "https://generativelanguage.googleapis.com/v1beta/openai/"
                  : "Leave blank for standard API"
              }
              value={currentState.baseUrl}
              onChange={(e) => updateCurrentState({ baseUrl: e.target.value })}
              className="w-full px-3.5 py-2 text-xs bg-white border border-slate-200 rounded-xl text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 shadow-xs font-mono"
            />
            <p className="text-[10px] text-slate-500">
              Override for local proxies or self-hosted vLLM/Ollama endpoints.
            </p>
          </div>

          {/* API Key Input */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label htmlFor={apiKeyInputId} className="block text-[11px] font-semibold text-slate-700 uppercase tracking-wider flex items-center gap-1">
                <Key className="w-3 h-3 text-slate-400" />
                <span>API Key</span>
              </label>

              {docLink && (
                <a
                  href={docLink.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-0.5 text-[10px] text-emerald-600 hover:text-emerald-700 hover:underline font-medium"
                >
                  <span>{docLink.label}</span>
                  <ExternalLink className="w-2.5 h-2.5" />
                </a>
              )}
            </div>

            <div className="relative">
              <input
                id={apiKeyInputId}
                type={showApiKey ? "text" : "password"}
                placeholder={
                  selectedProvider === "ollama" || selectedProvider === "opencode"
                    ? "Not required for local runtime"
                    : isConfiguredForThisProvider
                    ? "•••••••••••••••• (Leave blank to keep current)"
                    : "Paste API key"
                }
                value={currentState.apiKey}
                disabled={selectedProvider === "ollama" || selectedProvider === "opencode"}
                onChange={(e) => updateCurrentState({ apiKey: e.target.value })}
                className="w-full pl-3.5 pr-9 py-2 text-xs bg-white border border-slate-200 rounded-xl text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 shadow-xs disabled:opacity-50 disabled:bg-slate-50 font-mono"
              />
              {selectedProvider !== "ollama" && selectedProvider !== "opencode" && (
                <button
                  type="button"
                  onClick={() => setShowApiKey(!showApiKey)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                  aria-label={showApiKey ? "Hide API key" : "Show API key"}
                >
                  {showApiKey ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                </button>
              )}
            </div>

            <p className="text-[10px] text-slate-500">
              {isConfiguredForThisProvider && selectedProvider !== "ollama" && selectedProvider !== "opencode"
                ? "Key saved in secure vault. Enter value only to replace."
                : selectedProvider === "ollama"
                ? "Zero cloud tokens. Runs on your machine."
                : "Keys are encrypted at rest."}
            </p>
          </div>
        </div>

        {/* Step 3: Inline Primary Action Bar */}
        <div className="pt-4 border-t border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="text-xs text-slate-500">
            Click <strong>Test Connection</strong> to ping before activating as primary engine.
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleTestAiConnection}
              disabled={testingAi}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 rounded-xl text-xs font-semibold transition-colors shadow-xs"
            >
              <Zap className={`w-3.5 h-3.5 ${testingAi ? "animate-pulse text-amber-500" : "text-amber-500"}`} />
              <span>{testingAi ? "Pinging Engine..." : "Test Connection"}</span>
            </button>

            <button
              onClick={handleSaveAiProvider}
              disabled={saving}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-xl text-xs font-semibold shadow-xs transition-all"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>{saving ? "Saving..." : `Set Active (${selectedProviderInfo?.name || selectedProvider})`}</span>
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
