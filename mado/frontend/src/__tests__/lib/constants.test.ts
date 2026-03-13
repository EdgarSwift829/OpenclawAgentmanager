import { describe, it, expect } from "vitest";
import { ROLE_META, TASK_STATE_META } from "@/lib/constants";

describe("ROLE_META", () => {
  const expectedRoles = [
    "cto", "manager", "researcher", "engineer", "reviewer",
    "tester", "optimizer", "documenter", "marketer",
  ];

  it("contains all expected roles", () => {
    for (const role of expectedRoles) {
      expect(ROLE_META[role]).toBeDefined();
    }
  });

  it("each role has icon, label (en/ja), color, border", () => {
    for (const role of expectedRoles) {
      const meta = ROLE_META[role];
      expect(meta.icon).toBeTruthy();
      expect(meta.label.en).toBeTruthy();
      expect(meta.label.ja).toBeTruthy();
      expect(meta.color).toMatch(/^#/);
      expect(meta.border).toMatch(/^#/);
    }
  });
});

describe("TASK_STATE_META", () => {
  const expectedStates = [
    "idle", "queued", "running", "waiting_review",
    "completed", "failed", "rejected",
  ];

  it("contains all expected task states", () => {
    for (const state of expectedStates) {
      expect(TASK_STATE_META[state]).toBeDefined();
    }
  });

  it("each state has label (en/ja), color, dot", () => {
    for (const state of expectedStates) {
      const meta = TASK_STATE_META[state];
      expect(meta.label.en).toBeTruthy();
      expect(meta.label.ja).toBeTruthy();
      expect(meta.color).toMatch(/^#/);
      expect(meta.dot).toBeTruthy();
    }
  });
});
