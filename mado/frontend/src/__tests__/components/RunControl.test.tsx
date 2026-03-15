import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { RunControl } from "@/components/RunControl";
import { I18nProvider } from "@/lib/i18n";
import type { RunStatus } from "@/lib/types";

// Mock the api module
vi.mock("@/lib/api", () => ({
  startRun: vi.fn(),
  stopRun: vi.fn(),
}));

import * as api from "@/lib/api";

function renderRunControl(overrides: Partial<Parameters<typeof RunControl>[0]> = {}) {
  const defaultProps = {
    activeProject: "test-project",
    runStatus: null as RunStatus | null,
    onRefresh: vi.fn(),
    goal: "Build a REST API",
    maxIter: 200,
    onMaxIterChange: vi.fn(),
  };
  return render(
    <I18nProvider>
      <RunControl {...defaultProps} {...overrides} />
    </I18nProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("RunControl", () => {
  it("shows select project hint when no active project", () => {
    renderRunControl({ activeProject: null });
    expect(screen.getByText("プロジェクトを選択してください")).toBeInTheDocument();
  });

  it("shows start button when not running", () => {
    renderRunControl();
    expect(screen.getByText("開始")).toBeInTheDocument();
  });

  it("shows stop button when running", () => {
    renderRunControl({
      runStatus: { status: "running", iteration: 3, max_iterations: 30 },
    });
    expect(screen.getByText("停止")).toBeInTheDocument();
  });

  it("shows iteration count and badge when status is provided", () => {
    renderRunControl({
      runStatus: { status: "running", iteration: 5, max_iterations: 30 },
    });
    expect(screen.getByText("5/30")).toBeInTheDocument();
    expect(screen.getByText("running")).toBeInTheDocument();
  });

  it("disables iteration input when running", () => {
    renderRunControl({
      runStatus: { status: "running", iteration: 1, max_iterations: 30 },
    });
    const input = screen.getByDisplayValue("30");
    expect(input).toBeDisabled();
  });

  it("calls onMaxIterChange when input changes", () => {
    const onMaxIterChange = vi.fn();
    renderRunControl({ onMaxIterChange });
    const input = screen.getByDisplayValue("30");
    fireEvent.change(input, { target: { value: "50" } });
    expect(onMaxIterChange).toHaveBeenCalledWith(50);
  });

  it("calls startRun when start button clicked", async () => {
    (api.startRun as ReturnType<typeof vi.fn>).mockResolvedValue({ status: "started" });
    const onRefresh = vi.fn();
    renderRunControl({ onRefresh });

    fireEvent.click(screen.getByText("開始"));
    await waitFor(() => expect(api.startRun).toHaveBeenCalledWith("test-project", "Build a REST API", 30));
    await waitFor(() => expect(onRefresh).toHaveBeenCalled());
  });

  it("shows warning when goal is empty", async () => {
    renderRunControl({ goal: "  " });
    fireEvent.click(screen.getByText("開始"));
    // Should NOT call startRun
    expect(api.startRun).not.toHaveBeenCalled();
  });

  it("calls stopRun when stop button clicked", async () => {
    (api.stopRun as ReturnType<typeof vi.fn>).mockResolvedValue({ status: "stopped" });
    const onRefresh = vi.fn();
    renderRunControl({
      runStatus: { status: "running", iteration: 2, max_iterations: 30 },
      onRefresh,
    });

    fireEvent.click(screen.getByText("停止"));
    await waitFor(() => expect(api.stopRun).toHaveBeenCalledWith("test-project"));
  });

  it("shows exhausted banner when iterations are used up", () => {
    const onExtend = vi.fn();
    renderRunControl({
      runStatus: { status: "completed", iteration: 30, max_iterations: 30 },
      onExtendIterations: onExtend,
    });
    // Button text is "延長 (+30)" split across elements, use a button selector
    const extendBtn = screen.getByRole("button", { name: /延長/ });
    fireEvent.click(extendBtn);
    expect(onExtend).toHaveBeenCalledWith(30);
  });
});
