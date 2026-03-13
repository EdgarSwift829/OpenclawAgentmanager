"use client";

import React from "react";

interface Props {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <div style={{
          padding: "1rem",
          margin: "0.5rem",
          background: "rgba(239, 68, 68, 0.1)",
          border: "1px solid rgba(239, 68, 68, 0.3)",
          borderRadius: "8px",
          color: "#ef4444",
          fontSize: "0.85rem",
        }}>
          <strong>表示エラーが発生しました</strong>
          <p style={{ margin: "0.5rem 0 0", opacity: 0.8 }}>
            {this.state.error?.message || "Unknown error"}
          </p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            style={{
              marginTop: "0.5rem",
              padding: "0.25rem 0.75rem",
              background: "transparent",
              border: "1px solid #ef4444",
              borderRadius: "4px",
              color: "#ef4444",
              cursor: "pointer",
              fontSize: "0.8rem",
            }}
          >
            再試行
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
