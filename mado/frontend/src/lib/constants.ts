/* ─── Shared role metadata ──────────────────────────────── */
export const ROLE_META: Record<
  string,
  { icon: string; label: { en: string; ja: string }; color: string; border: string }
> = {
  cto:        { icon: "\uD83D\uDCCB", label: { en: "CTO",        ja: "CTO"              }, color: "#f59e0b", border: "#f59e0b" },
  manager:    { icon: "\uD83D\uDCC1", label: { en: "PM",         ja: "PM"               }, color: "#3b82f6", border: "#3b82f6" },
  researcher: { icon: "\uD83D\uDD0D", label: { en: "Researcher", ja: "リサーチャー"      }, color: "#8b5cf6", border: "#8b5cf6" },
  engineer:   { icon: "\u2699\uFE0F", label: { en: "Engineer",   ja: "エンジニア"        }, color: "#22c55e", border: "#22c55e" },
  reviewer:   { icon: "\uD83D\uDCDD", label: { en: "Reviewer",   ja: "レビュアー"        }, color: "#ec4899", border: "#ec4899" },
  tester:     { icon: "\uD83E\uDDEA", label: { en: "Tester",     ja: "テスター"          }, color: "#06b6d4", border: "#06b6d4" },
  optimizer:  { icon: "\u26A1",       label: { en: "Optimizer",   ja: "オプティマイザー"  }, color: "#f97316", border: "#f97316" },
  documenter: { icon: "\uD83D\uDCD6", label: { en: "Documenter", ja: "ドキュメンター"    }, color: "#64748b", border: "#64748b" },
  marketer:   { icon: "\uD83D\uDCE2", label: { en: "Marketer",   ja: "マーケター"        }, color: "#e11d48", border: "#e11d48" },
};

/* ─── Shared task state metadata ───────────────────────── */
export const TASK_STATE_META: Record<
  string,
  { label: { en: string; ja: string }; color: string; dot: string }
> = {
  idle:            { label: { en: "Idle",            ja: "待機"       }, color: "#555",    dot: "\u25CB" },
  queued:          { label: { en: "Queued",          ja: "待ち"       }, color: "#eab308", dot: "\u25D4" },
  running:         { label: { en: "Running",         ja: "実行中"     }, color: "#8b5cf6", dot: "\u25C9" },
  waiting_review:  { label: { en: "Awaiting Review", ja: "レビュー待ち" }, color: "#f59e0b", dot: "\u25D0" },
  completed:       { label: { en: "Done",            ja: "完了"       }, color: "#22c55e", dot: "\u25CF" },
  failed:          { label: { en: "Failed",          ja: "失敗"       }, color: "#ef4444", dot: "\u2716" },
  rejected:        { label: { en: "Rejected",        ja: "差し戻し"   }, color: "#f97316", dot: "\u21A9" },
};
