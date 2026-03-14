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

  /* ── Handlers ──────────────────────────────────────── */

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
        <div className="agents-tab-list">
          {configuredRoles.map((role) => {
            const meta = ROLE_META[role] || { icon: "\uD83E\uDD16", label: { en: role, ja: role }, color: "#888", border: "#888" };
            const runtime = runtimeMap.get(role);
            const model = runtime?.model || assignments[role] || "\u2014";
            const isActive = !!runtime;
            const isExpanded = expandedRole === role;
            const roleProfiles = globalProfiles[role] || [];
            const selectedId = agentProfiles[role]?.profile_id || null;

            return (
              <div key={role} className={`agents-tab-card ${isActive ? "agents-tab-card-active" : ""}`}>
                {/* Role header */}
                <div
                  className="agents-tab-card-header"
                  onClick={() => setExpandedRole(isExpanded ? null : role)}
                  style={{ cursor: "pointer" }}
                >
                  <span className="agents-tab-card-icon">{meta.icon}</span>
                  <div className="agents-tab-card-info">
                    <span className="agents-tab-card-role">{meta.label[loc]}</span>
                    <span className="agents-tab-card-model">{model}</span>
                  </div>
                  <span className={`agents-tab-card-status ${isActive ? "agents-tab-status-active" : "agents-tab-status-idle"}`}>
                    {isActive ? t("running") : t("initialized")}
                  </span>
                  <span className="agents-tab-card-badge">{roleProfiles.length}</span>
                  <span className="agents-tab-card-chevron">{isExpanded ? "\u25B2" : "\u25BC"}</span>
                </div>

                {/* Expanded: profiles list */}
                {isExpanded && (
                  <div className="agents-tab-profiles">
                    {/* Preset note */}
                    <div className="agents-tab-preset">
                      <div className="agents-tab-preset-text">
                        {loc === "ja"
                          ? "プリセットは編集可能ですが上書き保存はできません。編集後は別名で新しいプロフィールとして保存されます。"
                          : "Presets can be edited but not overwritten. Edits are saved as a new profile with a different name."
                        }
                      </div>
                    </div>

                    {/* Profiles list (preset + custom) */}
                    {roleProfiles.map((profile) => {
                      const isSelected = selectedId === profile.id;
                      const isEditingThis = editingProfile === profile.id;

                      return (
                        <div key={profile.id} className={`agents-tab-profile ${isSelected ? "agents-tab-profile-selected" : ""}`}>
                          {isEditingThis ? (
                            /* Edit form */
                            <div className="agents-tab-editor">
                              {profile.is_preset && (
                                <div className="agents-tab-editor-hint">
                                  {loc === "ja"
                                    ? "プリセットを編集中 - 別名で新しいプロフィールとして保存されます"
                                    : "Editing preset - will be saved as a new profile with a different name"
                                  }
                                </div>
                              )}
                              <input
                                className="agents-tab-editor-input"
                                value={editName}
                                onChange={(e) => setEditName(e.target.value)}
                                placeholder={loc === "ja" ? "新しいプロフィール名を入力" : "Enter new profile name"}
                              />
                              <label className="agents-tab-editor-label" style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "0.5rem", display: "block" }}>
                                {loc === "ja" ? "ベースプロンプト（ロール定義）" : "Base Prompt (role definition)"}
                              </label>
                              <textarea
                                className="agents-tab-editor-textarea"
                                value={editBasePrompt}
                                onChange={(e) => setEditBasePrompt(e.target.value)}
                                placeholder={loc === "ja"
                                  ? "このロールの基本的な振る舞いを定義するプロンプト"
                                  : "Base prompt defining this role's behavior"
                                }
                                rows={8}
                                style={{ fontFamily: "monospace", fontSize: "0.8rem" }}
                              />
                              <label className="agents-tab-editor-label" style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "0.5rem", display: "block" }}>
                                {loc === "ja" ? "追加プロンプト（カスタマイズ）" : "Additional Prompt (customization)"}
                              </label>
                              <textarea
                                className="agents-tab-editor-textarea"
                                value={editPrompt}
                                onChange={(e) => setEditPrompt(e.target.value)}
                                placeholder={loc === "ja"
                                  ? "追加プロンプト（ベースに加えて適用されます）"
                                  : "Additional prompt (applied on top of base)"
                                }
                                rows={4}
                              />
                              <div className="agents-tab-editor-actions">
                                <button className="agents-tab-editor-cancel" onClick={() => setEditingProfile(null)} disabled={saving}>
                                  {loc === "ja" ? "キャンセル" : "Cancel"}
                                </button>
                                <button className="agents-tab-editor-save" onClick={() => handleSaveEdit(role)} disabled={saving}>
                                  {saving ? "..." : (profile.is_preset
                                    ? (loc === "ja" ? "別名で保存" : "Save as new")
                                    : (loc === "ja" ? "保存" : "Save")
                                  )}
                                </button>
                              </div>
                            </div>
                          ) : (
                            /* Display */
                            <div className="agents-tab-profile-row">
                              <div className="agents-tab-profile-info" onClick={() => handleSelectProfile(role, profile.id)}>
                                <span className={`agents-tab-profile-radio ${isSelected ? "agents-tab-profile-radio-on" : ""}`} />
                                <span className="agents-tab-profile-name">
                                  {profile.name}
                                  {profile.is_preset && <span className="agents-tab-preset-tag">PRESET</span>}
                                </span>
                              </div>
                              <div className="agents-tab-profile-actions">
                                <button className="agents-tab-btn-sm" onClick={() => startEdit(profile)} title={loc === "ja" ? "編集" : "Edit"}>
                                  {"\u270E"}
                                </button>
                                {!profile.is_preset && (
                                  <>
                                    <button className="agents-tab-btn-sm" onClick={() => startCreate(role, "clone", profile.id)} title={loc === "ja" ? "コピーして作成" : "Clone"}>
                                      {"\u2398"}
                                    </button>
                                    <button className="agents-tab-btn-sm agents-tab-btn-danger" onClick={() => handleDelete(role, profile.id)} title={loc === "ja" ? "削除" : "Delete"}>
                                      {"\u2715"}
                                    </button>
                                  </>
                                )}
                              </div>
                            </div>
                          )}

                          {/* Preview base_prompt + additional_prompt if not editing */}
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
                        <input
                          className="agents-tab-editor-input"
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          placeholder={loc === "ja" ? "プロフィール名" : "Profile name"}
                        />
                        <textarea
                          className="agents-tab-editor-textarea"
                          value={editPrompt}
                          onChange={(e) => setEditPrompt(e.target.value)}
                          placeholder={loc === "ja"
                            ? "追加プロンプト（プリセットに加えて適用されます）"
                            : "Additional prompt (applied on top of preset)"
                          }
                          rows={6}
                        />
                        <div className="agents-tab-editor-actions">
                          <button className="agents-tab-editor-cancel" onClick={() => setCreating(null)} disabled={saving}>
                            {loc === "ja" ? "キャンセル" : "Cancel"}
                          </button>
                          <button className="agents-tab-editor-save" onClick={handleSaveNew} disabled={saving}>
                            {saving ? "..." : (loc === "ja" ? "作成" : "Create")}
                          </button>
                        </div>
                      </div>
                    ) : (
                      /* Add buttons */
                      <div className="agents-tab-add-profile-btns">
                        <button className="agents-tab-add-profile-btn" onClick={() => startCreate(role, "new")}>
                          + {loc === "ja" ? "新規作成" : "New"}
                        </button>
                        {roleProfiles.length > 0 && (
                          <button className="agents-tab-add-profile-btn" onClick={() => startCreate(role, "clone", roleProfiles[roleProfiles.length - 1]?.id)}>
                            + {loc === "ja" ? "既存からコピー" : "Clone"}
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
