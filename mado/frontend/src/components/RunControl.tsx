"use client";

import * as api from "@/lib/api";
import { useI18n } from "@/lib/i18n";

interface Props {
  activeProject: string | null;
  runStatus: any;
  onRefresh: () => void;
  goal: string;
  onGoalChange: (goal: string) => void;
  maxIter: number;
  onMaxIterChange: (n: number) => void;
}

export function RunControl({
  activeProject,
  runStatus,
  onRefresh,
  goal,
  onGoalChange,
  maxIter,
  onMaxIterChange,
}: Props) {
  const { t } = useI18n();

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

  if (!activeProject) {
    return (
      <div className="run-control">
        <span className="run-control-hint">{t("selectProject")}</span>
      </div>
    );
  }

  return (
    <div className="run-control">
      <input
        className="run-goal-input"
        placeholder={t("goalPlaceholder")}
        value={goal}
        onChange={(e) => onGoalChange(e.target.value)}
        disabled={isRunning}
        onKeyDown={(e) => e.key === "Enter" && !isRunning && handleStart()}
      />
      <div className="run-controls-row">
        <label className="run-iter-label">
          {t("iterations")}
          <input
            type="number"
            min={1}
            max={50}
            value={maxIter}
            onChange={(e) => onMaxIterChange(Number(e.target.value))}
            className="run-iter-input"
            disabled={isRunning}
          />
        </label>
        {!isRunning ? (
          <button className="btn btn-primary" onClick={handleStart}>
            {t("start")}
          </button>
        ) : (
          <button className="btn btn-danger" onClick={handleStop}>
            {t("stop")}
          </button>
        )}
        {runStatus && (
          <span className="run-status-info">
            <span className={`badge badge-${runStatus.status === "running" ? "running" : runStatus.status === "completed" ? "completed" : runStatus.status === "error" ? "error" : "idle"}`}>
              {runStatus.status}
            </span>
            <span className="run-iter-count">
              {runStatus.iteration}/{runStatus.max_iterations}
            </span>
          </span>
        )}
      </div>
    </div>
  );
}
