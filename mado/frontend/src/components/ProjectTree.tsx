"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import * as api from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useInlineStatus, StatusIndicator } from "@/components/Toast";

interface ProjectNode {
  project_id: string;
  display_name?: string;
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

interface ContextMenuState {
  visible: boolean;
  x: number;
  y: number;
  projectId: string;
  displayName: string;
  isArchived: boolean;
  hasChildren: boolean;
}

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
  const { status: treeStatus, showStatus } = useInlineStatus();
  const [deletePopup, setDeletePopup] = useState<{ projectId: string; displayName: string; x: number; y: number } | null>(null);
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
  const [contextMenu, setContextMenu] = useState<ContextMenuState>({
    visible: false, x: 0, y: 0, projectId: "", displayName: "", isArchived: false, hasChildren: false,
  });
  const [dragId, setDragId] = useState<string | null>(null);
  const [dropTarget, setDropTarget] = useState<{ id: string; position: "before" | "inside" | "after" } | null>(null);
  const treeRef = useRef<HTMLDivElement>(null);

  // Auto-expand: when activeProject changes, expand its ancestors + itself if it has children
  useEffect(() => {
    if (!activeProject || projectTree.length === 0) return;

    const nm = new Map<string, ProjectNode>();
    for (const n of projectTree) nm.set(n.project_id, n);

    const toExpand = new Set<string>();

    // Expand ancestors of active project so it's visible
    const current = nm.get(activeProject);
    if (current?.parent_id) {
      let parentId: string | null = current.parent_id;
      while (parentId) {
        toExpand.add(parentId);
        const parent = nm.get(parentId);
        parentId = parent?.parent_id || null;
      }
    }

    // Expand active project itself if it has children
    if (current && current.children.length > 0) {
      toExpand.add(activeProject);
    }

    if (toExpand.size > 0) {
      setExpandedNodes((prev) => {
        const next = new Set(prev);
        for (const id of toExpand) next.add(id);
        return next;
      });
    }
  }, [activeProject, projectTree]);

  // Close delete popup on Escape
  useEffect(() => {
    if (!deletePopup) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setDeletePopup(null);
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [deletePopup]);

  // Close context menu on click outside
  useEffect(() => {
    const handleClick = () => setContextMenu((prev) => ({ ...prev, visible: false }));
    if (contextMenu.visible) {
      document.addEventListener("click", handleClick);
      return () => document.removeEventListener("click", handleClick);
    }
  }, [contextMenu.visible]);

  // Delete key handler
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Delete" && activeProject && !renamingId) {
        const tag = (e.target as HTMLElement)?.tagName;
        if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

        const nm = new Map<string, ProjectNode>();
        for (const n of projectTree) nm.set(n.project_id, n);
        const node = nm.get(activeProject);
        if (node) {
          handleDeleteRequest(activeProject, node.display_name, e);
        }
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [activeProject, renamingId, projectTree]);

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
      .catch(() => setOpenclawStatus("not_installed"));
  }, []);

  const recheckOpenClaw = async () => {
    try {
      const data = await api.checkOpenClaw();
      setOpenclawStatus(data.installed ? "installed" : "not_installed");
      setOpenclawVersion(data.version || null);
      return data.installed;
    } catch {
      return false;
    }
  };

  const handleInstallOpenClaw = async () => {
    setOpenclawStatus("installing");
    showStatus("OpenClaw をインストール中...", "info");
    try {
      const result = await api.installOpenClaw();
      if (result.status === "already_installed" || result.status === "installed") {
        setOpenclawStatus("installed");
        setOpenclawVersion(result.version || null);
        showStatus("OpenClaw インストール完了", "success");
      } else {
        const isInstalled = await recheckOpenClaw();
        if (!isInstalled) {
          setOpenclawStatus("error");
          showStatus("OpenClaw インストール失敗", "error");
        }
      }
    } catch {
      const isInstalled = await recheckOpenClaw();
      if (!isInstalled) {
        setOpenclawStatus("error");
        showStatus("OpenClaw インストールエラー", "error");
      }
    }
  };

  // Build lookup
  const nodeMap = new Map<string, ProjectNode>();
  for (const n of projectTree) nodeMap.set(n.project_id, n);

  const topLevel = projectTree.filter(
    (n) => !n.parent_id || !nodeMap.has(n.parent_id)
  );

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

    const unsafeChars = /[/\\:*?"<>|]/;
    if (unsafeChars.test(id)) {
      showStatus("プロジェクトIDに無効な文字が含まれています", "error");
      return;
    }

    setCreating(true);
    showStatus("プロジェクト作成中...", "info");
    try {
      const result = await api.createProject(id, "", parentId || undefined);
      const actualId = result.project_id || id;
      if (parentId) {
        setChildNewId("");
        setAddingChildTo(null);
        setExpandedNodes((prev) => new Set(prev).add(parentId));
      } else {
        setNewId("");
      }
      onRefresh();
      onSelect(actualId);
      showStatus(`プロジェクト「${id}」を作成しました`, "success");
    } catch (e: any) {
      showStatus(`作成エラー: ${e?.message || "不明なエラー"}`, "error");
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
      showStatus(`「${oldId}」→「${trimmed}」に名前変更`, "success");
    } catch (e: any) {
      showStatus(`名前変更エラー: ${e.message}`, "error");
    }
  };

  const handleArchiveToggle = async (projectId: string) => {
    const node = nodeMap.get(projectId);
    if (!node) return;
    const newStatus = node.status === "archived" ? "initialized" : "archived";
    try {
      await api.updateProjectConfig(projectId, { status: newStatus });
      onRefresh();
      showStatus(
        newStatus === "archived"
          ? `「${node.display_name || projectId}」をアーカイブ`
          : `「${node.display_name || projectId}」のアーカイブ解除`,
        "success"
      );
    } catch (e: any) {
      showStatus(`エラー: ${e.message}`, "error");
    }
  };

  // Show popup near the project item for delete confirmation
  const handleDeleteRequest = (projectId: string, displayName?: string, event?: React.MouseEvent | KeyboardEvent) => {
    const name = displayName || projectId;
    let x = 100, y = 200;
    if (event && "clientX" in event) {
      x = event.clientX;
      y = event.clientY;
    } else if (treeRef.current) {
      const rect = treeRef.current.getBoundingClientRect();
      x = rect.left + rect.width / 2;
      y = rect.top + rect.height / 2;
    }
    setDeletePopup({ projectId, displayName: name, x, y });
  };

  const handleDeleteConfirm = async () => {
    if (!deletePopup) return;
    const { projectId, displayName: name } = deletePopup;
    setDeletePopup(null);
    showStatus(`「${name}」を削除中…`, "info");
    try {
      await api.deleteProject(projectId);
      onRefresh();
      if (activeProject === projectId) onSelect("");
      showStatus(`「${name}」を削除しました`, "success");
    } catch (e: any) {
      showStatus(`削除エラー: ${e.message || "不明なエラー"}`, "error");
    }
  };

  const handleFolderSave = async () => {
    if (!folderPath.trim()) return;
    setSaving(true);
    showStatus("フォルダ設定を保存中...", "info");
    try {
      const data = await api.setProjectsRoot(folderPath.trim());
      setSavedPath(data.projects_root);
      setFolderPath(data.projects_root);
      setShowFolderSettings(false);
      onRefresh();
      showStatus("フォルダ設定を保存しました", "success");
      setOpenclawStatus("checking");
      api.checkOpenClaw()
        .then((d) => {
          setOpenclawStatus(d.installed ? "installed" : "not_installed");
          setOpenclawVersion(d.version || null);
        })
        .catch(() => setOpenclawStatus("not_installed"));
    } catch (e: any) {
      showStatus(`フォルダ設定エラー: ${e.message}`, "error");
    } finally {
      setSaving(false);
    }
  };

  // Right-click handler
  const handleContextMenu = (e: React.MouseEvent, node: ProjectNode) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenu({
      visible: true,
      x: e.clientX,
      y: e.clientY,
      projectId: node.project_id,
      displayName: node.display_name || node.project_id,
      isArchived: node.status === "archived",
      hasChildren: node.children.length > 0,
    });
  };

  // --- Drag & Drop handlers ---
  const handleDragStart = (e: React.DragEvent, projectId: string) => {
    setDragId(projectId);
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", projectId);
  };

  const handleDragOver = (e: React.DragEvent, targetId: string) => {
    e.preventDefault();
    if (!dragId || dragId === targetId) return;
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const y = e.clientY - rect.top;
    const h = rect.height;
    let position: "before" | "inside" | "after";
    if (y < h * 0.25) position = "before";
    else if (y > h * 0.75) position = "after";
    else position = "inside";
    setDropTarget({ id: targetId, position });
  };

  const handleDragLeave = () => {
    setDropTarget(null);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    if (!dragId || !dropTarget) {
      setDragId(null);
      setDropTarget(null);
      return;
    }

    const { id: targetId, position } = dropTarget;
    setDragId(null);
    setDropTarget(null);

    if (dragId === targetId) return;

    const targetNode = nodeMap.get(targetId);
    const dragNode = nodeMap.get(dragId);
    if (!targetNode || !dragNode) return;

    // Check for circular: target is descendant of drag
    const isDescendant = (parentId: string, checkId: string): boolean => {
      const node = nodeMap.get(parentId);
      if (!node) return false;
      for (const cid of node.children) {
        if (cid === checkId) return true;
        if (isDescendant(cid, checkId)) return true;
      }
      return false;
    };
    if (isDescendant(dragId, targetId)) return;

    try {
      if (position === "inside") {
        // Make drag a child of target
        await api.moveProject(dragId, targetId);
        showStatus(`「${dragNode.display_name || dragId}」を「${targetNode.display_name || targetId}」の子に移動`, "success");
      } else {
        // Move to same parent as target, reorder
        const newParentId = targetNode.parent_id;
        if (dragNode.parent_id !== newParentId) {
          await api.moveProject(dragId, newParentId);
        }
        // Reorder siblings
        const siblings = newParentId
          ? (nodeMap.get(newParentId)?.children || []).filter((id) => id !== dragId)
          : topLevel.map((n) => n.project_id).filter((id) => id !== dragId);
        const targetIdx = siblings.indexOf(targetId);
        const insertIdx = position === "before" ? targetIdx : targetIdx + 1;
        siblings.splice(insertIdx, 0, dragId);
        await api.reorderProjects(siblings, newParentId);
        showStatus(`並び替え完了`, "success");
      }
      onRefresh();
    } catch (e: any) {
      showStatus(`移動エラー: ${e.message || "不明なエラー"}`, "error");
    }
  };

  const isParentRunning = (node: ProjectNode): boolean => {
    if (!node.parent_id) return true;
    return runStatuses[node.parent_id] === "running";
  };

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

    const isDragOver = dropTarget?.id === p;
    const dropPos = dropTarget?.position;

    return (
      <div key={p} className="tree-node-group">
        {isDragOver && dropPos === "before" && (
          <div className="tree-drop-indicator" style={{ marginLeft: `${0.5 + depth * 0.75}rem` }} />
        )}
        <div
          className={`tree-item ${isActive ? "tree-item-active" : ""} ${isArchived ? "tree-item-archived" : ""} ${isDragOver && dropPos === "inside" ? "tree-item-drop-inside" : ""}`}
          style={{ paddingLeft: `${0.5 + depth * 0.75}rem` }}
          draggable={!isRenaming}
          onDragStart={(e) => handleDragStart(e, p)}
          onDragOver={(e) => handleDragOver(e, p)}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onDragEnd={() => { setDragId(null); setDropTarget(null); }}
          onClick={() => !isRenaming && onSelect(p)}
          onDoubleClick={() => {
            setRenamingId(p);
            setRenameValue(p);
          }}
          onContextMenu={(e) => handleContextMenu(e, node)}
          title={t("renameProject")}
        >
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
            <span className="tree-label">{node.display_name || p}</span>
          )}

          {hasChildren && !isRenaming && (
            <span className="tree-child-count">{node.children.length}</span>
          )}

          {/* Hover actions: run controls + add child only */}
          {!isRenaming && (
            <span className="tree-actions">
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
        {isDragOver && dropPos === "after" && (
          <div className="tree-drop-indicator" style={{ marginLeft: `${0.5 + depth * 0.75}rem` }} />
        )}
      </div>
    );
  };

  return (
    <div className="project-tree" ref={treeRef}>
      <div className="tree-header" onClick={() => setCollapsed(!collapsed)}>
        <span className="tree-chevron">{collapsed ? "\u25B6" : "\u25BC"}</span>
        <span className="tree-title">{t("projects")}</span>
        <span className="tree-count">{totalProjects}</span>
      </div>

      {!collapsed && (
        <>
          <button
            className="tree-folder-btn"
            onClick={() => setShowFolderSettings(!showFolderSettings)}
            title={t("projectsFolder")}
          >
            {showFolderSettings ? "\u25B2" : "\u{1F4C1}"} {t("projectsFolder")}
          </button>
          {savedPath && !showFolderSettings && (
            <div className="tree-folder-display" title={savedPath}>
              {savedPath}
            </div>
          )}

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
                  <span className="tree-openclaw-error">
                    {t("openclawCheckFailed")}
                    <button
                      className="tree-openclaw-retry-btn"
                      onClick={() => {
                        setOpenclawStatus("checking");
                        recheckOpenClaw().then((ok) => {
                          if (!ok) setOpenclawStatus("not_installed");
                        });
                      }}
                    >
                      {t("refresh")}
                    </button>
                  </span>
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

      {/* Inline status for tree operations */}
      {treeStatus && (
        <div className="tree-inline-status">
          <StatusIndicator status={treeStatus} />
        </div>
      )}

      {/* Delete confirmation popup (near project) */}
      {deletePopup && (
        <div
          className="delete-popup-overlay"
          onClick={() => setDeletePopup(null)}
        >
          <div
            className="delete-popup"
            style={{ left: deletePopup.x, top: deletePopup.y }}
            onClick={(e) => e.stopPropagation()}
          >
            <p className="delete-popup-text">
              「{deletePopup.displayName}」を削除しますか？
            </p>
            <div className="delete-popup-actions">
              <button
                className="btn btn-danger delete-popup-confirm"
                onClick={handleDeleteConfirm}
              >
                {t("deleteProject")}
              </button>
              <button
                className="delete-popup-cancel"
                onClick={() => setDeletePopup(null)}
              >
                {t("cancel")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Right-click context menu */}
      {contextMenu.visible && (
        <div
          className="context-menu"
          style={{ left: contextMenu.x, top: contextMenu.y }}
          onClick={(e) => e.stopPropagation()}
        >
          <button
            className="context-menu-item"
            onClick={() => {
              setContextMenu((prev) => ({ ...prev, visible: false }));
              setRenamingId(contextMenu.projectId);
              setRenameValue(contextMenu.projectId);
            }}
          >
            ✏️ {t("renameProject")}
          </button>
          <button
            className="context-menu-item"
            onClick={() => {
              setContextMenu((prev) => ({ ...prev, visible: false }));
              setAddingChildTo(contextMenu.projectId);
              setChildNewId("");
            }}
          >
            ➕ {t("addSubProject")}
          </button>
          <div className="context-menu-separator" />
          <button
            className="context-menu-item"
            onClick={() => {
              setContextMenu((prev) => ({ ...prev, visible: false }));
              handleArchiveToggle(contextMenu.projectId);
            }}
          >
            {contextMenu.isArchived ? "↩ " : "📦 "}
            {contextMenu.isArchived ? t("unarchive") : t("archive")}
          </button>
          <div className="context-menu-separator" />
          <button
            className="context-menu-item context-menu-item-danger"
            onClick={(e) => {
              setContextMenu((prev) => ({ ...prev, visible: false }));
              handleDeleteRequest(contextMenu.projectId, contextMenu.displayName, e);
            }}
          >
            🗑 {t("deleteProject")}
          </button>
        </div>
      )}
    </div>
  );
}
