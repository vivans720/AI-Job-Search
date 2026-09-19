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
  RotateCcw,
  Eye,
  EyeOff,
  Cpu,
  Layers,
  Network,
} from "lucide-react";
import { getApiUrl } from "@/lib/api";

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

const COMMON_AGENT_MODELS = [
  { id: "gpt-4o-mini", label: "GPT-4o Mini (Default, Ultra Fast)", tag: "Recommended" },
  { id: "gpt-4o", label: "GPT-4o (Frontier Multi-modal)", tag: "Frontier" },
  { id: "claude-3-5-sonnet-20241022", label: "Claude 3.5 Sonnet (Deep Reasoning)", tag: "Frontier" },
  { id: "claude-3-5-haiku-20241022", label: "Claude 3.5 Haiku (Rapid Extraction)", tag: "Speed" },
  { id: "gemini-2.0-flash", label: "Gemini 2.0 Flash (Fast & Large Context)", tag: "Balanced" },
  { id: "deepseek-r1:8b", label: "DeepSeek R1 8B (Local / Gateway)", tag: "Reasoning" },
  { id: "meta-llama/llama-3.3-70b-instruct", label: "Llama 3.3 70B Instruct", tag: "Open Weights" },
];

export default function AgentConfigurationPage() {
  const [gatewayInfo, setGatewayInfo] = useState<AIProviderInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [model, setModel] = useState("gpt-4o-mini");
  const [baseUrl, setBaseUrl] = useState("http://localhost:8000/v1");
  const [apiKey, setApiKey] = useState("");
  const [showApiKey, setShowApiKey] = useState(false);
  const [hasStoredKey, setHasStoredKey] = useState(false);
  const [isCustomModel, setIsCustomModel] = useState(false);

  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ reachable?: boolean; latency_ms?: number; error?: string; model?: string } | null>(null);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const fetchConfig = async () => {
    setLoading(true);
    try {
      const [aiRes, prefRes] = await Promise.all([
        fetch(getApiUrl("/api/v1/ai/providers")),
        fetch(getApiUrl("/api/v1/preferences")),
      ]);

      if (aiRes.ok) {
        const list = await aiRes.json();
        if (Array.isArray(list) && list.length > 0) {
          const omni = list.find((p) => p.id === "omniroute") || list[0];
          setGatewayInfo(omni);
        }
      }

      if (prefRes.ok) {
        const data = await prefRes.json();
        if (data.ai_model) {
          setModel(data.ai_model);
          const isPreset = COMMON_AGENT_MODELS.some((m) => m.id === data.ai_model);
          setIsCustomModel(!isPreset);
        }
        if (data.ai_base_url) {
          setBaseUrl(data.ai_base_url);
        }
        if (data.has_custom_api_key) {
          setHasStoredKey(true);
        }
      }
    } catch {
      // Backend offline
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchConfig();
  }, []);

  const handleTestConnection = async () => {
    setTesting(true);
    setTestResult(null);
    setMessage(null);
    try {
      const res = await fetch(getApiUrl("/api/v1/ai/test"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: "omniroute",
          model: model.trim() || undefined,
          base_url: baseUrl.trim() || undefined,
          api_key: apiKey.trim() || undefined,
        }),
      });
      const data = await res.json();
      setTestResult(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Connection ping failed";
      setTestResult({ reachable: false, error: msg });
    } finally {
      setTesting(false);
    }
  };

  const handleSaveConfig = async () => {
    setSaving(true);
    setMessage(null);
    try {
      const payload: Record<string, unknown> = {
        ai_provider: "omniroute",
        ai_model: model.trim() || null,
        ai_base_url: baseUrl.trim() || null,
      };

      if (apiKey.trim()) {
        payload.ai_api_key = apiKey.trim();
      }

      const res = await fetch(getApiUrl("/api/v1/preferences"), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        setApiKey("");
        setHasStoredKey(true);
        setMessage({
          type: "success",
          text: `Agent configuration saved successfully. Gateway model: ${model}.`,
        });
      } else {
        setMessage({ type: "error", text: "Failed to save agent configuration." });
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Save failed";
      setMessage({ type: "error", text: msg });
    } finally {
      setSaving(false);
    }
  };

  const handleResetDefaults = async () => {
    try {
      const res = await fetch(getApiUrl("/api/v1/preferences"), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ai_provider: "omniroute",
          ai_model: null,
          ai_base_url: null,
          ai_api_key: null,
        }),
      });
      if (res.ok) {
        await fetchConfig();
        setTestResult(null);
        setMessage({ type: "success", text: "Reset settings to .env OmniRoute configuration." });
      }
    } catch {
      setModel(gatewayInfo?.default_model || "static-best-free");
      setBaseUrl(gatewayInfo?.base_url || "http://localhost:20128/v1");
      setApiKey("");
      setIsCustomModel(false);
      setTestResult(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-sm text-slate-500 font-mono">
        <RefreshCw className="w-4 h-4 animate-spin mr-2 text-emerald-600" />
        Loading Agent Gateway configuration...
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto py-8 px-4 sm:px-6 space-y-8">
      {/* Header Banner */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center justify-center text-emerald-600 shadow-xs shrink-0">
              <Cpu className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <h1 className="text-xl font-bold text-slate-900 tracking-tight">Agent Configuration</h1>
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">
                  <Network className="w-3 h-3" /> {gatewayInfo?.name || "OmniRoute Gateway"}
                </span>
              </div>
              <p className="text-sm text-slate-600 mt-1 leading-relaxed">
                {gatewayInfo?.description || "Configure your unified AI model gateway. OmniRoute centrally routes tasks to underlying models with automatic fallbacks and zero client-side vendor lock-in."}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Status Messages */}
      {message && (
        <div
          className={`p-4 rounded-xl text-sm flex items-center gap-3 border ${
            message.type === "success"
              ? "bg-emerald-50 border-emerald-200 text-emerald-800"
              : "bg-red-50 border-red-200 text-red-800"
          }`}
        >
          {message.type === "success" ? (
            <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
          ) : (
            <AlertCircle className="w-5 h-5 text-red-600 shrink-0" />
          )}
          <span>{message.text}</span>
        </div>
      )}

      {/* Configuration Card */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs space-y-6">
        <div className="border-b border-slate-100 pb-4">
          <h2 className="text-base font-semibold text-slate-900">Gateway Inference Settings</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Requests from Job Intelligence, Resume Parsing, and Agent Tools will pass through this endpoint.
          </p>
        </div>

        <div className="space-y-5">
          {/* OmniRoute Base URL */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
              OmniRoute Gateway Endpoint URL
            </label>
            <div className="relative">
              <Globe className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
              <input
                type="text"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder="http://localhost:8000/v1"
                className="w-full pl-9 pr-4 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 font-mono"
              />
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Standard OpenAI-compatible inference root (default: <code className="text-slate-600">http://localhost:8000/v1</code>).
            </p>
          </div>

          {/* Model Selection */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
                Default Agent Model
              </label>
              <button
                type="button"
                onClick={() => setIsCustomModel(!isCustomModel)}
                className="text-xs text-emerald-600 hover:text-emerald-700 font-medium cursor-pointer"
              >
                {isCustomModel ? "Choose from standard presets" : "Enter custom model ID"}
              </button>
            </div>

            {isCustomModel ? (
              <div className="relative">
                <Sparkles className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                <input
                  type="text"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder="e.g. meta-llama/llama-3.3-70b-instruct or claude-3-7-sonnet"
                  className="w-full pl-9 pr-4 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 font-mono"
                />
              </div>
            ) : (
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 bg-white"
              >
                {COMMON_AGENT_MODELS.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label}
                  </option>
                ))}
              </select>
            )}
            <p className="text-xs text-slate-400 mt-1">
              OmniRoute dynamically routes this model ID to the optimal provider or fallback group.
            </p>
          </div>

          {/* API Key */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
              Gateway API Key <span className="text-slate-400 font-normal lowercase">(optional if local)</span>
            </label>
            <div className="relative">
              <Key className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
              <input
                type={showApiKey ? "text" : "password"}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={hasStoredKey ? "•••••••••••••••• (API key securely stored)" : "Enter OmniRoute bearer token if required"}
                className="w-full pl-9 pr-10 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 font-mono"
              />
              <button
                type="button"
                onClick={() => setShowApiKey(!showApiKey)}
                className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600"
              >
                {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            {hasStoredKey && !apiKey && (
              <p className="text-xs text-emerald-600 mt-1 flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5" /> Stored credentials active in backend.
              </p>
            )}
          </div>
        </div>

        {/* Diagnostic Test Result */}
        {testResult && (
          <div
            className={`p-4 rounded-xl border text-sm ${
              testResult.reachable
                ? "bg-emerald-50/50 border-emerald-200 text-emerald-900"
                : "bg-red-50/50 border-red-200 text-red-900"
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 font-medium">
                {testResult.reachable ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                ) : (
                  <AlertCircle className="w-4 h-4 text-red-600" />
                )}
                {testResult.reachable ? "Gateway Connection Successful" : "Gateway Unreachable"}
              </div>
              {testResult.latency_ms !== undefined && (
                <span className="font-mono text-xs text-slate-500">
                  Latency: {testResult.latency_ms} ms
                </span>
              )}
            </div>
            {testResult.error && (
              <p className="text-xs text-red-700 mt-2 font-mono bg-red-100/60 p-2 rounded-lg break-all">
                {testResult.error}
              </p>
            )}
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-4 border-t border-slate-100">
          <button
            type="button"
            onClick={handleResetDefaults}
            className="text-xs text-slate-500 hover:text-slate-800 flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Reset Defaults
          </button>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleTestConnection}
              disabled={testing}
              className="text-xs font-medium px-4 py-2 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50 focus:outline-none transition-colors flex items-center gap-1.5 disabled:opacity-50"
            >
              {testing ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5 text-amber-500" />}
              Test Connection
            </button>
            <button
              type="button"
              onClick={handleSaveConfig}
              disabled={saving}
              className="text-xs font-semibold px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs focus:outline-none transition-colors flex items-center gap-1.5 disabled:opacity-50"
            >
              {saving ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
              Save Configuration
            </button>
          </div>
        </div>
      </div>

      {/* Architecture Information Card */}
      <div className="bg-slate-50 border border-slate-200 rounded-2xl p-5 text-xs text-slate-600 space-y-2">
        <div className="flex items-center gap-2 font-semibold text-slate-800">
          <Layers className="w-4 h-4 text-emerald-600" />
          <span>Unified Inference Routing Architecture</span>
        </div>
        <p>
          The application delegates model selection, retries, multi-provider credentials, and failovers directly to OmniRoute. Your application code remains cleanly decoupled from specific LLM providers.
        </p>
      </div>
    </div>
  );
}
