"use client";

import { useState } from "react";
import * as api from "@/lib/api";

interface Props {
  projects: string[];
  activeProject: string | null;
  onSelect: (id: string) => void;
  onRefresh: () => void;
}

export function ProjectPanel({ projects, activeProject, onSelect, onRefresh }: Props) {
  const [newId, setNewId] = useState("");
  const [creating, setCreating] = useState(false);

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
    <div className="card">
      <h2>Projects</h2>
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.75rem" }}>
        <input
          placeholder="New project ID"
          value={newId}
          onChange={(e) => setNewId(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleCreate()}
        />
        <button className="btn btn-primary" onClick={handleCreate} disabled={creating}>
          +
        </button>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
        {projects.length === 0 && (
          <span style={{ color: "var(--text-secondary)", fontSize: "0.8125rem" }}>
            No projects yet
          </span>
        )}
        {projects.map((p) => (
          <button
            key={p}
            className="btn"
            style={{
              textAlign: "left",
              background: p === activeProject ? "var(--accent)" : undefined,
              borderColor: p === activeProject ? "var(--accent)" : undefined,
            }}
            onClick={() => onSelect(p)}
          >
            {p}
          </button>
        ))}
      </div>
    </div>
  );
}
