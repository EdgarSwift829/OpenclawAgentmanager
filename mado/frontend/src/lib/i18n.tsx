"use client";

import { createContext, useContext, useState, useCallback, ReactNode } from "react";

export type Locale = "ja" | "en";

const dict = {
  // Sidebar
  collapse: { en: "Collapse", ja: "閉じる" },
  expand: { en: "Expand", ja: "開く" },

  // Tabs
  timeline: { en: "Timeline", ja: "タイムライン" },
  models: { en: "Models", ja: "モデル" },
  tasks: { en: "Tasks", ja: "タスク" },

  // ProjectTree
  projects: { en: "PROJECTS", ja: "プロジェクト" },
  newProject: { en: "New project...", ja: "新規プロジェクト..." },
  createProject: { en: "Create project", ja: "プロジェクト作成" },
  refreshProjects: { en: "Refresh projects", ja: "更新" },
  refresh: { en: "Refresh", ja: "更新" },
  noProjects: { en: "No projects", ja: "プロジェクトなし" },
  renameProject: { en: "Double-click to rename", ja: "ダブルクリックでリネーム" },
  addSubProject: { en: "Add sub-project", ja: "子プロジェクト追加" },
  newSubProject: { en: "New sub-project...", ja: "新規子プロジェクト..." },
  subProjects: { en: "sub-projects", ja: "子プロジェクト" },
  progress: { en: "Progress", ja: "進捗" },
  archive: { en: "Archive", ja: "アーカイブ" },
  unarchive: { en: "Unarchive", ja: "アーカイブ解除" },
  archived: { en: "Archived", ja: "アーカイブ済" },
  showArchived: { en: "Show archived", ja: "アーカイブ表示" },
  hideArchived: { en: "Hide archived", ja: "アーカイブ非表示" },

  // ProjectDetail
  overview: { en: "Overview", ja: "概要" },
  overviewPlaceholder: { en: "Project overview...", ja: "プロジェクトの概要を入力..." },
  policyLabel: { en: "Policy / Guidelines", ja: "方針・ガイドライン" },
  policyPlaceholder: { en: "Development policy...", ja: "開発方針を入力..." },
  roadmap: { en: "Roadmap / TODO", ja: "ロードマップ・やること" },
  roadmapPlaceholder: { en: "What needs to be done...", ja: "やるべきことを入力..." },
  descriptionLabel: { en: "Description", ja: "詳細" },
  descriptionPlaceholder: { en: "Task details...", ja: "タスクの詳細を入力..." },
  deadline: { en: "Deadline", ja: "期限" },
  taskList: { en: "Task List", ja: "タスク一覧" },
  addTask: { en: "Add task", ja: "タスク追加" },
  taskTitle: { en: "Task title", ja: "タスク名" },
  saved: { en: "Saved", ja: "保存済" },
  save: { en: "Save", ja: "保存" },
  saving: { en: "Saving...", ja: "保存中..." },
  pending: { en: "Pending", ja: "未着手" },
  inProgress: { en: "In progress", ja: "進行中" },
  priorityHigh: { en: "High", ja: "高" },
  priorityMedium: { en: "Medium", ja: "中" },
  priorityLow: { en: "Low", ja: "低" },
  noProjectSelected: { en: "Select a project", ja: "プロジェクトを選択" },
  iterExhausted: { en: "Iterations exhausted. Review results and extend if needed.", ja: "反復回数を使い切りました。成果を確認し、必要なら延長してください。" },
  extendIterations: { en: "Extend", ja: "延長" },

  // RunControl
  goalPlaceholder: { en: "Describe the project goal...", ja: "プロジェクトの目標を入力..." },
  iterations: { en: "Iterations:", ja: "反復回数:" },
  start: { en: "Start", ja: "開始" },
  stop: { en: "Stop", ja: "停止" },
  selectProject: { en: "Select a project to start", ja: "プロジェクトを選択してください" },

  // AgentGrid
  waitingForAgents: { en: "Waiting for agents...", ja: "エージェント待機中..." },
  startRunToSpawn: { en: "Start to spawn agents", ja: "開始してエージェントを起動" },
  processing: { en: "Processing...", ja: "処理中..." },
  standby: { en: "Standby", ja: "待機中" },
  done: { en: "done", ja: "完了" },
  fail: { en: "fail", ja: "失敗" },

  // AgentActivity
  agentActivity: { en: "Agent Activity", ja: "エージェント活動" },
  noActiveAgents: { en: "No active agents", ja: "アクティブなエージェントなし" },

  // ModelPanel
  agentPipeline: { en: "Agent Pipeline", ja: "エージェントパイプライン" },
  dragToReorder: { en: "Drag to reorder", ja: "ドラッグで並び替え" },
  noAgentConfig: { en: "No agent config loaded", ja: "エージェント設定未読み込み" },

  // Timeline
  iterationTimeline: { en: "Iteration Timeline", ja: "反復タイムライン" },
  noEventsYet: { en: "No events yet", ja: "イベントなし" },

  // Settings
  projectsFolder: { en: "Projects Folder", ja: "プロジェクトフォルダ" },
  folderPath: { en: "Folder path", ja: "フォルダパス" },
  apply: { en: "Apply", ja: "適用" },
  cancel: { en: "Cancel", ja: "キャンセル" },
  folderUpdated: { en: "Folder updated", ja: "フォルダを更新しました" },
  settings: { en: "Settings", ja: "設定" },

  // Run Control per project
  runProject: { en: "Run", ja: "実行" },
  pauseProject: { en: "Pause", ja: "一時停止" },
  resumeProject: { en: "Resume", ja: "再開" },
  paused: { en: "Paused", ja: "一時停止中" },
  stopped: { en: "Stopped", ja: "停止" },
  running: { en: "Running", ja: "実行中" },
  parentMustRun: { en: "Start parent project first", ja: "先に親プロジェクトを開始してください" },

  // OpenClaw
  openclawStatus: { en: "OpenClaw", ja: "OpenClaw" },
  openclawInstalled: { en: "Installed", ja: "インストール済" },
  openclawNotInstalled: { en: "Not installed", ja: "未インストール" },
  openclawInstalling: { en: "Installing...", ja: "インストール中..." },
  openclawInstallBtn: { en: "Install OpenClaw", ja: "OpenClawをインストール" },
  openclawCheckFailed: { en: "Check failed", ja: "確認失敗" },
  deleteProject: { en: "Delete", ja: "削除" },
  confirmDelete: { en: "Are you sure you want to delete", ja: "を削除してよろしいですか？" },

  // TaskGraph
  taskGraph: { en: "Task Graph", ja: "タスクグラフ" },
  noActiveTasks: { en: "No active tasks", ja: "アクティブなタスクなし" },
  ctoPlanning: { en: "CTO Planning", ja: "CTO 計画" },
  taskDecomposition: { en: "Task Decomposition", ja: "タスク分解" },
  research: { en: "Research", ja: "リサーチ" },
  implementation: { en: "Implementation", ja: "実装" },
  codeReview: { en: "Code Review", ja: "コードレビュー" },
  testing: { en: "Testing", ja: "テスト" },
} as const;

export type TKey = keyof typeof dict;

interface I18nContextType {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (key: TKey) => string;
}

const I18nContext = createContext<I18nContextType>({
  locale: "ja",
  setLocale: () => {},
  t: (key) => dict[key]?.ja ?? key,
});

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(() => {
    if (typeof window === "undefined") return "ja";
    return (localStorage.getItem("mado_locale") as Locale) || "ja";
  });

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    if (typeof window !== "undefined") {
      localStorage.setItem("mado_locale", l);
    }
  }, []);

  const t = useCallback(
    (key: TKey): string => dict[key]?.[locale] ?? key,
    [locale],
  );

  return (
    <I18nContext.Provider value={{ locale, setLocale, t }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n() {
  return useContext(I18nContext);
}
