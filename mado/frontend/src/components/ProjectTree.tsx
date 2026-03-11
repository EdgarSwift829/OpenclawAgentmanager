"use client";

import { useState } from "react";
import * as api from "@/lib/api";

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
  const [newId, setNewId] = useState("");
  const [creating, setCreating] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

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

  return (
    <div className="project-tree">
      <div className="tree-header" onClick={() => setCollapsed(!collapsed)}>
        <span className="tree-chevron">{collapsed ? "\u25B6" : "\u25BC"}</span>
        <span className="tree-title">PROJECTS</span>
        <span className="tree-count">{projects.length}</span>
      </div>

      {!collapsed && (
        <>
          <div className="tree-create">
            <input
              placeholder="New project..."
              value={newId}
              onChange={(e) => setNewId(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleCreate()}
              className="tree-input"
            />
            <button
              className="tree-add-btn"
              onClick={handleCreate}
              disabled={creating}
              title="Create project"
            >
              +
            </button>
          </div>

          <div className="tree-list">
            {projects.length === 0 && (
              <div className="tree-empty">No projects</div>
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
        title="Refresh projects"
      >
        Refresh
      </button>
    </div>
  );
}
