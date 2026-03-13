"use client";

import type { TKey } from "@/lib/i18n";

interface ContextMenuState {
  visible: boolean;
  x: number;
  y: number;
  projectId: string;
  displayName: string;
  isArchived: boolean;
  hasChildren: boolean;
}

interface Props {
  menu: ContextMenuState;
  onClose: () => void;
  onRename: (projectId: string) => void;
  onAddChild: (projectId: string) => void;
  onArchiveToggle: (projectId: string) => void;
  onDelete: (projectId: string, displayName: string, event: React.MouseEvent) => void;
  t: (key: TKey) => string;
}

export function ProjectContextMenu({ menu, onClose, onRename, onAddChild, onArchiveToggle, onDelete, t }: Props) {
  if (!menu.visible) return null;

  return (
    <div
      className="context-menu"
      style={{ left: menu.x, top: menu.y }}
      onClick={(e) => e.stopPropagation()}
      role="menu"
      aria-label={`${menu.displayName}のメニュー`}
    >
      <button
        className="context-menu-item"
        role="menuitem"
        onClick={() => {
          onClose();
          onRename(menu.projectId);
        }}
      >
        ✏️ {t("renameProject")}
      </button>
      <button
        className="context-menu-item"
        role="menuitem"
        onClick={() => {
          onClose();
          onAddChild(menu.projectId);
        }}
      >
        ➕ {t("addSubProject")}
      </button>
      <div className="context-menu-separator" role="separator" />
      <button
        className="context-menu-item"
        role="menuitem"
        onClick={() => {
          onClose();
          onArchiveToggle(menu.projectId);
        }}
      >
        {menu.isArchived ? "↩ " : "📦 "}
        {menu.isArchived ? t("unarchive") : t("archive")}
      </button>
      <div className="context-menu-separator" role="separator" />
      <button
        className="context-menu-item context-menu-item-danger"
        role="menuitem"
        onClick={(e) => {
          onClose();
          onDelete(menu.projectId, menu.displayName, e);
        }}
      >
        🗑 {t("deleteProject")}
      </button>
    </div>
  );
}
