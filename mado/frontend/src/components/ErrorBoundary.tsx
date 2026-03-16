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
        <div className="error-boundary" role="alert" aria-live="assertive">
          <div className="error-boundary-icon">{"\u26A0"}</div>
          <strong className="error-boundary-title">
            表示エラーが発生しました
          </strong>
          <p className="error-boundary-message">
            {this.state.error?.message || "予期しないエラーが発生しました"}
          </p>
          <div className="error-boundary-actions">
            <button
              className="btn btn-danger error-boundary-retry"
              onClick={() => this.setState({ hasError: false, error: null })}
            >
              再試行
            </button>
            <button
              className="btn error-boundary-reload"
              onClick={() => window.location.reload()}
            >
              ページを再読み込み
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
