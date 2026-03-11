"use client";

import { useState, useEffect } from "react";
import * as api from "@/lib/api";
import { useI18n } from "@/lib/i18n";

interface ProjectNode {
  project_id: string;
  parent_id: string | null;
  children: string[];
  status: string;
}

interface Props {
  projectTree: ProjectNode[];
  activeProject: string | null;
  onSelect: (id: string) => void;
  onRefresh: () => void;
  runStatuses?: Record<string, string>;
  onStartRun?: (projectId: string) => void;
  onStopRun?: (projectId: string) => void;
  onPauseRun?: (projectId: string) => void;
}

const STATUS_ICONS: Record<string, string> = {
  running: "\u25B6",
  completed: "\u2714",
  error: "\u2716",
  cancelled: "\u25A0",
  archived: "\u{1F4E6}",
};

export function ProjectTree({
  projectTree,
  activeProject,
  onSelect,
  onRefresh,
  runStatuses = {},
  onStartRun,
  onStopRun,
  onPauseRun,
}: Props) {
  const { t } = useI18n();
  const [newId, setNewId] = useState("");
  const [creating, setCreating] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [showFolderSettings, setShowFolderSettings] = useState(false);
  const [folderPath, setFolderPath] = useState("");
  const [savedPath, setSavedPath] = useState("");
  const [saving, setSaving] = useState(false);
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
  const [addingChildTo, setAddingChildTo] = useState<string | null>(null);
  const [childNewId, setChildNewId] = useState("");
  const [showArchived, setShowArchived] = useState(false);
  const [openclawStatus, setOpenclawStatus] = useState<"unknown" | "checking" | "installed" | "not_installed" | "installing" | "error">("unknown");
  const [openclawVersion, setOpenclawVersion] = useState<string | null>(null);

  // Load current projects root on mount
  useEffect(() => {
    api.getProjectsRoot()
      .then((data) => {
        setFolderPath(data.projects_root || "");
        setSavedPath(data.projects_root || "");
      })
      .catch(() => {});
  }, []);

  // Check OpenClaw install status on mount
  useEffect(() => {
    setOpenclawStatus("checking");
    api.checkOpenClaw()
      .then((data) => {
        setOpenclawStatus(data.installed ? "installed" : "not_installed");
        setOpenclawVersion(data.version || null);
      })
      .catch(() => setOpenclawStatus("error"));
  }, []);

  const handleInstallOpenClaw = async () => {
    setOpenclawStatus("installing");
    try {
      const result = await api.installOpenClaw();
      if (result.status === "already_installed" || result.status === "installed") {
        setOpenclawStatus("installed");
        setOpenclawVersion(result.version || null);
      } else {
        setOpenclawStatus("error");
      }
    } catch {
      setOpenclawStatus("error");
    }
  };

  // Build lookup
  const nodeMap = new Map<string, ProjectNode>();
  for (const n of projectTree) nodeMap.set(n.project_id, n);

  // Top-level = no parent (or parent doesn't exist in tree)
  const topLevel = projectTree.filter(
    (n) => !n.parent_id || !nodeMap.has(n.parent_id)
  );

  // Filter archived
  const shouldShow = (n: ProjectNode) =>
    showArchived || n.status !== "archived";

  const totalProjects = projectTree.filter(shouldShow).length;

  const toggleExpand = (id: string) => {
    setExpandedNodes((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleCreate = async (parentId?: string) => {
    const id = parentId ? childNewId.trim() : newId.trim();
    if (!id) return;
    setCreating(true);
    try {
      await api.createProject(id, "", parentId || undefined);
      if (parentId) {
        setChildNewId("");
        setAddingChildTo(null);
        setExpandedNodes((prev) => new Set(prev).add(parentId));
      } else {
        setNewId("");
      }
      onRefresh();
      onSelect(id);
    } catch (e: any) {
      alert(e.message);
    } finally {
      setCreating(false);
    }
  };

  const handleRename = async (oldId: string) => {
    const trimmed = renameValue.trim();
    if (!trimmed || trimmed === oldId) {
      setRenamingId(null);
      return;
    }
    try {
      await api.renameProject(oldId, trimmed);
      setRenamingId(null);
      onRefresh();
      if (activeProject === oldId) onSelect(trimmed);
    } catch (e: any) {
      alert(e.message);
    }
  };

  const handleArchiveToggle = async (projectId: string) => {
    const node = nodeMap.get(projectId);
    if (!node) return;
    const newStatus = node.status === "archived" ? "initialized" : "archived";
    try {
      await api.updateProjectConfig(projectId, { status: newStatus });
      onRefresh();
    } catch (e: any) {
      alert(e.message);
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
      // Re-check OpenClaw after folder change
      setOpenclawStatus("checking");
      api.checkOpenClaw()
        .then((d) => {
          setOpenclawStatus(d.installed ? "installed" : "not_installed");
          setOpenclawVersion(d.version || null);
        })
        .catch(() => setOpenclawStatus("error"));
    } catch (e: any) {
      alert(e.message);
    } finally {
      setSaving(false);
    }
  };

  // Check if a project's parent is running (for child run enablement)
  const isParentRunning = (node: ProjectNode): boolean => {
    if (!node.parent_id) return true; // top-level, no restriction
    return runStatuses[node.parent_id] === "running";
  };

  // Render a project item (recursive for children)
  const renderNode = (node: ProjectNode, depth: number = 0) => {
    if (!shouldShow(node)) return null;

    const p = node.project_id;
    const status = node.status === "archived" ? "archived" : runStatuses[p];
    const isActive = p === activeProject;
    const isRenaming = renamingId === p;
    const hasChildren = node.children.length > 0;
    const isExpanded = expandedNodes.has(p);
    const isArchived = node.status === "archived";
    const childNodes = node.children
      .map((cid) => nodeMap.get(cid))
      .filter(Boolean) as ProjectNode[];

    return (
      <div key={p} className="tree-node-group">
        <div
          className={`tree-item ${isActive ? "tree-item-active" : ""} ${isArchived ? "tree-item-archived" : ""}`}
          style={{ paddingLeft: `${0.5 + depth * 0.75}rem` }}
          onClick={() => !isRenaming && onSelect(p)}
          onDoubleClick={() => {
            setRenamingId(p);
            setRenameValue(p);
          }}
          title={t("renameProject")}
        >
          {/* Expand/collapse toggle for parent nodes */}
          {hasChildren ? (
            <span
              className="tree-expand-toggle"
              onClick={(e) => {
                e.stopPropagation();
                toggleExpand(p);
              }}
            >
              {isExpanded ? "\u25BC" : "\u25B6"}
            </span>
          ) : (
            <span className="tree-expand-spacer" />
          )}

          <span className="tree-icon">
            {status && STATUS_ICONS[status] ? STATUS_ICONS[status] : "\u25CB"}
          </span>

          {isRenaming ? (
            <input
              className="tree-rename-input"
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleRename(p);
                if (e.key === "Escape") setRenamingId(null);
              }}
              onBlur={() => handleRename(p)}
              autoFocus
              onClick={(e) => e.stopPropagation()}
            />
          ) : (
            <span className="tree-label">{p}</span>
          )}

          {hasChildren && !isRenaming && (
            <span className="tree-child-count">{node.children.length}</span>
          )}

          {/* Context actions */}
          {!isRenaming && (
            <span className="tree-actions">
              {/* Run control buttons */}
              {(() => {
                const rs = runStatuses[p];
                const parentOk = isParentRunning(node);
                if (rs === "running") {
                  return (
                    <>
                      <button
                        className="tree-action-btn tree-run-pause"
                        onClick={(e) => { e.stopPropagation(); onPauseRun?.(p); }}
                        title={t("pauseProject")}
                      >
                        {"\u23F8"}
                      </button>
                      <button
                        className="tree-action-btn tree-run-stop"
                        onClick={(e) => { e.stopPropagation(); onStopRun?.(p); }}
                        title={t("stop")}
                      >
                        {"\u25A0"}
                      </button>
                    </>
                  );
                }
                if (rs === "paused") {
                  return (
                    <button
                      className="tree-action-btn tree-run-resume"
                      onClick={(e) => { e.stopPropagation(); onStartRun?.(p); }}
                      title={t("resumeProject")}
                      disabled={!parentOk}
                    >
                      {"\u25B6"}
                    </button>
                  );
                }
                // idle / stopped / completed / error → show play
                return (
                  <button
                    className="tree-action-btn tree-run-start"
                    onClick={(e) => { e.stopPropagation(); onStartRun?.(p); }}
                    title={parentOk ? t("runProject") : t("parentMustRun")}
                    disabled={!parentOk}
                  >
                    {"\u25B6"}
                  </button>
                );
              })()}
              <button
                className="tree-action-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  setAddingChildTo(addingChildTo === p ? null : p);
                  setChildNewId("");
                }}
                title={t("addSubProject")}
              >
                +
              </button>
              <button
                className="tree-action-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  handleArchiveToggle(p);
                }}
                title={isArchived ? t("unarchive") : t("archive")}
              >
                {isArchived ? "\u21A9" : "\u{1F4E6}"}
              </button>
            </span>
          )}

          {status && !isRenaming && status !== "archived" && (
            <span className={`tree-status tree-status-${status}`}>
              {status}
            </span>
          )}
        </div>

        {/* Inline child creation */}
        {addingChildTo === p && (
          <div className="tree-create tree-create-child" style={{ paddingLeft: `${1.25 + depth * 0.75}rem` }}>
            <input
              placeholder={t("newSubProject")}
              value={childNewId}
              onChange={(e) => setChildNewId(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleCreate(p);
                if (e.key === "Escape") setAddingChildTo(null);
              }}
              className="tree-input"
              autoFocus
            />
            <button
              className="tree-add-btn"
              onClick={() => handleCreate(p)}
              disabled={creating}
              title={t("createProject")}
            >
              +
            </button>
          </div>
        )}

        {/* Children */}
        {isExpanded && childNodes.map((child) => renderNode(child, depth + 1))}
      </div>
    );
  };

  return (
    <div className="project-tree">
      <div className="tree-header" onClick={() => setCollapsed(!collapsed)}>
        <span className="tree-chevron">{collapsed ? "\u25B6" : "\u25BC"}</span>
        <span className="tree-title">{t("projects")}</span>
        <span className="tree-count">{totalProjects}</span>
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
              {/* OpenClaw install status */}
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
                  <button className="tree-openclaw-install-btn" onClick={handleInstallOpenClaw}>
                    {t("openclawInstallBtn")}
                  </button>
                )}
                {openclawStatus === "installing" && (
                  <span className="tree-openclaw-installing">{t("openclawInstalling")}</span>
                )}
                {openclawStatus === "error" && (
                  <span className="tree-openclaw-error">{t("openclawCheckFailed")}</span>
                )}
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
              onClick={() => handleCreate()}
              disabled={creating}
              title={t("createProject")}
            >
              +
            </button>
          </div>

          <div className="tree-list">
            {topLevel.length === 0 && (
              <div className="tree-empty">{t("noProjects")}</div>
            )}
            {topLevel.map((node) => renderNode(node))}
          </div>

          {/* Toggle archived visibility */}
          <button
            className="tree-archive-toggle"
            onClick={() => setShowArchived(!showArchived)}
          >
            {showArchived ? t("hideArchived") : t("showArchived")}
          </button>
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
