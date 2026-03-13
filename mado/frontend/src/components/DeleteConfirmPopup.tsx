"use client";

interface DeletePopupData {
  projectId: string;
  displayName: string;
  x: number;
  y: number;
}

interface Props {
  popup: DeletePopupData;
  onConfirm: () => void;
  onCancel: () => void;
  deleteLabel: string;
  cancelLabel: string;
}

export function DeleteConfirmPopup({ popup, onConfirm, onCancel, deleteLabel, cancelLabel }: Props) {
  return (
    <div
      className="delete-popup-overlay"
      onClick={onCancel}
      role="dialog"
      aria-modal="true"
      aria-label={`${popup.displayName}の削除確認`}
    >
      <div
        className="delete-popup"
        style={{ left: popup.x, top: popup.y }}
        onClick={(e) => e.stopPropagation()}
      >
        <p className="delete-popup-text" id="delete-popup-desc">
          「{popup.displayName}」を削除しますか？
        </p>
        <div className="delete-popup-actions">
          <button
            className="btn btn-danger delete-popup-confirm"
            onClick={onConfirm}
          >
            {deleteLabel}
          </button>
          <button
            className="delete-popup-cancel"
            onClick={onCancel}
          >
            {cancelLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
