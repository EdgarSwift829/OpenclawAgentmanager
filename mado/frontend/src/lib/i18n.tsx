"use client";

import { createContext, useContext, useState, useCallback, ReactNode } from "react";

export type Locale = "ja" | "en";

const dict = {
  // Setup Wizard
  setupWelcome: { en: "Welcome to MADO", ja: "MADOへようこそ" },
  setupWelcomeSub: { en: "Let's set up your workspace", ja: "ワークスペースを設定しましょう" },
  setupStep1Title: { en: "Projects Folder", ja: "プロジェクトフォルダ" },
  setupStep1Desc: { en: "Open the folder where your projects will be stored.", ja: "作業フォルダを開いてください。" },
  setupStep2Title: { en: "LLM Settings", ja: "LLM設定" },
  setupStep2Desc: { en: "Configure your local LLM provider and model.", ja: "ローカルLLMのプロバイダーとモデルを設定してください。" },
  setupFolderPath: { en: "Folder path", ja: "フォルダパス" },
  setupFolderPlaceholder: { en: "Enter or browse folder path", ja: "フォルダパスを入力または参照" },
  setupSave: { en: "Save & Continue", ja: "保存して次へ" },
  setupComplete: { en: "Start Using MADO", ja: "MADOを使い始める" },
  setupProvider: { en: "Provider", ja: "プロバイダー" },
  setupModel: { en: "Default Model", ja: "デフォルトモデル" },
  setupSkip: { en: "Skip (use defaults)", ja: "スキップ（デフォルト設定を使用）" },
  setupSaving: { en: "Saving...", ja: "保存中..." },

  // Sidebar
  collapse: { en: "Collapse", ja: "閉じる" },
  expand: { en: "Expand", ja: "開く" },

  // Tabs
  timeline: { en: "Timeline", ja: "タイムライン" },
  agentsTab: { en: "Agents", ja: "エージェント" },
  models: { en: "Models", ja: "モデル" },
  tasks: { en: "Tasks", ja: "タスク" },

  // Agents Tab
  noAgentsYet: { en: "No agents active yet. Start a run to spawn agents.", ja: "まだエージェントがいません。実行を開始するとエージェントが起動します。" },

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

  // Folder Browser
  browse: { en: "Browse", ja: "参照" },
  browseFolder: { en: "Open Work Folder", ja: "作業フォルダを開いてください" },
  folderUp: { en: "Go up", ja: "上の階層へ" },
  folderGo: { en: "Go", ja: "移動" },
  folderLoading: { en: "Loading...", ja: "読み込み中..." },
  folderEmpty: { en: "No subfolders", ja: "サブフォルダなし" },
  folderSelect: { en: "Select This Folder", ja: "このフォルダを選択" },

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

  // Project Rules
  rulesMust: { en: "Rules (MUST)", ja: "遵守事項（必ず守ること）" },
  rulesMustPlaceholder: { en: "Rules that all agents must follow...", ja: "全エージェントが必ず守るルールを入力..." },
  rulesForbidden: { en: "Rules (FORBIDDEN)", ja: "禁止事項（絶対にやらないこと）" },
  rulesForbiddenPlaceholder: { en: "Actions that are strictly prohibited...", ja: "絶対にやってはいけないことを入力..." },

  // Agent Profiles
  agentProfiles: { en: "Agent Profiles", ja: "エージェント設定" },
  agentTitlePlaceholder: { en: "Title (e.g. Top Engineer)", ja: "肩書き（例：トップエンジニア）" },
  agentPersonalityPlaceholder: { en: "Personality & strengths...", ja: "特徴・得意分野を入力..." },

  // Compact ProjectDetail
  additionalOrder: { en: "Additional Order", ja: "追加オーダー" },
  additionalOrderPlaceholder: { en: "Enter additional instructions...", ja: "追加の指示を入力..." },
  sendOrder: { en: "Send", ja: "送信" },
  taskStatusSummary: { en: "Task Status", ja: "タスク状況" },
  noTasks: { en: "No tasks", ja: "タスクなし" },
  detailSettings: { en: "Detail Settings", ja: "詳細設定" },
  editGoal: { en: "Click to edit", ja: "クリックして編集" },

  // Child Project Management
  childProjectManagement: { en: "Sub-project Control", ja: "子プロジェクト管理" },
  dispatchChild: { en: "Start", ja: "開始" },
  stopChild: { en: "Stop", ja: "停止" },
  dispatchAll: { en: "Start All", ja: "一括開始" },
  stopAll: { en: "Stop All", ja: "一括停止" },
  childStatus: { en: "Status", ja: "ステータス" },
  inheritingProfiles: { en: "Inheriting agent profiles from parent", ja: "親のエージェント設定を継承" },
  inheritingMemory: { en: "Sharing parent project memory", ja: "親のプロジェクトメモリを共有" },
  childInstruction: { en: "Instruction to child", ja: "子への指示" },
  sendInstruction: { en: "Send & Start", ja: "指示して開始" },
  noChildren: { en: "No sub-projects", ja: "子プロジェクトなし" },
  initialized: { en: "Ready", ja: "準備完了" },
  completed: { en: "Completed", ja: "完了" },
  error: { en: "Error", ja: "エラー" },

  // TaskFlow
  taskFlow: { en: "Task Flow", ja: "タスクフロー" },
  rejected: { en: "Rejected", ja: "差し戻し" },
  waitingReview: { en: "Awaiting Review", ja: "レビュー待ち" },
  queued: { en: "Queued", ja: "待ち" },

  // TaskGraph
  taskGraph: { en: "Task Graph", ja: "タスクグラフ" },
  noActiveTasks: { en: "No active tasks", ja: "アクティブなタスクなし" },
  ctoPlanning: { en: "CTO Planning", ja: "CTO 計画" },
  taskDecomposition: { en: "Task Decomposition", ja: "タスク分解" },
  research: { en: "Research", ja: "リサーチ" },
  implementation: { en: "Implementation", ja: "実装" },
  codeReview: { en: "Code Review", ja: "コードレビュー" },
  testing: { en: "Testing", ja: "テスト" },
  planFree: { en: "Free Plan", ja: "無料プラン" },
  planPro: { en: "Pro Plan", ja: "Proプラン" },
  planTeam: { en: "Team Plan", ja: "Teamプラン" },
  planEnterprise: { en: "Enterprise Plan", ja: "Enterpriseプラン" },
  projectUsage: { en: "Projects", ja: "プロジェクト" },
  limitReached: { en: "Limit reached", ja: "上限に達しました" },
  upgrade: { en: "Upgrade", ja: "アップグレード" },
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
