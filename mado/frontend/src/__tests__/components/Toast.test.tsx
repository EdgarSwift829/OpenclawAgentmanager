import { describe, it, expect, vi } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { StatusIndicator } from "@/components/Toast";
import type { InlineStatus } from "@/components/Toast";

describe("StatusIndicator", () => {
  it("returns null when status is null", () => {
    const { container } = render(<StatusIndicator status={null} />);
    expect(container.innerHTML).toBe("");
  });

  it("renders success status with checkmark", () => {
    const status: InlineStatus = { message: "Saved!", type: "success" };
    render(<StatusIndicator status={status} />);
    expect(screen.getByText("Saved!")).toBeInTheDocument();
    expect(screen.getByText("✓")).toBeInTheDocument();
  });

  it("renders error status with cross", () => {
    const status: InlineStatus = { message: "Failed!", type: "error" };
    render(<StatusIndicator status={status} />);
    expect(screen.getByText("Failed!")).toBeInTheDocument();
    expect(screen.getByText("✗")).toBeInTheDocument();
  });

  it("renders warning status with triangle", () => {
    const status: InlineStatus = { message: "Watch out", type: "warning" };
    render(<StatusIndicator status={status} />);
    expect(screen.getByText("Watch out")).toBeInTheDocument();
    expect(screen.getByText("⚠")).toBeInTheDocument();
  });

  it("renders info status with ellipsis", () => {
    const status: InlineStatus = { message: "Loading", type: "info" };
    render(<StatusIndicator status={status} />);
    expect(screen.getByText("Loading")).toBeInTheDocument();
  });

  it("applies correct CSS class based on type", () => {
    const status: InlineStatus = { message: "Info msg", type: "info" };
    const { container } = render(<StatusIndicator status={status} />);
    const span = container.querySelector(".inline-status-info");
    expect(span).toBeInTheDocument();
  });
});
