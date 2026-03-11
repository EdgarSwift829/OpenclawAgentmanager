"use client";

import { useState } from "react";
import * as api from "@/lib/api";

interface Props {
  activeProject: string | null;
  runStatus: any;
  onRefresh: () => void;
}

export function RunControl({ activeProject, runStatus, onRefresh }: Props) {
  const [goal, setGoal] = useState("");
  const [maxIter, setMaxIter] = useState(10);

  const handleStart = async () => {
    if (!activeProject || !goal.trim()) return;
    try {
      await api.startRun(activeProject, goal.trim(), maxIter);
      onRefresh();
    } catch (e: any) {
      alert(e.message);
    }
  };

  const handleStop = async () => {
    if (!activeProject) return;
    try {
      await api.stopRun(activeProject);
      onRefresh();
    } catch (e: any) {
      alert(e.message);
    }
  };

  const isRunning = runStatus?.status === "running";

  return (
    <div className="card">
      <h2>Orchestration</h2>
      {!activeProject ? (
        <span style={{ color: "var(--text-secondary)", fontSize: "0.8125rem" }}>
          Select a project
        </span>
      ) : (
        <>
          <div style={{ marginBottom: "0.5rem" }}>
            <input
              placeholder="Project goal..."
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              disabled={isRunning}
            />
          </div>
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", marginBottom: "0.75rem" }}>
            <label style={{ fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
              Max iterations:
            </label>
            <input
              type="number"
              min={1}
              max={50}
              value={maxIter}
              onChange={(e) => setMaxIter(Number(e.target.value))}
              style={{ width: "4rem" }}
              disabled={isRunning}
            />
          </div>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            {!isRunning ? (
              <button className="btn btn-primary" onClick={handleStart}>
                Start Run
              </button>
            ) : (
              <button className="btn btn-danger" onClick={handleStop}>
                Stop
              </button>
            )}
          </div>
          {runStatus && (
            <div style={{ marginTop: "0.75rem", fontSize: "0.8125rem" }}>
              <span>Status: </span>
              <span className={`badge badge-${runStatus.status === "running" ? "running" : runStatus.status === "completed" ? "completed" : runStatus.status === "error" ? "error" : "idle"}`}>
                {runStatus.status}
              </span>
              <span style={{ marginLeft: "0.5rem", color: "var(--text-secondary)" }}>
                Iteration: {runStatus.iteration}/{runStatus.max_iterations}
              </span>
            </div>
          )}
        </>
      )}
    </div>
  );
}
