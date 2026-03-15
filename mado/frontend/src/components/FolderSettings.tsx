"use client";

import { useState } from "react";
import type { TKey } from "@/lib/i18n";
import { FolderBrowser } from "./FolderBrowser";

type OpenClawStatus = "unknown" | "checking" | "installed" | "not_installed" | "installing" | "error";

interface Props {
  folderPath: string;
  savedPath: string;
  saving: boolean;
  openclawStatus: OpenClawStatus;
  openclawVersion: string | null;
  onFolderPathChange: (value: string) => void;
  onSave: () => void;
  onCancel: () => void;
  onInstallOpenClaw: () => void;
  onRetryOpenClaw: () => void;
  t: (key: TKey) => string;
}

export function FolderSettings({
  folderPath,
  savedPath,
  saving,
  openclawStatus,
  openclawVersion,
  onFolderPathChange,
  onSave,
  onCancel,
  onInstallOpenClaw,
  onRetryOpenClaw,
  t,
}: Props) {
  const [showBrowser, setShowBrowser] = useState(false);

  return (
    <div className="tree-folder-settings">
      <div className="tree-folder-input-row">
        <input
          className="tree-input tree-folder-input"
          placeholder={t("folderPath")}
          value={folderPath}
          onChange={(e) => onFolderPathChange(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && onSave()}
        />
        <button
          className="tree-browse-btn"
          onClick={() => setShowBrowser(true)}
          title={t("browse")}
          type="button"
        >
          {"..."}
        </button>
      </div>
      <div className="tree-folder-actions">
        <button
          className="tree-add-btn"
          onClick={onSave}
          disabled={saving || folderPath.trim() === savedPath}
          title={t("apply")}
        >
          {"\u2714"}
        </button>
        <button
          className="tree-folder-cancel"
          onClick={onCancel}
          title={t("cancel")}
        >
          {"\u2716"}
        </button>
      </div>
      <div className="tree-openclaw-status">
        <span className="tree-openclaw-label">{t("openclawStatus")}:</span>
        {openclawStatus === "checking" && (
          <span className="tree-openclaw-checking">...</span>
        )}
        {openclawStatus === "installed" && (
          <span className="tree-openclaw-ok">
            {t("openclawInstalled")} {openclawVersion && `(${openclawVersion})`}
          </span>
        )}
        {openclawStatus === "not_installed" && (
          <button className="tree-openclaw-install-btn" onClick={onInstallOpenClaw}>
            {t("openclawInstallBtn")}
          </button>
        )}
        {openclawStatus === "installing" && (
          <span className="tree-openclaw-installing">{t("openclawInstalling")}</span>
        )}
        {openclawStatus === "error" && (
          <span className="tree-openclaw-error">
            {t("openclawCheckFailed")}
            <button
              className="tree-openclaw-retry-btn"
              onClick={onRetryOpenClaw}
            >
              {t("refresh")}
            </button>
          </span>
        )}
      </div>
      {showBrowser && (
        <FolderBrowser
          currentPath={folderPath || savedPath}
          onSelect={(path) => {
            onFolderPathChange(path);
            setShowBrowser(false);
          }}
          onClose={() => setShowBrowser(false)}
          t={t}
        />
      )}
    </div>
  );
}
