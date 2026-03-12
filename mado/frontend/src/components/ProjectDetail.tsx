"use client";

import { useState, useEffect, useCallback } from "react";
import * as api from "@/lib/api";
import { useI18n, type Locale } from "@/lib/i18n";
import { useToast } from "@/components/Toast";

interface TaskItem {
  id: string;
  title: string;
  description: string;
  status: string;
  deadline: string;
  priority: string;
}

interface AgentProfile {
  title: string;
  personality: string;
}

interface ProjectNode {
  project_id: string;
  display_name?: string;
  parent_id: string | null;
  children: string[];
  status: string;
  goal: string;
  overview: string;
  policy: string;
  roadmap: string;
  description: string;
  deadline: string | null;
  tasks: TaskItem[];
  agent_profiles?: Record<string, AgentProfile>;
}

const AGENT_ROLES: {
  key: string;
  icon: string;
  label: { en: string; ja: string };
  defaultTitle: { en: string; ja: string };
  defaultPersonality: { en: string; ja: string };
}[] = [
  {
    key: "cto",
    icon: "\uD83D\uDCCB",
    label: { en: "CTO", ja: "CTO" },
    defaultTitle: { en: "Chief Technology Officer", ja: "最高技術責任者" },
    defaultPersonality: {
      en: "Visionary architect with deep expertise in system design and technology selection. Excels at breaking complex problems into manageable phases. Strong at risk assessment and making pragmatic trade-off decisions.",
      ja: "システム設計と技術選定に精通した先見性のあるアーキテクト。複雑な問題をフェーズに分解するのが得意。リスク評価と現実的なトレードオフ判断に優れる。",
    },
  },
  {
    key: "manager",
    icon: "\uD83D\uDCC1",
    label: { en: "PM", ja: "PM" },
    defaultTitle: { en: "Project Manager", ja: "プロジェクトマネージャー" },
    defaultPersonality: {
      en: "Organized coordinator who excels at task decomposition and dependency management. Keeps the team on track with clear priorities and realistic scheduling. Strong communication and progress tracking skills.",
      ja: "タスク分解と依存関係管理に長けた組織力のあるコーディネーター。明確な優先順位と現実的なスケジューリングでチームを導く。コミュニケーション力と進捗管理に優れる。",
    },
  },
  {
    key: "researcher",
    icon: "\uD83D\uDD0D",
    label: { en: "Researcher", ja: "リサーチャー" },
    defaultTitle: { en: "Senior Technical Researcher", ja: "シニアテクニカルリサーチャー" },
    defaultPersonality: {
      en: "Thorough investigator with broad technical knowledge. Quickly synthesizes information from multiple sources into actionable insights. Specializes in technology evaluation, best practice research, and competitive analysis.",
      ja: "幅広い技術知識を持つ徹底的な調査者。複数ソースの情報を実用的なインサイトに素早くまとめる。技術評価、ベストプラクティス調査、競合分析が専門。",
    },
  },
  {
    key: "engineer",
    icon: "\u2699\uFE0F",
    label: { en: "Engineer", ja: "エンジニア" },
    defaultTitle: { en: "Full-Stack Developer", ja: "フルスタックデベロッパー" },
    defaultPersonality: {
      en: "Highly productive developer who writes clean, maintainable code. Proficient in multiple languages and frameworks. Values simplicity and readability over cleverness. Follows project conventions and writes code that others can easily understand.",
      ja: "クリーンで保守しやすいコードを書く高い生産性の開発者。複数の言語・フレームワークに精通。巧妙さよりシンプルさと可読性を重視。プロジェクト規約に従い、他者が理解しやすいコードを書く。",
    },
  },
  {
    key: "reviewer",
    icon: "\uD83D\uDCDD",
    label: { en: "Reviewer", ja: "レビュアー" },
    defaultTitle: { en: "Code Quality Lead", ja: "コード品質リード" },
    defaultPersonality: {
      en: "Meticulous code reviewer with a sharp eye for bugs, security vulnerabilities, and design issues. Provides constructive feedback with concrete suggestions. Enforces coding standards while respecting developer intent.",
      ja: "バグ・セキュリティ脆弱性・設計問題を鋭く見抜く綿密なコードレビュアー。具体的な改善案を伴う建設的なフィードバックを提供。開発者の意図を尊重しつつコーディング規約を徹底。",
    },
  },
  {
    key: "tester",
    icon: "\uD83E\uDDEA",
    label: { en: "Tester", ja: "テスター" },
    defaultTitle: { en: "QA Engineer", ja: "QAエンジニア" },
    defaultPersonality: {
      en: "Quality-focused tester who designs comprehensive test strategies. Expert at identifying edge cases and writing reliable automated tests. Systematic approach to unit, integration, and end-to-end testing.",
      ja: "包括的なテスト戦略を設計する品質重視のテスター。エッジケースの特定と信頼性の高い自動テストの作成が得意。ユニット・統合・E2Eテストへの体系的アプローチ。",
    },
  },
  {
    key: "optimizer",
    icon: "\u26A1",
    label: { en: "Optimizer", ja: "オプティマイザー" },
    defaultTitle: { en: "Performance Engineer", ja: "パフォーマンスエンジニア" },
    defaultPersonality: {
      en: "Performance-obsessed engineer who identifies bottlenecks through profiling and metrics. Skilled at algorithmic optimization, caching strategies, and resource efficiency. Balances performance gains against code complexity.",
      ja: "プロファイリングとメトリクスでボトルネックを特定するパフォーマンス専門エンジニア。アルゴリズム最適化、キャッシュ戦略、リソース効率化に精通。パフォーマンス向上とコード複雑性のバランスを重視。",
    },
  },
  {
    key: "documenter",
    icon: "\uD83D\uDCD6",
    label: { en: "Documenter", ja: "ドキュメンター" },
    defaultTitle: { en: "Technical Writer", ja: "テクニカルライター" },
    defaultPersonality: {
      en: "Clear and concise technical writer who creates documentation developers actually want to read. Expert at API docs, architecture guides, and README files. Focuses on practical examples and maintainable documentation structure.",
      ja: "開発者が実際に読みたくなるドキュメントを作成する明瞭なテクニカルライター。API仕様書・アーキテクチャガイド・READMEの作成が得意。実践的なサンプルと保守しやすい構成を重視。",
    },
  },
  {
    key: "marketer",
    icon: "\uD83D\uDCE2",
    label: { en: "Marketer", ja: "マーケター" },
    defaultTitle: { en: "Growth Marketing Specialist", ja: "グロースマーケティングスペシャリスト" },
    defaultPersonality: {
      en: "Data-driven marketer who creates compelling content and growth strategies. Skilled at market analysis, SEO, social media strategy, and launch planning. Translates technical features into user-facing value propositions.",
      ja: "データ駆動で魅力的なコンテンツと成長戦略を立案するマーケター。市場分析・SEO・SNS戦略・ローンチ計画に精通。技術的な機能をユーザー向けの価値提案に変換するのが得意。",
    },
  },
];

interface Props {
  activeProject: string | null;
  projectTree: ProjectNode[];
  onRefresh: () => void;
}

export function ProjectDetail({ activeProject, projectTree, onRefresh }: Props) {
  const { t, locale } = useI18n();
  const { showToast } = useToast();
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [dirty, setDirty] = useState(false);

  // Editable fields
  const [goal, setGoal] = useState("");
  const [overview, setOverview] = useState("");
  const [policy, setPolicy] = useState("");
  const [roadmap, setRoadmap] = useState("");
  const [description, setDescription] = useState("");
  const [deadline, setDeadline] = useState("");
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [rulesMust, setRulesMust] = useState("");
  const [rulesForbidden, setRulesForbidden] = useState("");
  const [agentProfiles, setAgentProfiles] = useState<Record<string, AgentProfile>>({});

  const node = projectTree.find((n) => n.project_id === activeProject);
  const isParent = node ? node.children.length > 0 || !node.parent_id : false;

  // Load data when project changes
  useEffect(() => {
    if (!node) return;
    setGoal(node.goal || "");
    setOverview(node.overview || "");
    setPolicy(node.policy || "");
    setRoadmap(node.roadmap || "");
    setDescription(node.description || "");
    setDeadline(node.deadline || "");
    setTasks(node.tasks || []);
    setRulesMust((node as any).rules_must || "");
    setRulesForbidden((node as any).rules_forbidden || "");
    setAgentProfiles(node.agent_profiles || {});
    setDirty(false);
    setSaved(false);
  }, [activeProject, node?.project_id]);

  const markDirty = useCallback(() => {
    setDirty(true);
    setSaved(false);
  }, []);

  const handleSave = async () => {
    if (!activeProject) return;
    setSaving(true);
    try {
      const updates: Record<string, any> = {
        goal,
        rules_must: rulesMust,
        rules_forbidden: rulesForbidden,
        agent_profiles: agentProfiles,
      };
      if (isParent || !node?.parent_id) {
        updates.overview = overview;
        updates.policy = policy;
        updates.roadmap = roadmap;
      }
      if (node?.parent_id) {
        updates.description = description;
        updates.deadline = deadline || null;
        updates.tasks = tasks;
      }
      await api.updateProjectConfig(activeProject, updates);
      setSaved(true);
      setDirty(false);
      onRefresh();
      showToast("設定を保存しました", "success");
    } catch (e: any) {
      showToast(`保存エラー: ${e.message}`, "error");
    } finally {
      setSaving(false);
    }
  };

  const addTask = () => {
    const newTask: TaskItem = {
      id: `task-${Date.now()}`,
      title: "",
      description: "",
      status: "pending",
      deadline: "",
      priority: "medium",
    };
    setTasks([...tasks, newTask]);
    markDirty();
  };

  const updateTask = (idx: number, field: string, value: string) => {
    const updated = [...tasks];
    (updated[idx] as any)[field] = value;
    setTasks(updated);
    markDirty();
  };

  const removeTask = (idx: number) => {
    setTasks(tasks.filter((_, i) => i !== idx));
    markDirty();
  };

  if (!activeProject || !node) {
    return (
      <div className="project-detail-empty">
        <p>{t("noProjectSelected")}</p>
      </div>
    );
  }

  return (
    <div className="project-detail">
      <div className="detail-header">
        <h3 className="detail-title">{node?.display_name || activeProject}</h3>
        <div className="detail-save-area">
          {saved && <span className="detail-saved">{t("saved")}</span>}
          <button
            className="btn btn-primary detail-save-btn"
            onClick={handleSave}
            disabled={saving || !dirty}
          >
            {saving ? t("saving") : t("save")}
          </button>
        </div>
      </div>

      {/* Goal - common to all */}
      <div className="detail-field">
        <label className="detail-label">{t("goalPlaceholder").replace("...", "")}</label>
        <textarea
          className="detail-textarea"
          rows={2}
          placeholder={t("goalPlaceholder")}
          value={goal}
          onChange={(e) => { setGoal(e.target.value); markDirty(); }}
        />
      </div>

      {/* Project Rules - common to all */}
      <div className="detail-rules-group">
        <div className="detail-field detail-rules-must">
          <label className="detail-label">{t("rulesMust")}</label>
          <textarea
            className="detail-textarea"
            rows={3}
            placeholder={t("rulesMustPlaceholder")}
            value={rulesMust}
            onChange={(e) => { setRulesMust(e.target.value); markDirty(); }}
          />
        </div>
        <div className="detail-field detail-rules-forbidden">
          <label className="detail-label">{t("rulesForbidden")}</label>
          <textarea
            className="detail-textarea"
            rows={3}
            placeholder={t("rulesForbiddenPlaceholder")}
            value={rulesForbidden}
            onChange={(e) => { setRulesForbidden(e.target.value); markDirty(); }}
          />
        </div>
      </div>

      {/* Parent project: overview, policy, roadmap */}
      {(isParent || !node.parent_id) && (
        <>
          <div className="detail-field">
            <label className="detail-label">{t("overview")}</label>
            <textarea
              className="detail-textarea"
              rows={3}
              placeholder={t("overviewPlaceholder")}
              value={overview}
              onChange={(e) => { setOverview(e.target.value); markDirty(); }}
            />
          </div>
          <div className="detail-field">
            <label className="detail-label">{t("policyLabel")}</label>
            <textarea
              className="detail-textarea"
              rows={3}
              placeholder={t("policyPlaceholder")}
              value={policy}
              onChange={(e) => { setPolicy(e.target.value); markDirty(); }}
            />
          </div>
          <div className="detail-field">
            <label className="detail-label">{t("roadmap")}</label>
            <textarea
              className="detail-textarea"
              rows={4}
              placeholder={t("roadmapPlaceholder")}
              value={roadmap}
              onChange={(e) => { setRoadmap(e.target.value); markDirty(); }}
            />
          </div>
        </>
      )}

      {/* Child project: description, deadline, tasks */}
      {node.parent_id && (
        <>
          <div className="detail-field">
            <label className="detail-label">{t("descriptionLabel")}</label>
            <textarea
              className="detail-textarea"
              rows={3}
              placeholder={t("descriptionPlaceholder")}
              value={description}
              onChange={(e) => { setDescription(e.target.value); markDirty(); }}
            />
          </div>
          <div className="detail-field">
            <label className="detail-label">{t("deadline")}</label>
            <input
              type="date"
              className="detail-input"
              value={deadline}
              onChange={(e) => { setDeadline(e.target.value); markDirty(); }}
            />
          </div>

          {/* Task list */}
          <div className="detail-field">
            <div className="detail-task-header">
              <label className="detail-label">{t("taskList")}</label>
              <button className="tree-action-btn" onClick={addTask}>+ {t("addTask")}</button>
            </div>
            <div className="detail-task-list">
              {tasks.map((task, idx) => (
                <div key={task.id} className="detail-task-item">
                  <div className="detail-task-row">
                    <select
                      className="detail-task-status"
                      value={task.status}
                      onChange={(e) => updateTask(idx, "status", e.target.value)}
                    >
                      <option value="pending">{t("pending")}</option>
                      <option value="in_progress">{t("inProgress")}</option>
                      <option value="done">{t("done")}</option>
                    </select>
                    <select
                      className="detail-task-priority"
                      value={task.priority}
                      onChange={(e) => updateTask(idx, "priority", e.target.value)}
                    >
                      <option value="high">{t("priorityHigh")}</option>
                      <option value="medium">{t("priorityMedium")}</option>
                      <option value="low">{t("priorityLow")}</option>
                    </select>
                    <input
                      className="detail-task-title"
                      placeholder={t("taskTitle")}
                      value={task.title}
                      onChange={(e) => updateTask(idx, "title", e.target.value)}
                    />
                    <input
                      type="date"
                      className="detail-task-deadline"
                      value={task.deadline}
                      onChange={(e) => updateTask(idx, "deadline", e.target.value)}
                    />
                    <button className="detail-task-remove" onClick={() => removeTask(idx)}>
                      {"\u2716"}
                    </button>
                  </div>
                  <textarea
                    className="detail-task-desc"
                    rows={1}
                    placeholder={t("descriptionPlaceholder")}
                    value={task.description}
                    onChange={(e) => updateTask(idx, "description", e.target.value)}
                  />
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {/* Agent Profiles */}
      <div className="detail-field">
        <label className="detail-label">{t("agentProfiles")}</label>
        <div className="agent-profiles-list">
          {AGENT_ROLES.map((role) => {
            const profile = agentProfiles[role.key] || { title: "", personality: "" };
            const loc = locale as Locale;
            const defTitle = role.defaultTitle[loc];
            const defPersonality = role.defaultPersonality[loc];
            return (
              <div key={role.key} className="agent-profile-card">
                <div className="agent-profile-header">
                  <span className="agent-profile-icon">{role.icon}</span>
                  <span className="agent-profile-role">{role.label[loc]}</span>
                </div>
                <input
                  className="agent-profile-input"
                  placeholder={defTitle}
                  value={profile.title}
                  onChange={(e) => {
                    setAgentProfiles({
                      ...agentProfiles,
                      [role.key]: { ...profile, title: e.target.value },
                    });
                    markDirty();
                  }}
                />
                <textarea
                  className="agent-profile-textarea"
                  rows={2}
                  placeholder={defPersonality}
                  value={profile.personality}
                  onChange={(e) => {
                    setAgentProfiles({
                      ...agentProfiles,
                      [role.key]: { ...profile, personality: e.target.value },
                    });
                    markDirty();
                  }}
                />
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
