"use client";

import { useState, useEffect, useCallback } from "react";
import * as api from "@/lib/api";
import { useI18n, type Locale } from "@/lib/i18n";
import { useInlineStatus, StatusIndicator } from "@/components/Toast";

interface ProviderConfig {
  url: string;
}

const PROVIDER_INFO: Record<string, { label: string; defaultPort: string; description: { en: string; ja: string } }> = {
  lmstudio: {
    label: "LM Studio",
    defaultPort: "1234",
    description: { en: "OpenAI-compatible Chat API", ja: "OpenAI互換 Chat API" },
  },
  ollama: {
    label: "Ollama",
    defaultPort: "11434",
    description: { en: "Ollama native API", ja: "Ollama ネイティブAPI" },
  },
  vllm: {
    label: "vLLM",
    defaultPort: "8000",
    description: { en: "OpenAI-compatible Completions API", ja: "OpenAI互換 Completions API" },
  },
  oobabooga: {
    label: "oobabooga",
    defaultPort: "5000",
    description: { en: "text-generation-webui (OpenAI-compatible)", ja: "text-generation-webui (OpenAI互換)" },
  },
};

export function LlmSettings() {
  const { t, locale } = useI18n();
  const loc = locale as Locale;
  const { status, showStatus } = useInlineStatus();
  const [providers, setProviders] = useState<Record<string, ProviderConfig>>({});
  const [editUrls, setEditUrls] = useState<Record<string, string>>({});
  const [testResults, setTestResults] = useState<Record<string, "ok" | "fail" | "testing" | null>>({});

  const load = useCallback(async () => {
    try {
      const res = await api.getProviders();
      setProviders(res.providers || {});
      const urls: Record<string, string> = {};
      for (const [name, cfg] of Object.entries(res.providers || {})) {
        urls[name] = (cfg as ProviderConfig).url;
      }
      setEditUrls(urls);
    } catch (e: any) {
      showStatus(loc === "ja" ? `読み込みエラー: ${e?.message}` : `Load error: ${e?.message}`, "error");
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleSave = async (provider: string) => {
    const url = editUrls[provider];
    if (!url) return;
    try {
      await api.updateProvider(provider, url);
      showStatus(t("urlSaved"), "success");
      setProviders((prev) => ({ ...prev, [provider]: { url } }));
    } catch (e: any) {
      showStatus(t("urlSaveFailed"), "error");
    }
  };

  const handleTest = async (provider: string) => {
    setTestResults((prev) => ({ ...prev, [provider]: "testing" }));
    try {
      const res = await api.testProvider(provider);
      setTestResults((prev) => ({ ...prev, [provider]: res.status === "connected" ? "ok" : "fail" }));
      if (res.status === "connected") {
        showStatus(`${PROVIDER_INFO[provider]?.label || provider}: ${t("connectionOk")}`, "success");
      } else {
        showStatus(`${PROVIDER_INFO[provider]?.label || provider}: ${t("connectionFail")} - ${res.error || ""}`, "error");
      }
    } catch (e: any) {
      setTestResults((prev) => ({ ...prev, [provider]: "fail" }));
      showStatus(`${PROVIDER_INFO[provider]?.label || provider}: ${t("connectionFail")}`, "error");
    }
  };

  const providerNames = Object.keys(PROVIDER_INFO);

  return (
    <div className="llm-settings">
      <div className="llm-settings-header">
        <h3>{t("llmSettings")}</h3>
        <span className="llm-settings-desc">{t("llmSettingsDesc")}</span>
      </div>

      {status && <StatusIndicator status={status} />}

      <div className="llm-provider-list">
        {providerNames.map((name) => {
          const info = PROVIDER_INFO[name];
          const currentUrl = editUrls[name] || "";
          const savedUrl = providers[name]?.url || "";
          const isDirty = currentUrl !== savedUrl;
          const testResult = testResults[name];

          return (
            <div key={name} className="llm-provider-item">
              <div className="llm-provider-name-row">
                <span className="llm-provider-label">{info.label}</span>
                <span className="llm-provider-desc">{info.description[loc]}</span>
                {testResult === "ok" && <span className="llm-status-badge llm-status-ok">{t("connectionOk")}</span>}
                {testResult === "fail" && <span className="llm-status-badge llm-status-fail">{t("connectionFail")}</span>}
              </div>
              <div className="llm-provider-url-row">
                <input
                  className="llm-url-input"
                  type="text"
                  value={currentUrl}
                  onChange={(e) => setEditUrls((prev) => ({ ...prev, [name]: e.target.value }))}
                  placeholder={`http://localhost:${info.defaultPort}`}
                  onKeyDown={(e) => { if (e.key === "Enter" && isDirty) handleSave(name); }}
                />
                <button
                  className="llm-btn llm-btn-save"
                  onClick={() => handleSave(name)}
                  disabled={!isDirty}
                  title={t("save")}
                >
                  {t("save")}
                </button>
                <button
                  className="llm-btn llm-btn-test"
                  onClick={() => handleTest(name)}
                  disabled={testResult === "testing"}
                  title={t("testConnection")}
                >
                  {testResult === "testing" ? t("testing") : t("testConnection")}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
