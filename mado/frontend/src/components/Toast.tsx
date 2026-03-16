"use client";

import { useState, useCallback, useRef } from "react";

export type StatusType = "success" | "error" | "info" | "warning";

export interface InlineStatus {
  message: string;
  type: StatusType;
}

const STATUS_ICONS: Record<StatusType, string> = {
  success: "\u2713",
  error: "\u2717",
  warning: "\u26A0",
  info: "\u2026",
};

const STATUS_ARIA: Record<StatusType, string> = {
  success: "Success",
  error: "Error",
  warning: "Warning",
  info: "Info",
};

/**
 * Hook for inline status display near buttons.
 * Returns [status, showStatus] - render status near the triggering button.
 * Auto-clears after a timeout (5s for errors, 3s for others).
 */
export function useInlineStatus() {
  const [status, setStatus] = useState<InlineStatus | null>(null);
  const [fading, setFading] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const fadeRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const showStatus = useCallback((message: string, type: StatusType = "info") => {
    if (timerRef.current) clearTimeout(timerRef.current);
    if (fadeRef.current) clearTimeout(fadeRef.current);
    setFading(false);
    setStatus({ message, type });
    const ms = type === "error" ? 5000 : 3000;
    // Start fade-out 500ms before removal
    fadeRef.current = setTimeout(() => setFading(true), ms - 500);
    timerRef.current = setTimeout(() => {
      setStatus(null);
      setFading(false);
    }, ms);
  }, []);

  const clearStatus = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    if (fadeRef.current) clearTimeout(fadeRef.current);
    setStatus(null);
    setFading(false);
  }, []);

  return { status, showStatus, clearStatus, fading };
}

/** Small inline status indicator component */
export function StatusIndicator({ status, fading }: { status: InlineStatus | null; fading?: boolean }) {
  if (!status) return null;
  return (
    <span
      className={`inline-status inline-status-${status.type} ${fading ? "inline-status-fading" : ""}`}
      role="status"
      aria-live="polite"
      aria-label={`${STATUS_ARIA[status.type]}: ${status.message}`}
    >
      <span className="inline-status-icon" aria-hidden="true">
        {STATUS_ICONS[status.type]}
      </span>
      <span className="inline-status-text">{status.message}</span>
    </span>
  );
}
