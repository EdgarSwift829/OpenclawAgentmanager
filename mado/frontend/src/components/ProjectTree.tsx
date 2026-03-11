"use client";

import { useState, useEffect } from "react";
import * as api from "@/lib/api";
import { useI18n } from "@/lib/i18n";

interface Props {
  projects: string[];
  activeProject: string | null;
  onSelect: (id: string) => void;
  onRefresh: () => void;
  runStatuses?: Record<string, string>;
}

const STATUS_ICONS: Record<string, string> = {
  running: "\u25B6",
  completed: "\u2714",
  error: "\u2716",
  cancelled: "\u25A0",
};

export function ProjectTree({
  projects,
  activeProject,
  onSelect,
  onRefresh,
  runStatuses = {},
}: Props) {
  const { t } = useI18n();
  const [newId, setNewId] = useState("");
  const [creating, setCreating] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [showFolderSettings, setShowFolderSettings] = useState(false);
  const [folderPath, setFolderPath] = useState("");
  const [savedPath, setSavedPath] = useState("");
  const [saving, setSaving] = useState(false);

  // Load current projects root on mount
  useEffect(() => {
    api.getProjectsRoot()
      .then((data) => {
        setFolderPath(data.projects_root || "");
        setSavedPath(data.projects_root || "");
      })
      .catch(() => {});
  }, []);

  const handleCreate = async () => {
    if (!newId.trim()) return;
    setCreating(true);
    try {
      await api.createProject(newId.trim(), "");
      setNewId("");
      onRefresh();
      onSelect(newId.trim());
    } catch (e: any) {
      alert(e.message);
    } finally {
      setCreating(false);
    }
  };

  const handleFolderSave = async () => {
    if (!folderPath.trim()) return;
    setSaving(true);
    try {
      const data = await api.setProjectsRoot(folderPath.trim());
      setSavedPath(data.projects_root);
      setFolderPath(data.projects_root);
      setShowFolderSettings(false);
      onRefresh();
    } catch (e: any) {
      alert(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="project-tree">
      <div className="tree-header" onClick={() => setCollapsed(!collapsed)}>
        <span className="tree-chevron">{collapsed ? "\u25B6" : "\u25BC"}</span>
        <span className="tree-title">{t("projects")}</span>
        <span className="tree-count">{projects.length}</span>
      </div>

      {!collapsed && (
        <>
          {/* Folder settings toggle */}
          <button
            className="tree-folder-btn"
            onClick={() => setShowFolderSettings(!showFolderSettings)}
            title={t("projectsFolder")}
          >
            {showFolderSettings ? "\u25B2" : "\u{1F4C1}"} {t("projectsFolder")}
          </button>

          {showFolderSettings && (
            <div className="tree-folder-settings">
              <input
                className="tree-input tree-folder-input"
                placeholder={t("folderPath")}
                value={folderPath}
                onChange={(e) => setFolderPath(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleFolderSave()}
              />
              <div className="tree-folder-actions">
                <button
                  className="tree-add-btn"
                  onClick={handleFolderSave}
                  disabled={saving || folderPath.trim() === savedPath}
                  title={t("apply")}
                >
                  {"\u2714"}
                </button>
                <button
                  className="tree-folder-cancel"
                  onClick={() => {
                    setFolderPath(savedPath);
                    setShowFolderSettings(false);
                  }}
                  title={t("cancel")}
                >
                  {"\u2716"}
                </button>
              </div>
            </div>
          )}

          <div className="tree-create">
            <input
              placeholder={t("newProject")}
              value={newId}
              onChange={(e) => setNewId(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleCreate()}
              className="tree-input"
            />
            <button
              className="tree-add-btn"
              onClick={handleCreate}
              disabled={creating}
              title={t("createProject")}
            >
              +
            </button>
          </div>

          <div className="tree-list">
            {projects.length === 0 && (
              <div className="tree-empty">{t("noProjects")}</div>
            )}
            {projects.map((p) => {
              const status = runStatuses[p];
              const isActive = p === activeProject;
              return (
                <button
                  key={p}
                  className={`tree-item ${isActive ? "tree-item-active" : ""}`}
                  onClick={() => onSelect(p)}
                >
                  <span className="tree-icon">
                    {status && STATUS_ICONS[status]
                      ? STATUS_ICONS[status]
                      : "\u25CB"}
                  </span>
                  <span className="tree-label">{p}</span>
                  {status && (
                    <span className={`tree-status tree-status-${status}`}>
                      {status}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </>
      )}

      <button
        className="tree-refresh"
        onClick={onRefresh}
        title={t("refreshProjects")}
      >
        {t("refresh")}
      </button>
    </div>
  );
}
