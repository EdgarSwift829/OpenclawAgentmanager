"use client";

import { useState, useEffect } from "react";
import * as api from "@/lib/api";

export function ModelPanel() {
  const [models, setModels] = useState<Record<string, any>>({});
  const [assignments, setAssignments] = useState<Record<string, string>>({});
  const [switchRole, setSwitchRole] = useState("");
  const [switchModel, setSwitchModel] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const m = await api.listModels();
        setModels(m.models || {});
        const a = await api.getAssignments();
        setAssignments(a.assignments || {});
      } catch { /* API not available */ }
    };
    load();
  }, []);

  const handleSwitch = async () => {
    if (!switchRole || !switchModel) return;
    try {
      await api.switchModel(switchRole, switchModel);
      const a = await api.getAssignments();
      setAssignments(a.assignments || {});
      setSwitchRole("");
      setSwitchModel("");
    } catch (e: any) {
      alert(e.message);
    }
  };

  const modelNames = Object.keys(models);
  const roles = Object.keys(assignments);

  return (
    <div className="card">
      <h2>Models</h2>
      <div style={{ fontSize: "0.8125rem", marginBottom: "0.5rem" }}>
        {roles.map((role) => (
          <div key={role} style={{ display: "flex", justifyContent: "space-between", padding: "0.25rem 0" }}>
            <span>{role}</span>
            <span style={{ color: "var(--text-secondary)" }}>{assignments[role]}</span>
          </div>
        ))}
        {roles.length === 0 && (
          <span style={{ color: "var(--text-secondary)" }}>No model config loaded</span>
        )}
      </div>
      {modelNames.length > 0 && (
        <div style={{ display: "flex", gap: "0.25rem", flexWrap: "wrap", marginTop: "0.5rem" }}>
          <select value={switchRole} onChange={(e) => setSwitchRole(e.target.value)} style={{ flex: 1 }}>
            <option value="">Role...</option>
            {roles.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
          <select value={switchModel} onChange={(e) => setSwitchModel(e.target.value)} style={{ flex: 1 }}>
            <option value="">Model...</option>
            {modelNames.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
          <button className="btn" onClick={handleSwitch}>Switch</button>
        </div>
      )}
    </div>
  );
}
