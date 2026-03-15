"use client";

import { useState, useEffect, useCallback } from "react";
import * as api from "@/lib/api";
import { useI18n, type Locale } from "@/lib/i18n";
import { useInlineStatus, StatusIndicator } from "@/components/Toast";
import { ROLE_META } from "@/lib/constants";
import type { AgentInfo, AgentProfileAssignment } from "@/lib/types";

/* ── Types ────────────────────────────────────────────── */

interface GlobalProfile {
  id: string;
  name: string;
  additional_prompt: string;
  base_prompt: string;
  is_preset: boolean;
  created_from?: string | null;
}

interface Props {
  activeProject: string | null;
  agentProfiles: Record<string, AgentProfileAssignment>;
  runtimeAgents: AgentInfo[];
  onProfilesChanged?: () => void;
}

const ALL_ROLES = Object.keys(ROLE_META);

/* ── Component ────────────────────────────────────────── */

export function AgentPanel({ activeProject, agentProfiles, runtimeAgents, onProfilesChanged }: Props) {
  const { t, locale } = useI18n();
  const loc = locale as Locale;
  const { status, showStatus } = useInlineStatus();

  // Assignments (role → model mapping from agents.yaml)
  const [assignments, setAssignments] = useState<Record<string, string>>({});
  // Global profiles grouped by role
  const [globalProfiles, setGlobalProfiles] = useState<Record<string, GlobalProfile[]>>({});
  // UI state
  const [expandedRole, setExpandedRole] = useState<string | null>(null);
  const [editingProfile, setEditingProfile] = useState<string | null>(null); // profile id
  const [editName, setEditName] = useState("");
  const [editBasePrompt, setEditBasePrompt] = useState("");
  const [editPrompt, setEditPrompt] = useState("");
  const [creating, setCreating] = useState<{ role: string; mode: "new" | "clone"; sourceId?: string } | null>(null);
  const [saving, setSaving] = useState(false);

  /* ── Data loading ──────────────────────────────────── */

  const loadAssignments = useCallback(async () => {
    try {
      const data = await api.getAssignments();
      setAssignments(data.assignments || {});
    } catch { /* ignore */ }
  }, []);

  const loadProfiles = useCallback(async () => {
    try {
      const data = await api.listAllProfiles();
      setGlobalProfiles(data || {});
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    loadAssignments();
    loadProfiles();
  }, [loadAssignments, loadProfiles]);

  const runtimeMap = new Map(runtimeAgents.map((a) => [a.role, a]));
  const configuredRoles = Object.keys(assignments);

  // 2グループ: アクティブ（プロジェクトに追加済み）と登録済み（未追加）
  const activeProjectRoles = configuredRoles.filter(r => !!agentProfiles[r]);
  const availableRoles = configuredRoles.filter(r => !agentProfiles[r]);

  /* ── Handlers ──────────────────────────────────────── */

  const handleAddToProject = async (role: string) => {
    if (!activeProject) return;
    try {
      const updated = { ...agentProfiles, [role]: {} };
      await api.updateProjectConfig(activeProject, { agent_profiles: updated });
      showStatus(loc === "ja" ? `${role} をプロジェクトに追加` : `Added ${role}`, "success");
      onProfilesChanged?.();
    } catch (e: any) {
      showStatus(`Error: ${e.message}`, "error");
    }
  };

  const handleRemoveFromProject = async (role: string) => {
    if (!activeProject) return;
    try {
      const updated = { ...agentProfiles };
      delete updated[role];
      await api.updateProjectConfig(activeProject, { agent_profiles: updated });
      showStatus(loc === "ja" ? `${role} をプロジェクトから削除` : `Removed ${role}`, "success");
      onProfilesChanged?.();
    } catch (e: any) {
      showStatus(`Error: ${e.message}`, "error");
    }
  };

  const handleSelectProfile = async (role: string, profileId: string) => {
    if (!activeProject) return;
    try {
      const profile = (globalProfiles[role] || []).find(p => p.id === profileId);
      const updated = { ...agentProfiles };
      updated[role] = {
        profile_id: profileId,
        additional_prompt: profile?.additional_prompt || "",
      };
      await api.updateProjectConfig(activeProject, { agent_profiles: updated });
      showStatus(loc === "ja" ? "プロフィールを適用しました" : "Profile applied", "success");
      onProfilesChanged?.();
    } catch (e: any) {
      showStatus(`Error: ${e.message}`, "error");
    }
  };

  const startCreate = (role: string, mode: "new" | "clone", sourceId?: string) => {
    setCreating({ role, mode, sourceId });
    if (mode === "clone" && sourceId) {
      const source = (globalProfiles[role] || []).find(p => p.id === sourceId);
      setEditName(`${source?.name || ""} (copy)`);
      setEditPrompt(source?.additional_prompt || "");
    } else {
      setEditName("");
      setEditPrompt("");
    }
    setEditingProfile(null);
  };

  const handleSaveNew = async () => {
    if (!creating) return;
    if (!editName.trim()) {
      showStatus(loc === "ja" ? "名前を入力してください" : "Name required", "error");
      return;
    }
    setSaving(true);
    try {
      await api.createProfile(
        creating.role,
        editName.trim(),
        editPrompt,
        creating.mode === "clone" ? creating.sourceId : undefined,
        editBasePrompt,
      );
      showStatus(loc === "ja" ? "プロフィールを作成しました" : "Profile created", "success");
      setCreating(null);
      await loadProfiles();
    } catch (e: any) {
      showStatus(`Error: ${e.message}`, "error");
    } finally {
      setSaving(false);
    }
  };

  const startEdit = (profile: GlobalProfile) => {
    setEditingProfile(profile.id);
    setEditName(profile.is_preset ? "" : profile.name);
    setEditBasePrompt(profile.base_prompt || "");
    setEditPrompt(profile.additional_prompt);
    setCreating(null);
  };

  const handleSaveEdit = async (role: string) => {
    if (!editingProfile) return;
    const editingTarget = (globalProfiles[role] || []).find(p => p.id === editingProfile);
    if (!editName.trim()) {
      showStatus(
        loc === "ja" ? "名前を入力してください" : "Name is required",
        "error",
      );
      return;
    }

    // Preset: cannot overwrite, must save as new profile with a different name
    if (editingTarget?.is_preset) {
      if (editName.trim() === editingTarget.name) {
        showStatus(
          loc === "ja"
            ? "プリセットと同じ名前では保存できません。別の名前を付けてください。"
            : "Cannot use the same name as the preset. Please rename.",
          "error",
        );
        return;
      }
      setSaving(true);
      try {
        await api.createProfile(role, editName.trim(), editPrompt, editingProfile, editBasePrompt);
        showStatus(loc === "ja" ? "新しいプロフィールとして保存しました" : "Saved as new profile", "success");
        setEditingProfile(null);
        await loadProfiles();
      } catch (e: any) {
        showStatus(`Error: ${e.message}`, "error");
      } finally {
        setSaving(false);
      }
      return;
    }

    // Non-preset: normal update
    setSaving(true);
    try {
      await api.updateProfile(role, editingProfile, {
        name: editName.trim(),
        additional_prompt: editPrompt,
        base_prompt: editBasePrompt,
      });
      showStatus(loc === "ja" ? "保存しました" : "Saved", "success");
      setEditingProfile(null);
      await loadProfiles();
    } catch (e: any) {
      showStatus(`Error: ${e.message}`, "error");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (role: string, profileId: string) => {
    setSaving(true);
    try {
      await api.deleteProfile(role, profileId);
      showStatus(loc === "ja" ? "削除しました" : "Deleted", "success");
      await loadProfiles();
    } catch (e: any) {
      showStatus(`Error: ${e.message}`, "error");
    } finally {
      setSaving(false);
    }
  };

  /* ── Render ────────────────────────────────────────── */

  return (
    <div className="agents-tab-content">
      <div className="agents-tab-header">
        <h3 className="agents-tab-title">{t("agentsTab")}</h3>
        {status && <StatusIndicator status={status} />}
      </div>

      {configuredRoles.length === 0 ? (
        <div className="agents-tab-empty">
          <p>{t("noAgentsYet")}</p>
        </div>
      ) : (
        <>
          {/* ── アクティブ（プロジェクトに追加済み） ── */}
          {activeProjectRoles.length > 0 && (
            <div className="agents-tab-group">
              <h4 className="agents-tab-group-title">{loc === "ja" ? "アクティブ" : "Active"}</h4>
              <div className="agents-tab-list">
                {activeProjectRoles.map((role) => {
                  const meta = ROLE_META[role] || { icon: "\uD83E\uDD16", label: { en: role, ja: role }, color: "#888", border: "#888" };
                  const runtime = runtimeMap.get(role);
                  const model = runtime?.model || assignments[role] || "\u2014";
                  const isRunning = !!runtime;
                  const isExpanded = expandedRole === role;
                  const roleProfiles = (globalProfiles[role] || []).filter(p => !p.is_preset);
                  const selectedId = agentProfiles[role]?.profile_id || null;

                  return (
                    <div key={role} className={`agents-tab-card agents-tab-card-active`}>
                      <div
                        className="agents-tab-card-header"
                        onClick={() => setExpandedRole(isExpanded ? null : role)}
                        style={{ cursor: "pointer" }}
                        title={meta.label[loc]}
                      >
                        <span className="agents-tab-card-icon">{meta.icon}</span>
                        <div className="agents-tab-card-info">
                          <span className="agents-tab-card-role">{meta.label[loc]}</span>
                          <span className="agents-tab-card-model">{model}</span>
                        </div>
                        <span className={`agents-tab-card-status ${isRunning ? "agents-tab-status-active" : "agents-tab-status-idle"}`}>
                          {isRunning ? t("running") : t("initialized")}
                        </span>
                        <span className="agents-tab-card-chevron">{isExpanded ? "\u25B2" : "\u25BC"}</span>
                      </div>

                      {isExpanded && (
                        <div className="agents-tab-profiles">
                          {/* Remove from project */}
                          <button
                            className="agents-tab-remove-btn"
                            onClick={() => handleRemoveFromProject(role)}
                          >
                            {loc === "ja" ? "プロジェクトから外す" : "Remove from project"}
                          </button>

                          {/* Profiles list (custom only) */}
                          {roleProfiles.map((profile) => {
                            const isSelected = selectedId === profile.id;
                            const isEditingThis = editingProfile === profile.id;

                            return (
                              <div key={profile.id} className={`agents-tab-profile ${isSelected ? "agents-tab-profile-selected" : ""}`}>
                                {isEditingThis ? (
                                  <div className="agents-tab-editor">
                                    <input
                                      className="agents-tab-editor-input"
                                      value={editName}
                                      onChange={(e) => setEditName(e.target.value)}
                                      placeholder={loc === "ja" ? "プロフィール名" : "Profile name"}
                                    />
                                    <label className="agents-tab-editor-label" style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "0.5rem", display: "block" }}>
                                      {loc === "ja" ? "ベースプロンプト（ロール定義）" : "Base Prompt (role definition)"}
                                    </label>
                                    <textarea
                                      className="agents-tab-editor-textarea"
                                      value={editBasePrompt}
                                      onChange={(e) => setEditBasePrompt(e.target.value)}
                                      placeholder={loc === "ja" ? "ロール定義プロンプト" : "Role definition prompt"}
                                      rows={8}
                                      style={{ fontFamily: "monospace", fontSize: "0.8rem" }}
                                    />
                                    <label className="agents-tab-editor-label" style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "0.5rem", display: "block" }}>
                                      {loc === "ja" ? "追加プロンプト（カスタマイズ）" : "Additional Prompt"}
                                    </label>
                                    <textarea
                                      className="agents-tab-editor-textarea"
                                      value={editPrompt}
                                      onChange={(e) => setEditPrompt(e.target.value)}
                                      placeholder={loc === "ja" ? "追加プロンプト" : "Additional prompt"}
                                      rows={4}
                                    />
                                    <div className="agents-tab-editor-actions">
                                      <button className="agents-tab-editor-cancel" onClick={() => setEditingProfile(null)} disabled={saving}>
                                        {loc === "ja" ? "キャンセル" : "Cancel"}
                                      </button>
                                      <button className="agents-tab-editor-save" onClick={() => handleSaveEdit(role)} disabled={saving}>
                                        {saving ? "..." : (loc === "ja" ? "保存" : "Save")}
                                      </button>
                                    </div>
                                  </div>
                                ) : (
                                  <div className="agents-tab-profile-row">
                                    <div className="agents-tab-profile-info" onClick={() => handleSelectProfile(role, profile.id)}>
                                      <span className={`agents-tab-profile-radio ${isSelected ? "agents-tab-profile-radio-on" : ""}`} />
                                      <span className="agents-tab-profile-name">{profile.name}</span>
                                    </div>
                                    <div className="agents-tab-profile-actions">
                                      <button className="agents-tab-btn-sm" onClick={() => startEdit(profile)} title={loc === "ja" ? "編集" : "Edit"}>{"\u270E"}</button>
                                      <button className="agents-tab-btn-sm" onClick={() => startCreate(role, "clone", profile.id)} title={loc === "ja" ? "コピー" : "Clone"}>{"\u2398"}</button>
                                      <button className="agents-tab-btn-sm agents-tab-btn-danger" onClick={() => handleDelete(role, profile.id)} title={loc === "ja" ? "削除" : "Delete"}>{"\u2715"}</button>
                                    </div>
                                  </div>
                                )}

                                {!isEditingThis && isSelected && profile.base_prompt && (
                                  <div className="agents-tab-profile-preview" style={{ whiteSpace: "pre-wrap", fontSize: "0.75rem", lineHeight: 1.4, maxHeight: "8rem", overflow: "auto", background: "var(--bg-secondary, #1a1a2e)", padding: "0.5rem", borderRadius: "4px", margin: "0.25rem 0" }}>
                                    {profile.base_prompt}
                                  </div>
                                )}
                                {!isEditingThis && profile.additional_prompt && (
                                  <div className="agents-tab-profile-preview">
                                    {profile.additional_prompt.split("\n").slice(0, 2).join(" ")}
                                    {profile.additional_prompt.split("\n").length > 2 ? "..." : ""}
                                  </div>
                                )}
                              </div>
                            );
                          })}

                          {/* Create new form */}
                          {creating && creating.role === role ? (
                            <div className="agents-tab-editor agents-tab-editor-new">
                              <div className="agents-tab-editor-title">
                                {creating.mode === "clone"
                                  ? (loc === "ja" ? "既存からコピーして作成" : "Clone from existing")
                                  : (loc === "ja" ? "新規プロフィール作成" : "New profile")
                                }
                              </div>
                              <input className="agents-tab-editor-input" value={editName} onChange={(e) => setEditName(e.target.value)} placeholder={loc === "ja" ? "プロフィール名" : "Profile name"} />
                              <textarea className="agents-tab-editor-textarea" value={editPrompt} onChange={(e) => setEditPrompt(e.target.value)} placeholder={loc === "ja" ? "追加プロンプト" : "Additional prompt"} rows={6} />
                              <div className="agents-tab-editor-actions">
                                <button className="agents-tab-editor-cancel" onClick={() => setCreating(null)} disabled={saving}>{loc === "ja" ? "キャンセル" : "Cancel"}</button>
                                <button className="agents-tab-editor-save" onClick={handleSaveNew} disabled={saving}>{saving ? "..." : (loc === "ja" ? "作成" : "Create")}</button>
                              </div>
                            </div>
                          ) : (
                            <div className="agents-tab-add-profile-btns">
                              <button className="agents-tab-add-profile-btn" onClick={() => startCreate(role, "new")}>+ {loc === "ja" ? "新規作成" : "New"}</button>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* ── 登録済み（未追加） ── */}
          {availableRoles.length > 0 && (
            <div className="agents-tab-group">
              <h4 className="agents-tab-group-title">{loc === "ja" ? "登録済み" : "Available"}</h4>
              <div className="agents-tab-list">
                {availableRoles.map((role) => {
                  const meta = ROLE_META[role] || { icon: "\uD83E\uDD16", label: { en: role, ja: role }, color: "#888", border: "#888" };
                  const model = assignments[role] || "\u2014";

                  return (
                    <div key={role} className="agents-tab-card agents-tab-card-available">
                      <div className="agents-tab-card-header" style={{ cursor: "default" }}>
                        <span className="agents-tab-card-icon">{meta.icon}</span>
                        <div className="agents-tab-card-info">
                          <span className="agents-tab-card-role">{meta.label[loc]}</span>
                          <span className="agents-tab-card-model">{model}</span>
                        </div>
                        <button
                          className="agents-tab-add-btn"
                          onClick={() => handleAddToProject(role)}
                        >
                          + {loc === "ja" ? "追加" : "Add"}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
