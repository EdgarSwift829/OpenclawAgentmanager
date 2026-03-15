"use client";

import { useState, useEffect, useCallback } from "react";
import * as api from "@/lib/api";
import type { TKey } from "@/lib/i18n";

interface DirEntry {
  name: string;
  path: string;
  has_children: boolean;
}

interface BrowseResult {
  path: string;
  parent: string | null;
  dirs: DirEntry[];
  exists?: boolean;
}

interface Props {
  currentPath: string;
  onSelect: (path: string) => void;
  onClose: () => void;
  t: (key: TKey) => string;
}

export function FolderBrowser({ currentPath, onSelect, onClose, t }: Props) {
  const [browsePath, setBrowsePath] = useState(currentPath || "");
  const [result, setResult] = useState<BrowseResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadDir = useCallback(async (path?: string) => {
    setLoading(true);
    setError("");
    try {
      const data = await api.browseDirs(path || undefined);
      setResult(data);
      if (data.path) {
        setBrowsePath(data.path);
      }
    } catch (e: any) {
      setError(e.message || "Failed to browse");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDir(currentPath || undefined);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleNavigate = (path: string) => {
    loadDir(path);
  };

  const handleGoUp = () => {
    if (result?.parent) {
      handleNavigate(result.parent);
    }
  };

  const handleSelectCurrent = () => {
    if (browsePath) {
      onSelect(browsePath);
    }
  };

  const handleManualPathSubmit = () => {
    if (browsePath.trim()) {
      loadDir(browsePath.trim());
    }
  };

  return (
    <div className="folder-browser-overlay" onClick={onClose}>
      <div className="folder-browser" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="folder-browser-header">
          <span className="folder-browser-title">{t("browseFolder")}</span>
          <button className="folder-browser-close" onClick={onClose}>
            {"\u2716"}
          </button>
        </div>

        {/* Path bar */}
        <div className="folder-browser-pathbar">
          <button
            className="folder-browser-up-btn"
            onClick={handleGoUp}
            disabled={!result?.parent}
            title={t("folderUp")}
          >
            {"\u2191"}
          </button>
          <input
            className="folder-browser-path-input"
            value={browsePath}
            onChange={(e) => setBrowsePath(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleManualPathSubmit();
            }}
            placeholder={t("folderPath")}
          />
          <button
            className="folder-browser-go-btn"
            onClick={handleManualPathSubmit}
            title={t("folderGo")}
          >
            {"\u21B5"}
          </button>
        </div>

        {/* Error */}
        {error && <div className="folder-browser-error">{error}</div>}

        {/* Directory list */}
        <div className="folder-browser-list">
          {loading && (
            <div className="folder-browser-loading">{t("folderLoading")}</div>
          )}

          {!loading && result && result.dirs.length === 0 && (
            <div className="folder-browser-empty">{t("folderEmpty")}</div>
          )}

          {!loading &&
            result?.dirs.map((dir) => (
              <button
                key={dir.path}
                className="folder-browser-item"
                onClick={() => handleNavigate(dir.path)}
                onDoubleClick={() => onSelect(dir.path)}
                title={dir.path}
              >
                <span className="folder-browser-icon">
                  {dir.has_children ? "\uD83D\uDCC2" : "\uD83D\uDCC1"}
                </span>
                <span className="folder-browser-name">{dir.name}</span>
              </button>
            ))}
        </div>

        {/* Footer actions */}
        <div className="folder-browser-footer">
          <div className="folder-browser-selected">
            {browsePath && (
              <span className="folder-browser-selected-path">{browsePath}</span>
            )}
          </div>
          <div className="folder-browser-actions">
            <button className="folder-browser-cancel-btn" onClick={onClose}>
              {t("cancel")}
            </button>
            <button
              className="folder-browser-select-btn"
              onClick={handleSelectCurrent}
              disabled={!browsePath}
            >
              {t("folderSelect")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
