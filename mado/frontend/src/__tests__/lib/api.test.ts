import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  listProjects,
  getProject,
  createProject,
  deleteProject,
  startRun,
  stopRun,
  listModels,
  switchModel,
  reorderRoles,
  connectWebSocket,
} from "@/lib/api";

const mockFetch = global.fetch as ReturnType<typeof vi.fn>;

function mockOk(data: unknown) {
  mockFetch.mockResolvedValueOnce({
    ok: true,
    json: () => Promise.resolve(data),
  } as Response);
}

function mockError(status: number, detail: string) {
  mockFetch.mockResolvedValueOnce({
    ok: false,
    status,
    statusText: "Bad Request",
    json: () => Promise.resolve({ detail }),
  } as unknown as Response);
}

beforeEach(() => {
  mockFetch.mockReset();
});

describe("fetchJSON wrapper", () => {
  it("listProjects calls GET /api/projects/", async () => {
    mockOk({ projects: [] });
    const result = await listProjects();
    expect(result).toEqual({ projects: [] });
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/projects/",
      expect.objectContaining({ headers: { "Content-Type": "application/json" } }),
    );
  });

  it("getProject calls GET /api/projects/:id", async () => {
    mockOk({ project_id: "test" });
    const result = await getProject("test");
    expect(result.project_id).toBe("test");
  });

  it("createProject sends POST with body", async () => {
    mockOk({ project_id: "new-proj", status: "created" });
    await createProject("new-proj", "Build API", "parent-1");
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/projects/",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ project_id: "new-proj", goal: "Build API", parent_id: "parent-1" }),
      }),
    );
  });

  it("deleteProject sends DELETE", async () => {
    mockOk({ status: "deleted" });
    await deleteProject("old-proj");
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/projects/old-proj",
      expect.objectContaining({ method: "DELETE" }),
    );
  });

  it("throws on error response with detail", async () => {
    mockError(400, "Project not found");
    await expect(getProject("missing")).rejects.toThrow("Project not found");
  });

  it("throws statusText when json parse fails", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      json: () => Promise.reject(new Error("parse error")),
    } as unknown as Response);
    await expect(listProjects()).rejects.toThrow("Internal Server Error");
  });
});

describe("orchestrator API", () => {
  it("startRun sends POST with goal and max_iterations", async () => {
    mockOk({ status: "started" });
    await startRun("proj-1", "Build feature", 10);
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/orchestrator/run",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ project_id: "proj-1", goal: "Build feature", max_iterations: 10 }),
      }),
    );
  });

  it("stopRun sends POST", async () => {
    mockOk({ status: "stopped" });
    await stopRun("proj-1");
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/orchestrator/run/proj-1/stop",
      expect.objectContaining({ method: "POST" }),
    );
  });
});

describe("models API", () => {
  it("listModels calls GET", async () => {
    mockOk({ models: ["gpt-4", "claude-3"] });
    const result = await listModels();
    expect(result.models).toHaveLength(2);
  });

  it("switchModel sends PUT", async () => {
    mockOk({ status: "switched" });
    await switchModel("engineer", "claude-3");
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/models/switch",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({ role: "engineer", new_model: "claude-3" }),
      }),
    );
  });

  it("reorderRoles sends PUT with roles array", async () => {
    mockOk({ status: "reordered" });
    await reorderRoles(["cto", "engineer", "tester"]);
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/models/reorder",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({ roles: ["cto", "engineer", "tester"] }),
      }),
    );
  });
});

describe("connectWebSocket", () => {
  it("creates WebSocket with correct URL and handles messages", () => {
    const instances: any[] = [];

    class MockWebSocket {
      static CONNECTING = 0;
      static OPEN = 1;
      static CLOSING = 2;
      static CLOSED = 3;
      CONNECTING = 0;
      OPEN = 1;
      CLOSING = 2;
      CLOSED = 3;
      url: string;
      onmessage: any = null;
      onopen: any = null;
      onclose: any = null;
      close = vi.fn();
      constructor(url: string) {
        this.url = url;
        instances.push(this);
      }
    }

    vi.stubGlobal("WebSocket", MockWebSocket);

    const onMessage = vi.fn();
    connectWebSocket("my-project", onMessage);

    expect(instances.length).toBe(1);
    expect(instances[0].url).toContain("my-project");

    // Simulate message
    instances[0].onmessage({ data: JSON.stringify({ type: "status" }) });
    expect(onMessage).toHaveBeenCalledWith({ type: "status" });

    // Simulate onopen resets reconnect delay
    instances[0].onopen();

    vi.unstubAllGlobals();
  });
});
