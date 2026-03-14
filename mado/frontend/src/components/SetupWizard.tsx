"use client";

import { useState } from "react";
import * as api from "@/lib/api";
import { useI18n } from "@/lib/i18n";

interface Props {
  onComplete: () => void;
}

export function SetupWizard({ onComplete }: Props) {
  const { t } = useI18n();
  const [step, setStep] = useState(1);
  const [folderPath, setFolderPath] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // LLM settings
  const [provider, setProvider] = useState("lmstudio");
  const [llmSaved, setLlmSaved] = useState(false);

  const handleSaveFolder = async () => {
    if (!folderPath.trim()) return;
    setSaving(true);
    setError("");
    try {
      await api.setProjectsRoot(folderPath.trim());
      setStep(2);
    } catch (e: any) {
      setError(e.message || "Failed to set projects root");
    } finally {
      setSaving(false);
    }
  };

  const handleSaveLlm = async () => {
    // LLM config is already in models.yaml / agents.yaml
    // Just mark as done for now (provider selection is informational)
    setLlmSaved(true);
  };

  const handleComplete = () => {
    onComplete();
  };

  return (
    <div className="setup-wizard-overlay">
      <div className="setup-wizard">
        {/* Header */}
        <div className="setup-wizard-header">
          <div className="setup-wizard-logo">MADO</div>
          <div className="setup-wizard-welcome">{t("setupWelcome")}</div>
          <div className="setup-wizard-welcome-sub">{t("setupWelcomeSub")}</div>
        </div>

        {/* Step indicators */}
        <div className="setup-wizard-steps">
          <div className={`setup-step-dot ${step >= 1 ? "active" : ""} ${step > 1 ? "done" : ""}`}>1</div>
          <div className="setup-step-line" />
          <div className={`setup-step-dot ${step >= 2 ? "active" : ""}`}>2</div>
        </div>

        {/* Step 1: Folder */}
        {step === 1 && (
          <div className="setup-wizard-body">
            <h3 className="setup-section-title">{t("setupStep1Title")}</h3>
            <p className="setup-section-desc">{t("setupStep1Desc")}</p>
            <label className="setup-label">{t("setupFolderPath")}</label>
            <input
              className="setup-input"
              type="text"
              value={folderPath}
              onChange={(e) => setFolderPath(e.target.value)}
              placeholder={t("setupFolderPlaceholder")}
              onKeyDown={(e) => { if (e.key === "Enter") handleSaveFolder(); }}
              autoFocus
            />
            {error && <div className="setup-error">{error}</div>}
            <button
              className="setup-btn-primary"
              onClick={handleSaveFolder}
              disabled={!folderPath.trim() || saving}
            >
              {saving ? t("setupSaving") : t("setupSave")}
            </button>
          </div>
        )}

        {/* Step 2: LLM */}
        {step === 2 && (
          <div className="setup-wizard-body">
            <h3 className="setup-section-title">{t("setupStep2Title")}</h3>
            <p className="setup-section-desc">{t("setupStep2Desc")}</p>

            <label className="setup-label">{t("setupProvider")}</label>
            <div className="setup-provider-options">
              {["lmstudio", "ollama", "vllm"].map((p) => (
                <button
                  key={p}
                  className={`setup-provider-btn ${provider === p ? "selected" : ""}`}
                  onClick={() => setProvider(p)}
                >
                  {p === "lmstudio" ? "LM Studio" : p === "ollama" ? "Ollama" : "vLLM"}
                  {p === "lmstudio" && <span className="setup-provider-port">:1234</span>}
                  {p === "ollama" && <span className="setup-provider-port">:11434</span>}
                  {p === "vllm" && <span className="setup-provider-port">:8000</span>}
                </button>
              ))}
            </div>

            <div className="setup-llm-info">
              <div className="setup-llm-models">
                <div className="setup-llm-model-row">
                  <span className="setup-llm-model-label">Planning (CTO, Manager)</span>
                  <span className="setup-llm-model-value">qwen3.5-9b</span>
                </div>
                <div className="setup-llm-model-row">
                  <span className="setup-llm-model-label">Execution (Engineer, Tester)</span>
                  <span className="setup-llm-model-value">qwen2.5-coder-7b</span>
                </div>
              </div>
            </div>

            <div className="setup-btn-group">
              <button
                className="setup-btn-secondary"
                onClick={handleComplete}
              >
                {t("setupSkip")}
              </button>
              <button
                className="setup-btn-primary"
                onClick={() => { handleSaveLlm(); handleComplete(); }}
              >
                {t("setupComplete")}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
