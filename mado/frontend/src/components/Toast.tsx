"use client";

import { useState, useCallback, useRef } from "react";

export type StatusType = "success" | "error" | "info" | "warning";

export interface InlineStatus {
  message: string;
  type: StatusType;
}

/**
 * Hook for inline status display near buttons.
 * Returns [status, showStatus] - render status near the triggering button.
 * Auto-clears after a timeout (5s for errors, 3s for others).
 */
export function useInlineStatus() {
  const [status, setStatus] = useState<InlineStatus | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const showStatus = useCallback((message: string, type: StatusType = "info") => {
    if (timerRef.current) clearTimeout(timerRef.current);
    setStatus({ message, type });
    const ms = type === "error" ? 5000 : 3000;
    timerRef.current = setTimeout(() => setStatus(null), ms);
  }, []);

  const clearStatus = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    setStatus(null);
  }, []);

  return { status, showStatus, clearStatus };
}

/** Small inline status indicator component */
export function StatusIndicator({ status }: { status: InlineStatus | null }) {
  if (!status) return null;
  return (
    <span className={`inline-status inline-status-${status.type}`}>
      <span className="inline-status-icon">
        {status.type === "success" && "✓"}
        {status.type === "error" && "✗"}
        {status.type === "warning" && "⚠"}
        {status.type === "info" && "…"}
      </span>
      <span className="inline-status-text">{status.message}</span>
    </span>
  );
}
