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
