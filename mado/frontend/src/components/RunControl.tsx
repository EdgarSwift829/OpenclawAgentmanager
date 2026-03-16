"use client";

import { useState, useCallback } from "react";
import * as api from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useInlineStatus, StatusIndicator } from "@/components/Toast";
import type { RunStatus } from "@/lib/types";

interface Props {
  activeProject: string | null;
  runStatus: RunStatus | null;
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
  const { t, locale } = useI18n();
  const { status, showStatus } = useInlineStatus();
  const [starting, setStarting] = useState(false);
  const [confirmStop, setConfirmStop] = useState(false);

  const handleStart = async () => {
    if (!activeProject || !goal.trim()) {
      showStatus(locale === "ja" ? "目標を入力してください" : "Please enter a goal", "warning");
      return;
    }
    setStarting(true);
    showStatus(locale === "ja" ? "実行準備中…" : "Preparing...", "info");
    try {
      await api.startRun(activeProject, goal.trim(), maxIter);
      onRefresh();
      showStatus(locale === "ja" ? "実行開始" : "Started", "success");
    } catch (e: any) {
      showStatus(`${locale === "ja" ? "実行エラー" : "Error"}: ${e.message}`, "error");
    } finally {
      setStarting(false);
    }
  };

  const handleStop = useCallback(async () => {
    if (!activeProject) return;
    setConfirmStop(false);
    try {
      await api.stopRun(activeProject);
      onRefresh();
      showStatus(locale === "ja" ? "停止完了" : "Stopped", "success");
    } catch (e: any) {
      showStatus(`${locale === "ja" ? "停止エラー" : "Stop error"}: ${e.message}`, "error");
    }
  }, [activeProject, onRefresh, showStatus, locale]);

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
          <button className="btn btn-primary" onClick={handleStart} disabled={starting}>
            {starting ? (locale === "ja" ? "準備中..." : "Starting...") : t("start")}
          </button>
        ) : confirmStop ? (
          <span className="run-stop-confirm">
            <button className="btn btn-danger btn-sm" onClick={handleStop}>
              {locale === "ja" ? "停止する" : "Confirm"}
            </button>
            <button className="btn btn-ghost btn-sm" onClick={() => setConfirmStop(false)}>
              {t("cancel")}
            </button>
          </span>
        ) : (
          <button className="btn btn-danger" onClick={() => setConfirmStop(true)}>
            {t("stop")}
          </button>
        )}
        <StatusIndicator status={status} />
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
      {isRunning && runStatus && runStatus.max_iterations > 0 && (
        <div className="run-progress-bar-container">
          <div className="run-progress-bar">
            <div
              className="run-progress-fill"
              style={{ width: `${Math.min(100, (runStatus.iteration / runStatus.max_iterations) * 100)}%` }}
            />
          </div>
          <span className="run-progress-label">
            {locale === "ja"
              ? `イテレーション ${runStatus.iteration} / ${runStatus.max_iterations}`
              : `Iteration ${runStatus.iteration} / ${runStatus.max_iterations}`}
          </span>
        </div>
      )}
      {isExhausted && (
        <div className="run-exhausted-banner" role="alert">
          <span className="run-exhausted-text">{"\u26A0"} {t("iterExhausted")}</span>
          <button className="btn btn-primary run-extend-btn" onClick={handleExtend}>
            {t("extendIterations")} (+{maxIter})
          </button>
        </div>
      )}
    </div>
  );
}
