"use client";

import * as api from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useToast } from "@/components/Toast";

interface Props {
  activeProject: string | null;
  runStatus: any;
  onRefresh: () => void;
  /** Goal from project config (ProjectDetail saves this) */
  goal: string;
  maxIter: number;
  onMaxIterChange: (n: number) => void;
  onExtendIterations?: (extra: number) => void;
}

export function RunControl({
  activeProject,
  runStatus,
  onRefresh,
  goal,
  maxIter,
  onMaxIterChange,
  onExtendIterations,
}: Props) {
  const { t } = useI18n();
  const { showToast } = useToast();

  const handleStart = async () => {
    if (!activeProject || !goal.trim()) {
      showToast("目標を入力してください", "warning");
      return;
    }
    showToast("実行準備中...", "info");
    try {
      await api.startRun(activeProject, goal.trim(), maxIter);
      onRefresh();
      showToast("実行を開始しました", "success");
    } catch (e: any) {
      showToast(`実行エラー: ${e.message}`, "error");
    }
  };

  const handleStop = async () => {
    if (!activeProject) return;
    try {
      await api.stopRun(activeProject);
      onRefresh();
      showToast("実行を停止しました", "success");
    } catch (e: any) {
      showToast(`停止エラー: ${e.message}`, "error");
    }
  };

  const handleExtend = () => {
    if (onExtendIterations) {
      onExtendIterations(maxIter);
    }
  };

  const isRunning = runStatus?.status === "running";
  const isExhausted =
    runStatus &&
    runStatus.status !== "running" &&
    runStatus.iteration > 0 &&
    runStatus.iteration >= runStatus.max_iterations;

  if (!activeProject) {
    return (
      <div className="run-control">
        <span className="run-control-hint">{t("selectProject")}</span>
      </div>
    );
  }

  return (
    <div className="run-control">
      <div className="run-controls-row">
        <label className="run-iter-label">
          {t("iterations")}
          <input
            type="number"
            min={1}
            max={200}
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
      {isExhausted && (
        <div className="run-exhausted-banner">
          <span className="run-exhausted-text">{t("iterExhausted")}</span>
          <button className="btn btn-primary run-extend-btn" onClick={handleExtend}>
            {t("extendIterations")} (+{maxIter})
          </button>
        </div>
      )}
    </div>
  );
}
